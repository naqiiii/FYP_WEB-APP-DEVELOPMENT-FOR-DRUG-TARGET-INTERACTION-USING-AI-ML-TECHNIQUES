from typing import Dict
from pathlib import Path

# These ranges are shared with the frontend so the gauge colors
# stay consistent with what the model actually outputs
MODEL_METADATA = {
    "threshold_strong": 7.0,
    "threshold_moderate": 6.0,
    "gauge_min": 3.0,
    "gauge_max": 9.0,
    "unit": "pKd"
}

# Wrap all ML imports in a try/except so the server can still start
# and return a proper error message if torch/rdkit aren't installed
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import numpy as np
    from rdkit import Chem
    from rdkit import RDLogger
    from rdkit.Chem import AllChem
    from torch_geometric.data import Data, Batch
    from torch_geometric.nn import TransformerConv

    RDLogger.DisableLog("rdApp.*")
    HAS_TORCH = True
except ImportError as e:
    ML_IMPORT_ERROR = e
    print(f"Error: ML dependencies are not installed: {e}")
    HAS_TORCH = False
else:
    ML_IMPORT_ERROR = None


if HAS_TORCH:
    # Automatically detect if a GPU is available to leverage the RTX A6000
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

    # Bond type → one-hot encoding, same as in training
    BOND_TYPES = {
        Chem.rdchem.BondType.SINGLE:   [1, 0, 0, 0],
        Chem.rdchem.BondType.DOUBLE:   [0, 1, 0, 0],
        Chem.rdchem.BondType.TRIPLE:   [0, 0, 1, 0],
        Chem.rdchem.BondType.AROMATIC: [0, 0, 0, 1],
    }
    ESM_DIM = 1280  # ESM-2 650M gives 1280-dim per-residue embeddings

    def get_atom_features(atom):
        # Same 41-feature atom vector used during training - must match exactly
        def one_h(val, choices): return [1 if val == c else 0 for c in choices]
        f  = one_h(atom.GetSymbol(), ['C','N','O','S','F','Si','P','Cl','Br','Mg','Na','Ca','Fe','I','B','Zn','other'])
        f += one_h(atom.GetDegree(),          [0,1,2,3,4,5,6])
        f += one_h(atom.GetTotalNumHs(),      [0,1,2,3,4,5])
        f += one_h(atom.GetImplicitValence(), [0,1,2,3,4,5])
        f += [int(atom.GetIsAromatic()), int(atom.IsInRing())]
        return np.array(f, dtype=np.float32)

    def smiles_to_graph(smiles):
        # Convert SMILES to a PyG-compatible graph for the drug encoder.
        # Gasteiger charges are appended as the 41st atom feature.
        mol = Chem.MolFromSmiles(smiles)
        if mol is None: return None
        try: AllChem.ComputeGasteigerCharges(mol)
        except: pass

        nodes = []
        for atom in mol.GetAtoms():
            feat = get_atom_features(atom).tolist()
            try: charge = float(atom.GetProp('_GasteigerCharge'))
            except: charge = 0.0
            nodes.append(feat + [charge])

        x = torch.tensor(nodes, dtype=torch.float)
        # Enforce exactly 41 features - pad or truncate if something went wrong
        if x.size(1) != 41:
            x = torch.cat([x, torch.zeros((x.size(0), 41 - x.size(1)))], dim=1) if x.size(1) < 41 else x[:, :41]

        edges, edge_attrs = [], []
        for bond in mol.GetBonds():
            i, j = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
            attr = BOND_TYPES.get(bond.GetBondType(), [0, 0, 0, 0]) + [int(bond.IsInRing()), int(bond.GetIsConjugated())]
            # Add both directions since the graph is undirected
            edges += [[i, j], [j, i]]; edge_attrs += [attr, attr]

        edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous() if edges else torch.zeros((2, 1), dtype=torch.long)
        edge_attr  = torch.tensor(edge_attrs, dtype=torch.float) if edges else torch.zeros((1, 6), dtype=torch.float)
        return x, edge_index, edge_attr

    # -------------------------------------------------------------------
    # Model architecture - must be identical to the training code
    # so the saved weights load correctly
    # -------------------------------------------------------------------

    class AdvancedDrugEncoder(nn.Module):
        # 3-layer Graph Transformer that encodes atom graphs into per-atom features.
        # TransformerConv uses multi-head attention over neighboring atoms,
        # which captures longer-range chemical context than simple GCN layers.
        def __init__(self):
            super().__init__()
            self.conv1 = TransformerConv(41, 64, heads=4, edge_dim=6, dropout=0.1)
            self.bn1   = nn.BatchNorm1d(256)
            self.conv2 = TransformerConv(256, 128, heads=4, edge_dim=6, dropout=0.1)
            self.bn2   = nn.BatchNorm1d(512)
            self.conv3 = TransformerConv(512, 256, heads=1, edge_dim=6, dropout=0.1)
            self.bn3   = nn.BatchNorm1d(256)

        def forward(self, batch):
            x, edge_index, edge_attr = batch.x, batch.edge_index, batch.edge_attr
            x = F.silu(self.bn1(self.conv1(x, edge_index, edge_attr)))
            x = F.silu(self.bn2(self.conv2(x, edge_index, edge_attr)))
            return F.silu(self.bn3(self.conv3(x, edge_index, edge_attr)))

    class CrossAttentionFusionEngine(nn.Module):
        # Drug atoms attend over protein residues (from ESM-2) to find which
        # parts of the protein the drug is likely interacting with.
        # This is more biologically meaningful than just concatenating pooled vectors.
        def __init__(self):
            super().__init__()
            # Project ESM's 1280-dim down to 256 to match the drug encoder output
            self.proj_protein = nn.Sequential(nn.Linear(ESM_DIM, 256), nn.LayerNorm(256), nn.SiLU())
            self.cross_attention = nn.MultiheadAttention(embed_dim=256, num_heads=8, dropout=0.15, batch_first=True)

            self.ln_drug = nn.LayerNorm(256)
            self.ln_prot = nn.LayerNorm(256)

            # Learned gate decides how to blend the two representations
            self.gate = nn.Sequential(nn.Linear(512, 256), nn.LayerNorm(256), nn.Sigmoid())
            self.out_proj = nn.Linear(512, 256)

        def forward(self, atom_feats, batch_indices, padded_protein, protein_mask):
            num_graphs = padded_protein.size(0)
            proj_p = self.proj_protein(padded_protein)

            # Re-pack flat atom features back into a padded batch tensor
            graph_sizes = torch.bincount(batch_indices, minlength=num_graphs)
            max_atoms = torch.max(graph_sizes).item()

            padded_atoms = torch.zeros(num_graphs, max_atoms, 256, device=atom_feats.device)
            atom_mask = torch.zeros(num_graphs, max_atoms, device=atom_feats.device)

            accum_index = 0
            for idx, size in enumerate(graph_sizes):
                if size > 0:
                    padded_atoms[idx, :size, :] = atom_feats[accum_index : accum_index + size]
                    atom_mask[idx, :size] = 1.0; accum_index += size

            # Drug atoms query over protein residues; padding tokens are masked out
            attn_out, _ = self.cross_attention(query=padded_atoms, key=proj_p, value=proj_p, key_padding_mask=(protein_mask == 0))

            attn_out = self.ln_drug(attn_out)
            proj_p = self.ln_prot(proj_p)

            # Masked average pooling - ignore padded positions in both sequences
            p_drug = (attn_out * atom_mask.unsqueeze(-1)).sum(dim=1) / atom_mask.unsqueeze(-1).sum(dim=1).clamp(min=1.0)
            p_prot = (proj_p * protein_mask.unsqueeze(-1)).sum(dim=1) / protein_mask.unsqueeze(-1).sum(dim=1).clamp(min=1.0)

            combined = torch.cat([p_drug, p_prot], dim=-1)
            return self.gate(combined) * self.out_proj(combined)

    class AdvancedDTIModel(nn.Module):
        # Full DTI model: drug graph encoder → cross-attention fusion → two heads.
        # Regression head predicts pKd; classifier head predicts binding/non-binding.
        # Only the regression output is used at inference time.
        def __init__(self):
            super().__init__()
            self.drug_encoder = AdvancedDrugEncoder()
            self.fusion_engine = CrossAttentionFusionEngine()
            self.regressor = nn.Sequential(nn.Linear(256, 256), nn.LayerNorm(256), nn.SiLU(), nn.Dropout(0.2), nn.Linear(256, 128), nn.SiLU(), nn.Linear(128, 1))
            self.classifier = nn.Sequential(nn.Linear(256, 64), nn.SiLU(), nn.Dropout(0.1), nn.Linear(64, 1))

        def forward(self, batch, padded_protein, protein_mask):
            atom_feats = self.drug_encoder(batch)
            fused_context = self.fusion_engine(atom_feats, batch.batch, padded_protein, protein_mask)
            return self.regressor(fused_context).squeeze(-1), self.classifier(fused_context).squeeze(-1)

    # -------------------------------------------------------------------
    # -------------------------------------------------------------------
    # Artifact loading - model weights and cache migration
    # -------------------------------------------------------------------
    import hashlib
    import gc
    
    _MODEL = None
    CACHE_DIR = BASE_DIR / "esm2_cache"

    def get_sequence_hash(sequence: str) -> str:
        """Compute the MD5 hash of the canonical protein sequence."""
        cleaned_seq = "".join(c for c in sequence.strip().upper() if c.isalpha())
        return hashlib.md5(cleaned_seq.encode('utf-8')).hexdigest()

    def get_cached_embedding(sequence: str) -> torch.Tensor | None:
        """Retrieve a cached ESM-2 embedding from the cache directory."""
        if not CACHE_DIR.exists():
            return None
        seq_hash = get_sequence_hash(sequence)
        file_path = CACHE_DIR / f"{seq_hash}.pt"
        if file_path.exists():
            try:
                # Load on CPU, map to DEVICE as needed later
                return torch.load(file_path, map_location="cpu", weights_only=True)
            except Exception as e:
                print(f"Warning: Failed to load cached embedding for sequence hash {seq_hash}: {e}")
        return None

    def save_embedding_to_cache(sequence: str, embedding: torch.Tensor):
        """Save a generated ESM-2 embedding to the cache directory."""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            seq_hash = get_sequence_hash(sequence)
            file_path = CACHE_DIR / f"{seq_hash}.pt"
            # Keep cache on CPU to preserve VRAM
            torch.save(embedding.cpu(), file_path)
        except Exception as e:
            print(f"Warning: Failed to save embedding to cache: {e}")

    def migrate_old_cache_if_needed(old_cache_path: Path):
        """Extract embeddings from monolithic cache and save as individual files."""
        if not old_cache_path.exists():
            return
        try:
            print(f"\n[MIGRATION] One-time cache migration: Extracting from monolithic {old_cache_path.name}...")
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            
            # Load monolithic cache dict
            old_cache = torch.load(old_cache_path, map_location="cpu", weights_only=True)
            migrated_count = 0
            
            for seq, emb in old_cache.items():
                seq_hash = get_sequence_hash(seq)
                file_path = CACHE_DIR / f"{seq_hash}.pt"
                if not file_path.exists():
                    torch.save(emb.cpu(), file_path)
                    migrated_count += 1
            
            print(f"[MIGRATION] Successfully migrated {migrated_count} embedding vectors to {CACHE_DIR}.")
            
            # Rename the monolithic cache so it's not checked or loaded again
            migrated_path = old_cache_path.with_name(old_cache_path.name + ".migrated")
            old_cache_path.rename(migrated_path)
            print(f"[MIGRATION] Renamed original monolithic cache file to {migrated_path.name}\n")
        except Exception as e:
            print(f"[MIGRATION WARNING] Failed to migrate monolithic cache: {e}")
            import traceback
            traceback.print_exc()

    def load_artifacts():
        global _MODEL
        if _MODEL is not None:
            return

        model_path = BASE_DIR / "best_production_dti_weights.pt"
        old_cache_path = BASE_DIR / "esm2_unpooled_cache.pt"

        # Migrate monolithic file to directory on startup if present
        if old_cache_path.exists():
            migrate_old_cache_if_needed(old_cache_path)

        if not model_path.exists():
            raise FileNotFoundError(
                f"Required model weights file not found in {BASE_DIR}. "
                "Expected best_production_dti_weights.pt."
            )

        try:
            print(f"Loading AdvancedDTIModel from {model_path}...")
            _MODEL = AdvancedDTIModel()
            _MODEL.load_state_dict(torch.load(model_path, map_location=DEVICE, weights_only=True))
            _MODEL.eval()
            _MODEL.to(DEVICE)
            print("Model loaded successfully.")
        except Exception as e:
            _MODEL = None
            raise RuntimeError(f"Failed to load ML artifacts: {e}") from e

    # Fail early on startup if the required model files are missing
    load_artifacts()


