#%%
# ============================================================
# Baseline GraphDTA-style drug-target model
# ============================================================

# ===============================
# Imports
# ===============================
from unittest import TestLoader
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pandas as pd

from pathlib import Path
from rdkit import Chem
from rdkit.Chem.rdchem import ValenceType

from torch.utils.data import Dataset
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader
from torch_geometric.nn import GCNConv, global_mean_pool

from sklearn.model_selection import train_test_split
from scipy.stats import pearsonr

# ===============================
# Device
# ===============================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ============================================================
# Load dataset and protein embeddings
# ============================================================
BASE_DIR = Path(__file__).resolve().parent

df = pd.read_csv(BASE_DIR / "bindingdb_clean.tsv", sep="\t")

# Precomputed, frozen ProtBERT embeddings
protein_cache = torch.load(BASE_DIR / "protein_embeddings.pt")

print("Dataset size:", len(df))
print("Protein embedding dim:",
      next(iter(protein_cache.values())).shape)

# ============================================================
# Load cached protein embeddings from disk
# ============================================================
protein_cache = torch.load(
    BASE_DIR / "protein_embeddings.pt",
    map_location="cpu"
)

print("Protein embedding dim:",
      next(iter(protein_cache.values())).shape)


# ============================================================
# Convert SMILES strings to graph data
# ============================================================
def atom_features(atom):
    return [
        atom.GetAtomicNum(),
        atom.GetDegree(),
        atom.GetFormalCharge(),
        atom.GetHybridization().real,
        atom.GetIsAromatic(),
        atom.GetTotalNumHs(),
        atom.GetValence(ValenceType.IMPLICIT),
    ]


def smiles_to_graph(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("Invalid SMILES")

    x = torch.tensor(
        [atom_features(a) for a in mol.GetAtoms()],
        dtype=torch.float
    )

    edges = []
    for bond in mol.GetBonds():
        i, j = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        edges.append([i, j])
        edges.append([j, i])

    edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
    return x, edge_index

# ============================================================
# Dataset wrapper for graph samples
# ============================================================
class BindingDBDataset(Dataset):
    def __init__(self, df, protein_cache):
        self.df = df.reset_index(drop=True)
        self.cache = protein_cache

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]

        x, edge_index = smiles_to_graph(row["drug_smiles"])
        protein = self.cache[row["protein_sequence"]].unsqueeze(0)

        return Data(
            x=x,
            edge_index=edge_index,
            protein=protein,                     # [1,1024]
            y=torch.tensor(row["log_affinity"], dtype=torch.float),
        )

# ============================================================
# Drug graph encoder network
# ============================================================
class DrugGNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = GCNConv(7, 128)
        self.conv2 = GCNConv(128, 256)
        self.conv3 = GCNConv(256, 256)

    def forward(self, x, edge_index, batch):
        x = F.relu(self.conv1(x, edge_index))
        x = F.relu(self.conv2(x, edge_index))
        x = self.conv3(x, edge_index)
        return global_mean_pool(x, batch)   # [B,256]

# ============================================================
# Baseline model architecture
# ============================================================
class GraphDTABaselineV2(nn.Module):
    def __init__(self):
        super().__init__()

        self.drug_encoder = DrugGNN()

        # Frozen ProtBERT projection
        self.protein_fc = nn.Linear(1024, 256)

        # Regularized regression head
        self.regressor = nn.Sequential(
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 1),
        )

    def forward(self, batch):
        drug_emb = self.drug_encoder(
            batch.x,
            batch.edge_index,
            batch.batch
        )

        protein_emb = self.protein_fc(batch.protein)

        fused = torch.cat([drug_emb, protein_emb], dim=1)
        return self.regressor(fused).squeeze(-1)

# ============================================================
# Protein-level split to avoid leakage
# ============================================================
unique_proteins = df["protein_sequence"].unique()

train_proteins, val_proteins = train_test_split(
    unique_proteins,
    test_size=0.2,
    random_state=42
)

train_df = df[df["protein_sequence"].isin(train_proteins)].copy()
val_df   = df[df["protein_sequence"].isin(val_proteins)].copy()

assert set(train_df["protein_sequence"]).isdisjoint(
    set(val_df["protein_sequence"])
)

# ============================================================
# Standardize targets using training statistics
# ============================================================
mean = train_df["log_affinity"].mean()
std  = train_df["log_affinity"].std()

train_df["log_affinity"] = (train_df["log_affinity"] - mean) / std
val_df["log_affinity"]   = (val_df["log_affinity"] - mean) / std

# ============================================================
# DataLoader construction
# ============================================================
train_dataset = BindingDBDataset(train_df, protein_cache)
val_dataset   = BindingDBDataset(val_df, protein_cache)

train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
val_loader   = DataLoader(val_dataset, batch_size=32, shuffle=False)

# ============================================================
# Training and evaluation routines
# ============================================================
def train_epoch(model, loader, optimizer):
    model.train()
    total_loss, n = 0.0, 0

    for batch in loader:
        batch = batch.to(device)

        optimizer.zero_grad()
        preds = model(batch)
        loss = F.mse_loss(preds, batch.y)

        loss.backward()
        optimizer.step()

        total_loss += loss.item() * batch.num_graphs
        n += batch.num_graphs

    return total_loss / n


def eval_epoch(model, loader):
    model.eval()
    preds_all, targets_all = [], []

    with torch.no_grad():
        for batch in loader:
            batch = batch.to(device)
            preds = model(batch)

            preds_all.append(preds.cpu())
            targets_all.append(batch.y.cpu())

    preds_all = torch.cat(preds_all).numpy()
    targets_all = torch.cat(targets_all).numpy()

    rmse = np.sqrt(((preds_all - targets_all) ** 2).mean())
    pearson = pearsonr(preds_all, targets_all)[0]

    return rmse, pearson

# ============================================================
# Main training loop
# ============================================================
model = GraphDTABaselineV2().to(device)

optimizer = torch.optim.Adam(
    model.parameters(),
    lr=3e-4,
    weight_decay=1e-5
)

scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer,
    mode="max",
    factor=0.5,
    patience=5
)

best_pearson = -1.0

for epoch in range(1, 101):
    train_mse = train_epoch(model, train_loader, optimizer)
    val_rmse, val_p = eval_epoch(model, val_loader)

    scheduler.step(val_p)

    print(
        f"Epoch {epoch:03d} | "
        f"Train MSE: {train_mse:.4f} | "
        f"Val RMSE: {val_rmse:.4f} | "
        f"Val Pearson: {val_p:.4f}"
    )

    if val_p > best_pearson:
        best_pearson = val_p
        torch.save(model.state_dict(), "baseline_v2.pt")
        print(f"Saved best Baseline v2 (Pearson = {best_pearson:.4f})")


# %%
