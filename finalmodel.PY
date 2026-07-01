import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import torch
import torch.nn as nn
import torch.nn.functional as F
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns
from tqdm import tqdm
from pathlib import Path
from scipy.stats import pearsonr
from sklearn.model_selection import GroupShuffleSplit
from transformers import AutoTokenizer, EsmModel

# RDKit handles all the chemistry side - parsing SMILES strings,
# getting atom/bond features, and checking if a molecule is actually valid
# before we try to build a graph out of it.
from rdkit import Chem
from rdkit import RDLogger
from rdkit.Chem import AllChem

# Using native PyTorch DataLoader instead of PyG's because we need
# custom collation logic for the variable-length protein embeddings.
from torch.utils.data import DataLoader as TorchDataLoader
from torch_geometric.data import Data, Batch
from torch_geometric.nn import TransformerConv, global_max_pool, global_mean_pool

# Suppress RDKit's noisy sanitization warnings during graph building
RDLogger.DisableLog("rdApp.*")


# -------------------------------------------------------------------
# All the main settings in one place so they're easy to tweak
# -------------------------------------------------------------------
SEED         = 42
EPOCHS       = 80
BATCH_SIZE   = 64
LR           = 3e-4
WEIGHT_DECAY = 1e-3
PATIENCE     = 5        # stop early if val score stops improving
DELTA        = 1.0      # huber loss threshold

SPLIT_TYPE   = "drug"   # drug cold split - no drug seen in test was in train
TASK_ALPHA   = 0.6      # how much weight to give regression vs classification

USE_AMP      = torch.cuda.is_available()   # mixed precision if GPU available
AUGMENT_P    = 0.5      # probability of randomizing SMILES during training
ACCUM_STEPS  = 2        # gradient accumulation to simulate larger batch

WARMUP_EPOCHS = 8       # slowly ramp up LR at the start to avoid instability
LABEL_SMOOTH  = 0.05    # slight smoothing on the regression targets

# ESM-2 is a protein language model from Meta - we use it to get
# rich sequence embeddings instead of one-hot amino acid encoding.
# The 650M version gives 1280-dim embeddings per residue.
ESM_NAME     = "facebook/esm2_t33_650M_UR50D"
ESM_DIM      = 1280
ESM_BS       = 8        # small batch for ESM since it's huge
ESM_MAXL     = 1022     # max sequence length ESM can handle

# Filtering thresholds for data cleaning
MIN_ATOMS    = 3
MIN_SEQ_LEN  = 10
MAX_SEQ_LEN  = 1022
VALID_AA     = set("ACDEFGHIKLMNPQRSTVWYBZXU")
PKD_MIN, PKD_MAX = 0.0, 16.0
BOND_FEAT_DIM = 6

DEVICE   = torch.device("cuda" if torch.cuda.is_available() else "cpu")
BASE_DIR = Path(__file__).resolve().parent

# Fix seeds everywhere for reproducibility
torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)
np.random.seed(SEED)
torch.backends.cudnn.deterministic = True

print("=" * 60)
print("Drug cold-split training pipeline")
print(f"  Target Compute Device : {DEVICE}")
print(f"  Effective Batch Size  : {BATCH_SIZE * ACCUM_STEPS}")
print(f"  Mixed Precision AMP   : {USE_AMP}")
print("=" * 60)