# -------------------------------------------------------------------
# ESM-2 live embedding - only runs if the protein isn't in the cache.
# ESM-2 is loaded lazily here because it's ~1.3GB and most requests
# will be served from the cache without needing it.
# -------------------------------------------------------------------
_ESM_MODEL = None
_ESM_TOKENIZER = None

def preload_esm2():
    """Load the ESM-2 model and tokenizer dynamically. Called during startup lifespan."""
    global _ESM_MODEL, _ESM_TOKENIZER
    if not HAS_TORCH:
        return
    if _ESM_MODEL is not None and _ESM_TOKENIZER is not None:
        return
        
    # Try loading from local Hugging Face cache first to avoid proxy/firewall timeouts
    try:
        from transformers import AutoTokenizer, EsmModel
        print("Attempting to load ESM-2 model offline from local cache...")
        _ESM_TOKENIZER = AutoTokenizer.from_pretrained("facebook/esm2_t33_650M_UR50D", local_files_only=True)
        _ESM_MODEL = EsmModel.from_pretrained("facebook/esm2_t33_650M_UR50D", local_files_only=True)
        _ESM_MODEL.eval()
        _ESM_MODEL.to(DEVICE)
        print("ESM-2 model loaded offline successfully.")
        return
    except Exception as local_err:
        print(f"Local cache load failed or model not found locally: {local_err}")
        print("Attempting online load from Hugging Face hub...")

    try:
        from transformers import AutoTokenizer, EsmModel
        _ESM_TOKENIZER = AutoTokenizer.from_pretrained("facebook/esm2_t33_650M_UR50D")
        _ESM_MODEL = EsmModel.from_pretrained("facebook/esm2_t33_650M_UR50D")
        _ESM_MODEL.eval()
        _ESM_MODEL.to(DEVICE)
        print("ESM-2 model downloaded and loaded online successfully.")
    except Exception as e:
        print(f"Warning: Failed to load ESM-2 model online/offline: {e}")

