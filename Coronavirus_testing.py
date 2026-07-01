import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import torch
import torch.nn as nn
import torch.nn.functional as F
import pandas as pd
import numpy as np
from pathlib import Path
from rdkit import Chem
from rdkit import RDLogger
from rdkit.Chem import AllChem
from transformers import AutoTokenizer, EsmModel
from torch_geometric.data import Data, Batch
from torch_geometric.nn import TransformerConv

RDLogger.DisableLog("rdApp.*")

# ============================================================
# Parameters and directory setup
# ============================================================
ESM_NAME = "facebook/esm2_t33_650M_UR50D"
ESM_DIM  = 1280
DEVICE   = torch.device("cuda" if torch.cuda.is_available() else "cpu")
BASE_DIR = Path(__file__).resolve().parent

# ============================================================
# RDKit molecule-to-graph conversion utilities
# ============================================================
BOND_TYPES = {
    Chem.rdchem.BondType.SINGLE:   [1, 0, 0, 0],
    Chem.rdchem.BondType.DOUBLE:   [0, 1, 0, 0],
    Chem.rdchem.BondType.TRIPLE:   [0, 0, 1, 0],
    Chem.rdchem.BondType.AROMATIC: [0, 0, 0, 1],
}

def get_atom_features(atom):
    def one_h(val, choices): return [1 if val == c else 0 for c in choices]
    f  = one_h(atom.GetSymbol(), ['C','N','O','S','F','Si','P','Cl','Br','Mg','Na','Ca','Fe','I','B','Zn','other'])
    f += one_h(atom.GetDegree(),          [0,1,2,3,4,5,6])
    f += one_h(atom.GetTotalNumHs(),      [0,1,2,3,4,5])
    f += one_h(atom.GetImplicitValence(), [0,1,2,3,4,5])
    f += [int(atom.GetIsAromatic()), int(atom.IsInRing())]
    return np.array(f, dtype=np.float32)

def smiles_to_graph(smiles):
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
    if x.size(1) != 41:
        x = torch.cat([x, torch.zeros((x.size(0), 41 - x.size(1)))], dim=1) if x.size(1) < 41 else x[:, :41]

    edges, edge_attrs = [], []
    for bond in mol.GetBonds():
        i, j = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        attr = BOND_TYPES.get(bond.GetBondType(), [0, 0, 0, 0]) + [int(bond.IsInRing()), int(bond.GetIsConjugated())]
        edges += [[i, j], [j, i]]; edge_attrs += [attr, attr]

    edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous() if edges else torch.zeros((2, 1), dtype=torch.long)
    edge_attr  = torch.tensor(edge_attrs, dtype=torch.float) if edges else torch.zeros((1, 6), dtype=torch.float)
    return x, edge_index, edge_attr

# ============================================================
# Model architecture configuration
# ============================================================
class AdvancedDrugEncoder(nn.Module):
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
    def __init__(self):
        super().__init__()
        self.proj_protein = nn.Sequential(nn.Linear(ESM_DIM, 256), nn.LayerNorm(256), nn.SiLU())
        self.cross_attention = nn.MultiheadAttention(embed_dim=256, num_heads=8, dropout=0.15, batch_first=True)
        
        self.ln_drug = nn.LayerNorm(256)
        self.ln_prot = nn.LayerNorm(256)
        
        self.gate = nn.Sequential(nn.Linear(512, 256), nn.LayerNorm(256), nn.Sigmoid())
        self.out_proj = nn.Linear(512, 256)

    def forward(self, atom_feats, batch_indices, padded_protein, protein_mask):
        num_graphs = padded_protein.size(0)
        proj_p = self.proj_protein(padded_protein) 
        graph_sizes = torch.bincount(batch_indices, minlength=num_graphs)
        max_atoms = torch.max(graph_sizes).item()
        
        padded_atoms = torch.zeros(num_graphs, max_atoms, 256, device=atom_feats.device)
        atom_mask = torch.zeros(num_graphs, max_atoms, device=atom_feats.device)
        
        accum_index = 0
        for idx, size in enumerate(graph_sizes):
            if size > 0:
                padded_atoms[idx, :size, :] = atom_feats[accum_index : accum_index + size]
                atom_mask[idx, :size] = 1.0; accum_index += size
                
        attn_out, _ = self.cross_attention(query=padded_atoms, key=proj_p, value=proj_p, key_padding_mask=(protein_mask == 0))
        
        attn_out = self.ln_drug(attn_out)
        proj_p = self.ln_prot(proj_p)
        
        p_drug = (attn_out * atom_mask.unsqueeze(-1)).sum(dim=1) / atom_mask.unsqueeze(-1).sum(dim=1).clamp(min=1.0)
        p_prot = (proj_p * protein_mask.unsqueeze(-1)).sum(dim=1) / protein_mask.unsqueeze(-1).sum(dim=1).clamp(min=1.0)
        
        combined = torch.cat([p_drug, p_prot], dim=-1)
        return self.gate(combined) * self.out_proj(combined)