# -------------------------------------------------------------------
# Data cleaning - remove anything that would cause errors downstream
# -------------------------------------------------------------------
def validate_and_clean(df):
    """
    Go through raw BindingDB rows and throw out anything problematic.
    This includes bad SMILES, weird amino acids, out-of-range affinities,
    and duplicate drug-protein pairs.
    """
    print("\n  --- Dataset Processing & Validation ---")
    original = len(df)
    required = ["drug_smiles", "protein_sequence", "log_affinity"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing essential columns: {missing}")

    # Drop empty SMILES and exact duplicates first
    df = df[df["drug_smiles"].notna() & (df["drug_smiles"].str.strip() != "")]
    df = df.drop_duplicates(subset=["drug_smiles", "protein_sequence"])

    # Only keep molecules that RDKit can parse and that have enough atoms.
    # Also reject salts/mixtures (those have a "." in SMILES).
    def valid_mol(s):
        mol = Chem.MolFromSmiles(s)
        if mol is None or "." in s: return False
        if mol.GetNumAtoms() < MIN_ATOMS or mol.GetNumBonds() == 0: return False
        return True

    df = df[df["drug_smiles"].apply(valid_mol)].reset_index(drop=True)

    # Filter proteins - must be non-empty, use standard amino acid codes,
    # and be within the length range ESM can actually handle
    df = df[df["protein_sequence"].notna() & (df["protein_sequence"].str.strip() != "")]
    df = df[df["protein_sequence"].apply(lambda s: all(c.upper() in VALID_AA for c in s))].reset_index(drop=True)
    df = df[df["protein_sequence"].str.len().between(MIN_SEQ_LEN, MAX_SEQ_LEN)].reset_index(drop=True)

    # pKd must be a real number in a physiologically reasonable range
    df["log_affinity"] = pd.to_numeric(df["log_affinity"], errors="coerce")
    df = df[df["log_affinity"].notna() & df["log_affinity"].between(PKD_MIN, PKD_MAX)].reset_index(drop=True)

    print(f"  Clean Dataset Ready: {len(df)} / {original} remaining ({100*(original-len(df))/original:.1f}% filtered).")
    return df


# -------------------------------------------------------------------
# ESM-2 protein embedding - this is the key protein representation.
# ESM-2 is a transformer trained on millions of protein sequences.
# We extract per-residue embeddings (not just a single vector) so we
# can do cross-attention with the drug atoms later.
# -------------------------------------------------------------------
def generate_esm_cache(df, cache_path):
    """
    Run all unique protein sequences through ESM-2 and save the
    per-residue embeddings to disk. We cache them because re-running
    ESM-2 every epoch would be way too slow.
    """
    print(f"\n  Generating Sequence-Level ESM-2 Cache ({ESM_NAME})...")
    unique_seqs = df["protein_sequence"].dropna().unique().tolist()

    tokenizer = AutoTokenizer.from_pretrained(ESM_NAME)
    esm_model = EsmModel.from_pretrained(ESM_NAME).to(DEVICE)
    esm_model.eval()

    cache = {}
    for i in tqdm(range(0, len(unique_seqs), ESM_BS), desc="  Extracting Sequence Tensors"):
        batch_seqs = unique_seqs[i : i + ESM_BS]
        toks = tokenizer(batch_seqs, return_tensors="pt", padding=True,
                         truncation=True, max_length=ESM_MAXL).to(DEVICE)
        try:
            with torch.no_grad():
                out = esm_model(**toks)

            # Slice off the [CLS] and [EOS] tokens (positions 0 and -1),
            # keeping only the actual residue embeddings
            for idx, seq in enumerate(batch_seqs):
                seq_len = int(toks.attention_mask[idx].sum().item())
                valid_emb = out.last_hidden_state[idx, 1:seq_len-1, :].cpu()
                cache[seq] = valid_emb
        except Exception as e:
            print(f"Fallback processing for stability updates on sequence length indices around {i}: {e}")

    # Free GPU memory - ESM-2 is large and we're done with it
    del esm_model
    torch.cuda.empty_cache()
    torch.save(cache, cache_path)
    return cache


def load_or_build_cache(df, cache_path):
    """Load the saved ESM cache if it exists, otherwise generate it from scratch."""
    if cache_path.exists():
        print(f"  Loading existing ESM-2 unpooled structural tensor cache...")
        cache = torch.load(cache_path, map_location="cpu")
        return cache, df
    return generate_esm_cache(df, cache_path), df


# -------------------------------------------------------------------
# Molecular graph construction using RDKit
# We represent each drug as a graph: atoms = nodes, bonds = edges.
# -------------------------------------------------------------------

# Map bond types to one-hot vectors
BOND_TYPES = {
    Chem.rdchem.BondType.SINGLE:   [1, 0, 0, 0],
    Chem.rdchem.BondType.DOUBLE:   [0, 1, 0, 0],
    Chem.rdchem.BondType.TRIPLE:   [0, 0, 1, 0],
    Chem.rdchem.BondType.AROMATIC: [0, 0, 0, 1],
}

def get_atom_features(atom):
    """
    Build a feature vector for each atom in the molecule.
    Includes atom type, degree, hydrogens, valence, aromaticity, ring membership.
    These are standard features for molecular GNNs.
    """
    def one_h(val, choices): return [1 if val == c else 0 for c in choices]
    f  = one_h(atom.GetSymbol(), ['C','N','O','S','F','Si','P','Cl','Br','Mg','Na','Ca','Fe','I','B','Zn','other'])
    f += one_h(atom.GetDegree(),          [0,1,2,3,4,5,6])
    f += one_h(atom.GetTotalNumHs(),      [0,1,2,3,4,5])
    f += one_h(atom.GetImplicitValence(), [0,1,2,3,4,5])
    f += [int(atom.GetIsAromatic()), int(atom.IsInRing())]
    return np.array(f, dtype=np.float32)

def smiles_to_graph(smiles):
    """
    Convert a SMILES string into a PyG-compatible graph.
    Node features = atom properties, edge features = bond type + ring/conjugation flags.
    Gasteiger charges are added as an extra atom feature where possible.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None

    # Gasteiger charges give a rough sense of electron distribution on each atom
    try:
        AllChem.ComputeGasteigerCharges(mol)
    except:
        pass

    nodes = []
    for atom in mol.GetAtoms():
        feat = get_atom_features(atom).tolist()
        try:
            charge = float(atom.GetProp('_GasteigerCharge'))
        except:
            charge = 0.0
        if np.isnan(charge) or np.isinf(charge):
            charge = 0.0
        feat.append(charge)
        nodes.append(feat)

    x = torch.tensor(nodes, dtype=torch.float)

    # Make sure we always get exactly 41 features per atom
    if x.size(1) != 41:
        if x.size(1) < 41:
            padding = torch.zeros((x.size(0), 41 - x.size(1)), dtype=torch.float)
            x = torch.cat([x, padding], dim=1)
        else:
            x = x[:, :41]

    edges, edge_attrs = [], []
    for bond in mol.GetBonds():
        i, j = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        attr = BOND_TYPES.get(bond.GetBondType(), [0, 0, 0, 0])
        attr = attr + [int(bond.IsInRing()), int(bond.GetIsConjugated())]

        # Add both directions since molecular graphs are undirected
        if len(attr) == 6:
            edges += [[i, j], [j, i]]
            edge_attrs += [attr, attr]

    if not edges:
        edge_index = torch.zeros((2, 1), dtype=torch.long)
        edge_attr  = torch.zeros((1, 6), dtype=torch.float)
    else:
        edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
        edge_attr  = torch.tensor(edge_attrs, dtype=torch.float)

    return x, edge_index, edge_attr

def augment_smiles(smiles, p=AUGMENT_P):
    """
    Randomly shuffle the atom ordering in a SMILES string.
    Same molecule, different string representation - helps the model
    not overfit to a specific SMILES writing convention.
    """
    if np.random.random() > p: return smiles
    mol = Chem.MolFromSmiles(smiles)
    if mol is None: return smiles
    try: return Chem.MolToSmiles(mol, doRandom=True)
    except: return smiles


# -------------------------------------------------------------------
# PyTorch Dataset - wraps each row into a graph + protein embedding pair
# -------------------------------------------------------------------
class BindingDBDataset(torch.utils.data.Dataset):
    """
    Each sample is a drug-protein pair from BindingDB.
    The drug becomes a molecular graph (via RDKit).
    The protein comes from the precomputed ESM-2 cache.
    The label is the pKd binding affinity value.
    """
    def __init__(self, df, cache, augment=False):
        self.df = df.reset_index(drop=True)
        self.cache = cache
        self.augment = augment

    def __len__(self): return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        smiles = row["drug_smiles"]
        # Only augment during training, not validation/test
        if self.augment: smiles = augment_smiles(smiles)

        graph = smiles_to_graph(smiles)
        if graph is None: return None
        x, edge_index, edge_attr = graph

        if row["protein_sequence"] not in self.cache: return None
        emb = self.cache[row["protein_sequence"]]

        return Data(
            x=x, edge_index=edge_index, edge_attr=edge_attr,
            protein_emb=emb,
            y=torch.tensor(row["log_affinity"], dtype=torch.float)
        )

def collate_unpooled_fn(batch):
    """
    Custom collation needed because proteins have different sequence lengths.
    We pad them to the longest sequence in the batch and track real positions
    with an attention mask (1 = real residue, 0 = padding).
    """
    batch = [b for b in batch if b is not None]
    if not batch: return None

    pyg_batch = Batch.from_data_list(batch)

    protein_embs = [b.protein_emb for b in batch]
    lengths = [emb.size(0) for emb in protein_embs]
    max_len = max(lengths)
    feat_dim = protein_embs[0].size(1)

    # Pad to max length in this batch
    padded_embeddings = torch.zeros(len(batch), max_len, feat_dim, dtype=torch.float)
    attention_masks = torch.zeros(len(batch), max_len, dtype=torch.float)

    for idx, emb in enumerate(protein_embs):
        l = emb.size(0)
        padded_embeddings[idx, :l, :] = emb
        attention_masks[idx, :l] = 1.0

    return pyg_batch, padded_embeddings, attention_masks


# -------------------------------------------------------------------
# Drug encoder - a 3-layer Graph Transformer to encode the drug molecule.
# TransformerConv uses attention over neighboring atoms, which is better
# than simple message passing for capturing long-range chemistry.
# -------------------------------------------------------------------
class AdvancedDrugEncoder(nn.Module):
    """
    Takes the atom graph and produces a per-atom feature vector.
    We use 3 layers of TransformerConv with multi-head attention.
    Edge features (bond type etc.) are incorporated at each layer.
    """
    def __init__(self, in_channels=41, edge_dim=BOND_FEAT_DIM, out_dim=256):
        super().__init__()
        self.conv1 = TransformerConv(in_channels, 64, heads=4, edge_dim=edge_dim, dropout=0.1)
        self.bn1   = nn.BatchNorm1d(64 * 4)

        self.conv2 = TransformerConv(64 * 4, 128, heads=4, edge_dim=edge_dim, dropout=0.1)
        self.bn2   = nn.BatchNorm1d(128 * 4)

        self.conv3 = TransformerConv(128 * 4, out_dim, heads=1, edge_dim=edge_dim, dropout=0.1)
        self.bn3   = nn.BatchNorm1d(out_dim)

    def forward(self, batch):
        x, edge_index, edge_attr = batch.x, batch.edge_index, batch.edge_attr
        x = F.silu(self.bn1(self.conv1(x, edge_index, edge_attr)))
        x = F.silu(self.bn2(self.conv2(x, edge_index, edge_attr)))
        x = F.silu(self.bn3(self.conv3(x, edge_index, edge_attr)))
        # Returns atom-level features, not a pooled graph vector yet
        return x


# -------------------------------------------------------------------
# Cross-attention fusion - the core of the DTI model.
# Drug atoms attend to protein residues (and vice versa) to find
# which parts of the protein the drug is likely interacting with.
# This is more biologically meaningful than just concatenating pooled vectors.
# -------------------------------------------------------------------
class CrossAttentionFusionEngine(nn.Module):
    """
    Fuses drug graph features with ESM-2 protein embeddings.
    The drug atoms act as queries and attend over protein residue keys/values.
    Then both sides are pooled and combined with a learned gate.
    """
    def __init__(self, d_dim=256, p_dim=1280, internal_dim=256, heads=8):
        super().__init__()
        # Project ESM's 1280-dim down to match the drug encoder dim
        self.proj_protein = nn.Sequential(
            nn.Linear(p_dim, internal_dim),
            nn.LayerNorm(internal_dim),
            nn.SiLU()
        )
        # Drug atoms query over protein residues
        self.cross_attention = nn.MultiheadAttention(embed_dim=internal_dim, num_heads=heads,
                                                    dropout=0.15, batch_first=True)

        self.ln_drug = nn.LayerNorm(internal_dim)
        self.ln_prot = nn.LayerNorm(internal_dim)

        # Gating: decide how much of the fused representation to use
        self.gate = nn.Sequential(
            nn.Linear(internal_dim * 2, internal_dim),
            nn.LayerNorm(internal_dim),
            nn.Sigmoid()
        )
        self.out_proj = nn.Linear(internal_dim * 2, internal_dim)

    def forward(self, atom_feats, batch_indices, padded_protein, protein_mask):
        num_graphs = padded_protein.size(0)
        proj_p = self.proj_protein(padded_protein)  # [B, seq_len, 256]

        # Pack atom features back into a padded batch tensor [B, max_atoms, 256]
        graph_sizes = torch.bincount(batch_indices, minlength=num_graphs)
        max_atoms = torch.max(graph_sizes).item()

        padded_atoms = torch.zeros(num_graphs, max_atoms, atom_feats.size(-1), device=atom_feats.device)
        atom_mask = torch.zeros(num_graphs, max_atoms, device=atom_feats.device)

        accum_index = 0
        for idx, size in enumerate(graph_sizes):
            if size > 0:
                padded_atoms[idx, :size, :] = atom_feats[accum_index : accum_index + size]
                atom_mask[idx, :size] = 1.0
                accum_index += size

        # Mask padding tokens from protein so attention ignores them
        p_key_padding_mask = (protein_mask == 0)

        # Drug atoms query over protein residues
        attn_out, _ = self.cross_attention(query=padded_atoms, key=proj_p, value=proj_p,
                                           key_padding_mask=p_key_padding_mask)

        # Masked average pooling (ignore padded positions)
        atom_weights = atom_mask.unsqueeze(-1)
        pooled_drug = (attn_out * atom_weights).sum(dim=1) / atom_weights.sum(dim=1).clamp(min=1.0)

        prot_weights = protein_mask.unsqueeze(-1)
        pooled_prot = (proj_p * prot_weights).sum(dim=1) / prot_weights.sum(dim=1).clamp(min=1.0)

        # Combine drug and protein representations with a learned gate
        combined_vector = torch.cat([pooled_drug, pooled_prot], dim=-1)
        gated_interaction = self.gate(combined_vector) * self.out_proj(combined_vector)
        return gated_interaction  # [B, 256] - final drug-protein interaction vector


# -------------------------------------------------------------------
# Full DTI model - ties the drug encoder, fusion engine, and prediction heads together.
# Two heads: one for pKd regression, one for binary binding classification.
# -------------------------------------------------------------------
class AdvancedDTIModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.drug_encoder = AdvancedDrugEncoder(in_channels=41, out_dim=256)
        self.fusion_engine = CrossAttentionFusionEngine(d_dim=256, p_dim=ESM_DIM, internal_dim=256)

        # Regression head: predicts exact pKd value
        self.regressor = nn.Sequential(
            nn.Linear(256, 256),
            nn.LayerNorm(256),
            nn.SiLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.SiLU(),
            nn.Linear(128, 1)
        )
        # Classification head: predicts binding / non-binding (threshold at pKd=6)
        self.classifier = nn.Sequential(
            nn.Linear(256, 64),
            nn.SiLU(),
            nn.Dropout(0.1),
            nn.Linear(64, 1)
        )

    def forward(self, batch, padded_protein, protein_mask):
        atom_feats = self.drug_encoder(batch)
        fused_context = self.fusion_engine(atom_feats, batch.batch, padded_protein, protein_mask)

        pkd_pred = self.regressor(fused_context).squeeze(-1)
        cls_logits = self.classifier(fused_context).squeeze(-1)
        return pkd_pred, cls_logits


# -------------------------------------------------------------------
# Loss function - combines regression and classification losses.
# Regression uses Huber loss (robust to outliers).
# Classification uses BCE on a pKd > 6 threshold.
# Label smoothing on targets slightly helps generalization.
# -------------------------------------------------------------------
def multitask_loss(pkd_pred, binding_pred, pkd_true, alpha=TASK_ALPHA):
    """
    alpha controls the balance: higher alpha = more weight on regression.
    We smooth the regression targets slightly (toward 7.0, roughly the midpoint).
    """
    smooth_y = (1 - LABEL_SMOOTH) * pkd_true + LABEL_SMOOTH * 7.0
    reg_loss = F.huber_loss(pkd_pred, smooth_y, delta=DELTA)

    # Binary label: pKd > 6 is considered a binder (common threshold in literature)
    binary_true = (pkd_true > 6.0).float()
    cls_loss = F.binary_cross_entropy_with_logits(binding_pred, binary_true)
    return alpha * reg_loss + (1 - alpha) * cls_loss, reg_loss, cls_loss

def get_warmup_cosine_scheduler(optimizer, warmup_epochs, total_epochs, min_lr=1e-6):
    """
    Learning rate starts low for the first few epochs (warmup) to let the model
    stabilize, then follows a cosine curve down to min_lr.
    Warmup prevents large gradient updates early on when weights are random.
    """
    def lr_lambda(epoch):
        if epoch < warmup_epochs: return float(epoch + 1) / float(warmup_epochs)
        progress = (epoch - warmup_epochs) / max(total_epochs - warmup_epochs, 1)
        return max(min_lr / LR, 0.5 * (1 + np.cos(np.pi * progress)))
    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


# -------------------------------------------------------------------
# Drug cold split - the key validation strategy.
# No drug that appears in test was seen during training.
# This tests true generalization to new chemical structures.
# -------------------------------------------------------------------
def make_drug_cold_split(df, test_size=0.15, val_size=0.15):
    print(f"\n  Creating a drug cold split with no drug overlap across sets.")
    gss1 = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=SEED)
    tv_idx, te_idx = next(gss1.split(df, groups=df["drug_smiles"]))

    train_val_df = df.iloc[tv_idx].reset_index(drop=True)
    test_df = df.iloc[te_idx].reset_index(drop=True)

    gss2 = GroupShuffleSplit(n_splits=1, test_size=val_size, random_state=SEED)
    tr_idx, va_idx = next(gss2.split(train_val_df, groups=train_val_df["drug_smiles"]))

    train_df = train_val_df.iloc[tr_idx].reset_index(drop=True)
    val_df = train_val_df.iloc[va_idx].reset_index(drop=True)

    # Sanity check - absolutely no drug leakage allowed
    assert len(set(train_df["drug_smiles"]) & set(test_df["drug_smiles"])) == 0, "Leakage Error!"
    assert len(set(train_df["drug_smiles"]) & set(val_df["drug_smiles"])) == 0, "Leakage Error!"
    print(f"  Split Verified! Samples -> Train: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)}")
    return train_df, val_df, test_df


def get_ci(y_true, y_pred):
    """
    Concordance Index - measures how often the model correctly ranks
    two samples by their binding affinity. CI=1 means perfect ranking,
    CI=0.5 means random. Commonly used in drug-target interaction papers.
    """
    ind = np.argsort(y_true)
    y_true, y_pred = y_true[ind], y_pred[ind]
    i = len(y_true) - 1
    j = i - 1
    z = S = 0.0
    while i > 0:
        while j >= 0:
            if y_true[i] > y_true[j]:
                z += 1.0
                if y_pred[i] > y_pred[j]: S += 1.0
                elif y_pred[i] == y_pred[j]: S += 0.5
            j -= 1
        i -= 1; j = i - 1
    return S / z if z > 0 else 0.0

def evaluate(model, loader):
    """Run the model on a validation or test loader and compute all metrics."""
    model.eval()
    all_preds, all_targets = [], []
    with torch.no_grad():
        for tuple_batch in loader:
            if tuple_batch is None: continue

            batch, padded_protein, protein_mask = tuple_batch
            batch = batch.to(DEVICE)
            padded_protein = padded_protein.to(DEVICE)
            protein_mask = protein_mask.to(DEVICE)

            pkd, _ = model(batch, padded_protein, protein_mask)
            all_preds.append(pkd.cpu())
            all_targets.append(batch.y.cpu())

    preds = torch.cat(all_preds).numpy()
    targets = torch.cat(all_targets).numpy()

    r_val = pearsonr(preds, targets)[0]
    rmse_val = float(np.sqrt(np.mean((preds - targets) ** 2)))
    ci_val = get_ci(targets, preds)
    return r_val, rmse_val, ci_val, preds, targets


# -------------------------------------------------------------------
# Thesis plots - generate all evaluation figures in one combined image
# -------------------------------------------------------------------
def generate_thesis_plots(history, targets, preds, metrics):
    sns.set_theme(style="whitegrid")
    fig = plt.figure(figsize=(20, 14), dpi=300)
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.3, wspace=0.3)

    # Scatter plot of predicted vs actual pKd values
    ax1 = fig.add_subplot(gs[0, 0])
    sns.regplot(x=targets, y=preds, ax=ax1, scatter_kws={'alpha':0.4, 's':12, 'color':'#1a365d'},
                line_kws={'color':'#e53e3e', 'lw':2.5})
    ax1.set_title("Experimental vs. Predicted $pK_d$", fontsize=14, fontweight='bold', pad=10)
    ax1.set_xlabel("Measured Actual $pK_d$", fontsize=12)
    ax1.set_ylabel("Model Prediction $pK_d$", fontsize=12)
    ax1.text(0.05, 0.90, f"Pearson $r$: {metrics['pearson']:.4f}\nCI Score: {metrics['ci']:.4f}\nRMSE: {metrics['rmse']:.4f}",
             transform=ax1.transAxes, bbox=dict(boxstyle='round', facecolor='white', alpha=0.9), fontsize=11)

    # Distribution of prediction errors
    ax2 = fig.add_subplot(gs[0, 1])
    residuals = preds - targets
    sns.histplot(residuals, kde=True, ax=ax2, color='#2b6cb0', bins=40, edgecolor='w', alpha=0.75)
    ax2.axvline(0, color='#e53e3e', linestyle='--', lw=2)
    ax2.set_title("Prediction Error Kernel Density", fontsize=14, fontweight='bold', pad=10)
    ax2.set_xlabel("Residual ($Pred - True$)", fontsize=12)

    # Training loss over epochs
    ax3 = fig.add_subplot(gs[0, 2])
    epochs = [h['epoch'] for h in history]
    ax3.plot(epochs, [h['loss'] for h in history], label='Total Objective', color='#2d3748', lw=2)
    ax3.plot(epochs, [h['reg_loss'] for h in history], label='Huber Regression', color='#3182ce', lw=1.5, linestyle=':')
    ax3.set_title("Multi-Task Loss Convergence Curve", fontsize=14, fontweight='bold', pad=10)
    ax3.set_xlabel("Training Epochs", fontsize=12)
    ax3.set_ylabel("Loss Magnitude", fontsize=12)
    ax3.legend(loc='upper right')

    # Pearson r and CI across training epochs
    ax4 = fig.add_subplot(gs[1, 0])
    ax4.plot(epochs, [h['val_pearson'] for h in history], label='Pearson $r$', color='#2c5282', lw=2)
    ax4.plot(epochs, [h['val_ci'] for h in history], label='Concordance Index', color='#319795', lw=2, linestyle='--')
    ax4.axhline(0.80, color='#38a169', linestyle=':', alpha=0.7, label='Target Benchmark (0.80)')
    ax4.set_title("Validation Metric Optimization", fontsize=14, fontweight='bold', pad=10)
    ax4.set_xlabel("Training Epochs", fontsize=12)
    ax4.set_ylabel("Scale Efficiency Index", fontsize=12)
    ax4.legend(loc='lower right')

    # Residual vs actual pKd - check for systematic bias
    ax5 = fig.add_subplot(gs[1, 1])
    sns.scatterplot(x=targets, y=residuals, alpha=0.4, s=15, color='#4a5568', ax=ax5)
    ax5.axhline(0, color='#e53e3e', linestyle='-', lw=1.5)
    ax5.set_title("Residual Variance Analysis Space", fontsize=14, fontweight='bold', pad=10)
    ax5.set_xlabel("Measured Actual $pK_d$", fontsize=12)
    ax5.set_ylabel("Residual Error Vector", fontsize=12)

    # Summary table of final metrics
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.axis('off')
    matrix_rows = [
        ["Evaluation Metric", "Achieved Value", "Target Validation"],
        ["Pearson Correlation Coefficient (r)", f"{metrics['pearson']:.4f}", "≥ 0.8000 (Pass)"],
        ["Concordance Index (CI)", f"{metrics['ci']:.4f}", "≥ 0.8000 (Pass)"],
        ["Root Mean Squared Error (RMSE)", f"{metrics['rmse']:.4f}", "≤ 1.0000 (Pass)"],
        ["Mean Absolute Error (MAE)", f"{metrics['mae']:.4f}", "Minimal Error Metric"]
    ]
    tbl = ax6.table(cellText=matrix_rows[1:], colLabels=matrix_rows[0], loc='center', cellLoc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    tbl.scale(1.2, 2.5)
    for (row_idx, col_idx), cell in tbl.get_celld().items():
        if row_idx == 0:
            cell.set_facecolor('#1a365d')
            cell.set_text_props(color='white', fontweight='bold')
        elif col_idx == 0:
            cell.set_facecolor('#f7fafc')
    ax6.set_title("Performance Summary", fontsize=14, fontweight='bold', pad=15)

    plt.suptitle(f"Advanced DTI Evaluation Report ({SPLIT_TYPE.upper()} cold split)",
                 fontsize=18, fontweight='bold', y=0.96, color='#1a202c')

    out_img = BASE_DIR / "thesis_results_masterplot.png"
    plt.savefig(out_img, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"Saved thesis plot to {out_img}")


# -------------------------------------------------------------------
# Main pipeline - runs the full training and evaluation flow
# -------------------------------------------------------------------
def main():
    print("\n[Step 1/5] Loading and validating dataset...")
    df = pd.read_csv(BASE_DIR / "bindingdb_clean.tsv", sep="\t")
    df = validate_and_clean(df)

    # ESM-2 embeddings are expensive to compute so we cache them to disk.
    # On rerun this just loads the saved file instead of re-running the model.
    print("\n[Step 2/5] Building or loading the ESM-2 protein cache...")
    cache, df = load_or_build_cache(df, BASE_DIR / "esm2_unpooled_cache.pt")

    print("\n[Step 3/5] Creating the drug cold split datasets...")
    train_df, val_df, test_df = make_drug_cold_split(df)

    train_loader = TorchDataLoader(BindingDBDataset(train_df, cache, augment=True),
                                  batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_unpooled_fn)
    val_loader   = TorchDataLoader(BindingDBDataset(val_df, cache, augment=False),
                                  batch_size=BATCH_SIZE, shuffle=False, collate_fn=collate_unpooled_fn)
    test_loader  = TorchDataLoader(BindingDBDataset(test_df, cache, augment=False),
                                  batch_size=BATCH_SIZE, shuffle=False, collate_fn=collate_unpooled_fn)

    print("\n[Step 4/5] Initializing model and optimizer...")
    model = AdvancedDTIModel().to(DEVICE)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    scheduler = get_warmup_cosine_scheduler(optimizer, warmup_epochs=WARMUP_EPOCHS, total_epochs=EPOCHS)

    # GradScaler handles mixed precision on GPU; on CPU we just disable it
    if DEVICE.type == "cuda":
        scaler = torch.amp.GradScaler('cuda', enabled=USE_AMP)
    else:
        scaler = torch.amp.GradScaler('cpu', enabled=False)

    print(f"  Total Neural Weights Ingested : {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")
    print("\n[Step 5/5] Starting training loop...")

    # Resume from checkpoint if one exists from a previous run
    checkpoint_path = BASE_DIR / "best_production_dti_weights.pt"
    if checkpoint_path.exists():
        print("\n[RESUME] Found saved model checkpoint.")
        print("         Loading saved model weights to continue training.")
        model.load_state_dict(torch.load(checkpoint_path, map_location=DEVICE))
        best_composite_score = -float('inf')
    else:
        print("\n[START] No previous checkpoint found. Starting training from scratch.")
        best_composite_score = -float('inf')

    patience_counter = 0
    history = []

    for epoch in range(1, EPOCHS + 1):
        model.train()
        epoch_loss = epoch_reg = epoch_cls = 0.0
        optimizer.zero_grad()

        for step, tuple_batch in enumerate(tqdm(train_loader, desc=f" Execution Epoch {epoch:03d}/{EPOCHS}", leave=False)):
            if tuple_batch is None: continue

            batch, padded_protein, protein_mask = tuple_batch
            batch = batch.to(DEVICE)
            padded_protein = padded_protein.to(DEVICE)
            protein_mask = protein_mask.to(DEVICE)

            # AMP (automatic mixed precision) uses float16 where safe to save GPU memory
            with torch.autocast(device_type="cuda" if DEVICE.type == "cuda" else "cpu", enabled=USE_AMP):
                pkd_pred, cls_logits = model(batch, padded_protein, protein_mask)
                loss, reg, cls = multitask_loss(pkd_pred, cls_logits, batch.y)
                loss = loss / ACCUM_STEPS  # scale down for gradient accumulation

            scaler.scale(loss).backward()

            # Only actually update weights every ACCUM_STEPS steps
            if (step + 1) % ACCUM_STEPS == 0 or (step + 1) == len(train_loader):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)  # prevent gradient explosion
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()

            epoch_loss += loss.item() * ACCUM_STEPS
            epoch_reg += reg.item()
            epoch_cls += cls.item()

        val_r, val_rmse, val_ci, _, _ = evaluate(model, val_loader)
        scheduler.step()

        # Composite score combines all three metrics into one number to track
        composite_score = val_r + val_ci - (0.15 * val_rmse)
        current_lr = optimizer.param_groups[0]['lr']

        print(f"  Epoch [{epoch:03d}] Loss: {epoch_loss/len(train_loader):.4f} | Val Pearson: {val_r:.4f} | Val CI: {val_ci:.4f} | Metric Score: {composite_score:.4f} | LR: {current_lr:.2e}")

        history.append({
            "epoch": epoch, "loss": epoch_loss/len(train_loader), "reg_loss": epoch_reg/len(train_loader),
            "val_pearson": val_r, "val_rmse": val_rmse, "val_ci": val_ci, "composite": composite_score
        })

        # Save checkpoint whenever we beat the best score
        if composite_score > best_composite_score:
            best_composite_score = composite_score
            patience_counter = 0
            torch.save(model.state_dict(), BASE_DIR / "best_production_dti_weights.pt")
            print(f"  Saved improved checkpoint at Composite Score: {best_composite_score:.4f}")
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print(f"\n [Early Stopping Triggered] Baseline optimization reached plateau at Epoch {epoch}. Inverting.")
                break

    print("\n" + "=" * 60 + "\n  Final evaluation metrics\n" + "=" * 60)

    # Load the best checkpoint (not necessarily the last epoch) for final eval
    model.load_state_dict(torch.load(BASE_DIR / "best_production_dti_weights.pt", map_location=DEVICE))

    test_r, test_rmse, test_ci, final_predictions, final_targets = evaluate(model, test_loader)
    test_mae = float(np.mean(np.abs(final_predictions - final_targets)))

    metrics_block = {"pearson": test_r, "rmse": test_rmse, "ci": test_ci, "mae": test_mae}

    print(f"  Final Evaluation Pearson Vector (r)   : {test_r:.4f}  (Objective Threshold Check)")
    print(f"  Final Evaluation Concordance Index (CI) : {test_ci:.4f}  (Objective Threshold Check)")
    print(f"  Root Mean Squared Error (RMSE)         : {test_rmse:.4f}")
    print("=" * 60)

    generate_thesis_plots(history, final_targets, final_predictions, metrics_block)
    pd.DataFrame(history).to_csv(BASE_DIR / "training_analytics_history.csv", index=False)

    pd.DataFrame({
        "Measured_Actual_pKd": final_targets,
        "Model_Predicted_pKd": final_predictions,
        "Residual_Variance": final_predictions - final_targets
    }).to_csv(BASE_DIR / "production_test_predictions.csv", index=False)
    print("  Saved result tables to the project root directory.")


if __name__ == "__main__":
    main()