def get_esm2_embedding_unpooled(sequence: str) -> torch.Tensor:
    global _ESM_MODEL, _ESM_TOKENIZER
    # Load ESM-2 on first call only - expensive but only happens for new sequences
    if _ESM_MODEL is None or _ESM_TOKENIZER is None:
        preload_esm2()
        if _ESM_MODEL is None or _ESM_TOKENIZER is None:
            raise RuntimeError("ESM-2 model could not be initialized.")

    cleaned_seq = "".join(c for c in sequence.strip().upper() if c.isalpha())
    if not cleaned_seq:
        raise ValueError("Protein sequence is empty or invalid.")

    inputs = _ESM_TOKENIZER(cleaned_seq, return_tensors="pt", max_length=1022, truncation=True)
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = _ESM_MODEL(**inputs)

    # Slice off [CLS] and [EOS] tokens - we only want the actual residue embeddings
    emb = outputs.last_hidden_state[0, 1:int(inputs['attention_mask'][0].sum().item())-1, :].cpu()
    return emb


def predict_dti(drug_smiles: str, protein_sequence: str) -> Dict:
    """
    Main prediction entry point called by the API route.
    Takes a SMILES string and protein sequence, returns pKd + affinity in nM.
    Raises RuntimeError if the model isn't loaded, ValueError for bad inputs.
    """
    if not HAS_TORCH or _MODEL is None:
        detail = f" Missing dependency: {ML_IMPORT_ERROR}" if ML_IMPORT_ERROR else ""
        raise RuntimeError(f"Real ML model is not available.{detail}")

    # Check cache directory first
    emb = get_cached_embedding(protein_sequence)
    if emb is None:
        print(f"Protein sequence not in cache. Generating live ESM-2 embedding...")
        try:
            emb = get_esm2_embedding_unpooled(protein_sequence)
            save_embedding_to_cache(protein_sequence, emb)
        except Exception as e:
            raise ValueError(f"Failed to generate ESM-2 embedding for sequence: {e}")

    graph = smiles_to_graph(drug_smiles)
    if graph is None:
        raise ValueError("Invalid SMILES string provided. Cannot parse molecular graph.")

    x, edge_index, edge_attr = graph

    # Sanitize embeddings - NaN/inf can appear in ESM output for unusual sequences
    if torch.isnan(emb).any() or torch.isinf(emb).any():
        emb = torch.nan_to_num(emb, nan=0.0, posinf=0.0, neginf=0.0)

    data = Data(x=x, edge_index=edge_index, edge_attr=edge_attr)
    batch = Batch.from_data_list([data]).to(DEVICE)

    # Build padded protein tensor - batch size is always 1 at inference
    max_len = emb.size(0)
    padded_p = torch.zeros(1, max_len, ESM_DIM).to(DEVICE)
    p_mask = torch.zeros(1, max_len).to(DEVICE)
    padded_p[0, :max_len, :] = emb.to(DEVICE)
    p_mask[0, :max_len] = 1.0

    with torch.no_grad():
        pred_pkd, pred_class = _MODEL(batch, padded_p, p_mask)
        pred_pkd = pred_pkd.item()
        # Compute confidence score dynamically from the classifier head
        confidence = float(torch.sigmoid(pred_class).item())

    # Convert pKd back to nM affinity for display: Kd(nM) = 10^(9 - pKd)
    try:
        affinity = float(10 ** (9.0 - pred_pkd))
    except OverflowError:
        affinity = float('inf')

    # Trigger garbage collection to clean up memory
    gc.collect()
    if DEVICE.type == "cuda":
        torch.cuda.empty_cache()

    return {
        "affinity": round(affinity, 3) if affinity != float('inf') else 9999.999,
        "log_affinity": round(pred_pkd, 3),
        "confidence": round(confidence, 4),
        "model_name": "AdvancedDTIModel (TransformerConv+CrossAttentionFusion)",
        "metadata": MODEL_METADATA
    }