class AdvancedDTIModel(nn.Module):
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

# ============================================================
# Execution path for the use-case script
# ============================================================
def main():
    DRUG_NAME = "Nirmatrelvir (Paxlovid)"
    NIRMATRELVIR_SMILES = "CC1(C2C1C(N(C2)C(=O)C(C(C)(C)C)NC(=O)C(F)(F)F)C(=O)NC(CC3CCN(C3=O)C)C#N)C"
    
    PROTEIN_NAME = "SARS-CoV-2 Main Protease (Mpro)"
    M_PRO_SEQUENCE = "SGFRKMAFPSGKVEGCMVQVTCGTTTLNGLWLDDVVYCPRHVICTSEDMLNPNYEDLLIRKSNHNFLVQAGNVQLRVIGHSMQNCVLKLKVDTANPKTPKYKFVRIQPGQTFSVLACYNGS"
    
    REAL_PKD = 7.74

    cache_path = BASE_DIR / "esm2_unpooled_cache.pt"
    cache = torch.load(cache_path, map_location="cpu", weights_only=True) if cache_path.exists() else {}

    if M_PRO_SEQUENCE not in cache:
        print("Processing SARS-CoV-2 sequence with ESM-2...")
        tok = AutoTokenizer.from_pretrained(ESM_NAME)
        esm = EsmModel.from_pretrained(ESM_NAME).to(DEVICE)
        with torch.no_grad():
            t = tok(M_PRO_SEQUENCE, return_tensors="pt", max_length=1022, truncation=True).to(DEVICE)
            emb = esm(**t).last_hidden_state[0, 1:int(t.attention_mask[0].sum().item())-1, :].cpu()
            cache[M_PRO_SEQUENCE] = emb
        torch.save(cache, cache_path)

    print("\nInitializing AdvancedDTIModel structure...")
    model = AdvancedDTIModel().to(DEVICE)
    model.load_state_dict(torch.load(BASE_DIR / "best_production_dti_weights.pt", map_location=DEVICE, weights_only=True))
    model.eval()

    graph_data = smiles_to_graph(NIRMATRELVIR_SMILES)
    if graph_data is None:
        print("[Critical Error] Graph compilation failed.")
        return

    x, edge_index, edge_attr = graph_data
    pyg_data = Data(x=x, edge_index=edge_index, edge_attr=edge_attr)
    pyg_batch = Batch.from_data_list([pyg_data]).to(DEVICE)
    
    p_emb = cache[M_PRO_SEQUENCE].to(DEVICE)
    padded_p = p_emb.unsqueeze(0)
    p_mask = torch.ones(1, p_emb.size(0)).to(DEVICE)

    with torch.no_grad():
        pred, _ = model(pyg_batch, padded_p, p_mask)
    pred_val = pred.cpu().item()

    results_df = pd.DataFrame({
        "Drug Compound": [DRUG_NAME],
        "Viral Target System": [PROTEIN_NAME],
        "Experimental_pKd": [REAL_PKD],
        "Model_Predicted_pKd": [pred_val]
    })
    results_df["Absolute_Error"] = abs(results_df["Model_Predicted_pKd"] - results_df["Experimental_pKd"])

    print("\n" + "="*95)
    print(" Viral target benchmark report")
    print("="*95)
    print(results_df.to_string(index=False, formatters={
        "Experimental_pKd": "{:.2f}".format,
        "Model_Predicted_pKd": "{:.2f}".format,
        "Absolute_Error": "{:.2f}".format
    }))
    print("="*95)

if __name__ == "__main__":
    main()