def predict_dti_batch(drug_inputs: list[str], protein_inputs: list[str]) -> list[Dict]:
    """
    Predict DTI in parallel using PyG's Batch mechanism to leverage GPU tensor cores.
    Aligns inputs: if one list has size 1, replicates it to match the other list.
    """
    if not HAS_TORCH or _MODEL is None:
        raise RuntimeError("Real ML model is not available.")
        
    num_drugs = len(drug_inputs)
    num_proteins = len(protein_inputs)
    max_len = max(num_drugs, num_proteins)
    
    # Replicate inputs if a single target/drug is provided for a batch
    if num_drugs == 1 and num_proteins > 1:
        drug_inputs = drug_inputs * max_len
    elif num_proteins == 1 and num_drugs > 1:
        protein_inputs = protein_inputs * max_len
    elif num_drugs != num_proteins:
        raise ValueError(f"Batch dimension mismatch: drugs={num_drugs}, proteins={num_proteins}")
        
    # 1. Resolve protein embeddings (either load from cache or compute via ESM-2)
    embeddings = []
    for seq in protein_inputs:
        emb = get_cached_embedding(seq)
        if emb is None:
            print(f"Protein sequence not in cache. Generating live ESM-2 embedding...")
            try:
                emb = get_esm2_embedding_unpooled(seq)
                save_embedding_to_cache(seq, emb)
            except Exception as e:
                raise ValueError(f"Failed to generate ESM-2 embedding for sequence: {e}")
        
        # Sanitize
        if torch.isnan(emb).any() or torch.isinf(emb).any():
            emb = torch.nan_to_num(emb, nan=0.0, posinf=0.0, neginf=0.0)
        embeddings.append(emb)
        
    # 2. Parse molecular graphs
    data_list = []
    for idx, smiles in enumerate(drug_inputs):
        graph = smiles_to_graph(smiles)
        if graph is None:
            raise ValueError(f"Invalid SMILES string provided at index {idx}.")
        x, edge_index, edge_attr = graph
        data = Data(x=x, edge_index=edge_index, edge_attr=edge_attr)
        data_list.append(data)
        
    # 3. Collate drug graphs into a single Batch
    pyg_batch = Batch.from_data_list(data_list).to(DEVICE)
    
    # 4. Collate protein embeddings into a single padded tensor
    max_protein_len = max(emb.size(0) for emb in embeddings)
    padded_p = torch.zeros(max_len, max_protein_len, ESM_DIM).to(DEVICE)
    p_mask = torch.zeros(max_len, max_protein_len).to(DEVICE)
    
    for idx, emb in enumerate(embeddings):
        curr_len = emb.size(0)
        padded_p[idx, :curr_len, :] = emb.to(DEVICE)
        p_mask[idx, :curr_len] = 1.0
        
    # 5. Execute model in a single forward pass
    with torch.no_grad():
        pred_pkd, pred_class = _MODEL(pyg_batch, padded_p, p_mask)
        # Convert output to CPU
        pred_pkd = pred_pkd.cpu().numpy()
        confidence = torch.sigmoid(pred_class).cpu().numpy()
        
    # 6. Format results
    results = []
    for idx in range(max_len):
        pkd = float(pred_pkd[idx])
        conf = float(confidence[idx])
        try:
            affinity = float(10 ** (9.0 - pkd))
        except OverflowError:
            affinity = float('inf')
            
        results.append({
            "affinity": round(affinity, 3) if affinity != float('inf') else 9999.999,
            "log_affinity": round(pkd, 3),
            "confidence": round(conf, 4),
            "model_name": "AdvancedDTIModel (TransformerConv+CrossAttentionFusion)",
            "metadata": MODEL_METADATA
        })
        
    # Trigger memory cleanup
    gc.collect()
    if DEVICE.type == "cuda":
        torch.cuda.empty_cache()
        
    return results