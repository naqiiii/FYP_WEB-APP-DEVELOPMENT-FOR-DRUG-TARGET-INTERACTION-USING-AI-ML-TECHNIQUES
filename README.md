<div align="center">
Drug–Target Interaction Prediction Platform

Graph Neural Networks meet protein language models, served through a production-style web app.

Paste a drug SMILES and a protein sequence. Get binding affinity, Kd and interaction confidence in seconds, with 3D structures alongside.

<br>

FastAPI Next.js PyTorch PyTorch Geometric MongoDB TailwindCSS

<sub>Final Year Project · BS Computer Science · PIEAS</sub>

</div>
What it does

Early-stage drug discovery needs a fast way to screen which molecules are likely to bind which proteins. Molecular docking is accurate but heavy, and it scales poorly when you want to screen at volume.

This platform takes a different route. A learned model predicts the interaction directly from a drug SMILES string and a protein FASTA sequence, and returns three things:

Output	Meaning
pKd	Predicted binding affinity, where pKd = −log₁₀(Kd)
Kd (nM)	The same affinity in nanomolar units
Confidence	Probability that the pair actually interacts

On top of the model sits a full web product: accounts, prediction history, drug-likeness analysis, interactive 3D viewers and an optional docking service.

Highlights
Hybrid deep learning model. A 3-layer Graph Transformer encodes the drug as a molecular graph, and the 650M-parameter ESM-2 encodes the protein.
Cross-attention fusion. Drug atoms attend over protein residues, so the model can relate functional groups to candidate binding regions instead of just concatenating two vectors.
Multi-task output. One forward pass gives a regression head (pKd) and a classification head (interaction probability).
Fast by design. Embedding cache, batched GPU inference and managed VRAM keep repeat queries near-instant.
Complete product. JWT auth, per-user history, Lipinski analysis and 3D structure viewers, not just a notebook.
Model architecture
Drug SMILES
RDKit parsing
Molecular graph41-dim atoms, 6-dim bonds
Graph Transformer3x TransformerConv
Atom embeddingsN x 256
Protein FASTA
ESM-2 650M
Residue embeddingsL x 1280
Linear projection
Protein contextL x 256
Multi-head cross-attentionatoms query residues
Gated fusion pooling
Fused context256
Regressor headpKd
Classifier headinteraction probability
Drug side

Molecules are parsed with RDKit into a graph where atoms are nodes and bonds are edges.

Atom features (41 dims): element one-hot, degree, total hydrogens, implicit valence, aromaticity, ring membership and Gasteiger partial charge for electrostatics.
Bond features (6 dims): bond type (single, double, triple, aromatic), ring membership and conjugation.
Encoder: AdvancedDrugEncoder, a 3-layer stack of PyTorch Geometric TransformerConv layers that applies multi-head attention over each atom's neighbours.
Protein side
Model: facebook/esm2_t33_650M_UR50D, pretrained on evolutionary sequence data.
Output: a (sequence_length, 1280) residue representation, with [CLS] and [EOS] tokens stripped so only real residues remain.
Fusion and prediction
Protein embeddings are projected from 1280 to 256 dimensions.
Drug atoms act as queries over protein residues (keys and values), then a learned gate controls how much drug and protein context flows into the final representation.
The regression head outputs pKd, which is converted to nanomolar:
$$K_d\,(\text{nM}) = 10^{\,9 - pK_d}$$
System architecture
REST
Next.js 14 UI3D viewers, charts, history
FastAPI backendasync + threadpoolinference
AdvancedDTIModelPyTorch + ESM-2
MongoDB Atlasusers, prediction history
Docking microserviceAutoDock Vina / GNINA
Structure sourcesAlphaFold, PDB, UniProt,ESMFold, PubChem
Layer	Role
Frontend	Next.js 14 with Tailwind. Interactive 3D protein (AlphaFold/PDB) and ligand (PubChem) viewers, affinity gauges and a history view.
Backend	FastAPI with async routing. Model runs are pushed to a worker threadpool with run_in_threadpool() so the event loop never blocks.
Docking service	A separate FastAPI service wrapping 3D docking workflows, kept apart so heavy structural jobs never slow down predictions.
Database	MongoDB Atlas stores JWT-authenticated users and every prediction alongside its calculated Lipinski properties.
Performance engineering
Optimization	What it does
Protein embedding cache	ESM-2 is the slow step. The backend hashes each sequence (MD5) and stores its embedding as a .pt file, so repeat sequences return in sub-millisecond time.
Batched GPU inference	Many drug graphs are merged into one torch_geometric.data.Batch and protein tensors are padded, so a whole batch runs in a single forward pass.
VRAM management	gc.collect() and torch.cuda.empty_cache() run after inference to stop memory from creeping up under load.
Quick start

1. Configure environment

bash
# backend and docking
cp dti-prediction-app/backend/.env.example dti-prediction-app/backend/.env
cp dti-prediction-app/docking/.env.example dti-prediction-app/docking/.env

# frontend
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > dti-prediction-app/frontend/.env.local

Fill in your database URI, secret key and email settings in the backend .env.

2. Run the backend

bash
cd dti-prediction-app/backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.server:app --host 127.0.0.1 --port 8000 --reload

API at http://localhost:8000, interactive docs at http://localhost:8000/docs.

3. Run the frontend

bash
cd dti-prediction-app/frontend
npm install
npm run dev

App at http://localhost:3000.

4. Try a prediction

Register an account, then use the samples in testing_samples/, for example Paracetamol (CC(=O)NC1=CC=C(O)C=C1) against Rhodopsin.

API
POST /api/predict

Predicts the interaction for a single drug–target pair.

<details> <summary><b>Request</b></summary>
json
{
  "smiles": "CC(=O)NC1=CC=C(O)C=C1",
  "drug_name": "Paracetamol",
  "sequence": "MNGTEGPNFYVPFSNKTGVVRSPFEAPQYYLAEPWQFML...",
  "protein_name": "Rhodopsin",
  "min_affinity_checkpoint": 6.0
}
</details> <details> <summary><b>Response</b></summary>
json
{
  "affinity": 32.551,
  "log_affinity": 7.487,
  "confidence": 0.9412,
  "model_name": "AdvancedDTIModel (TransformerConv+CrossAttentionFusion)",
  "drug_label": "Paracetamol",
  "protein_label": "Rhodopsin",
  "drug_likeness": {
    "molecular_weight": 151.16,
    "logp": 0.91,
    "lipinski_violations": 0,
    "passes_lipinski": true
  },
  "protein_info": {
    "length": 348,
    "molecular_weight": 38893.2,
    "isoelectric_point": 6.21
  }
}
</details>

Every prediction is also saved per user in the prediction_history collection, together with the full drug-likeness profile (H-bond donors and acceptors, rotatable bonds, TPSA) and protein properties (aromaticity, instability index, GRAVY).

Project layout
dti-prediction-app/
├── backend/      FastAPI server, GNN model, auth, history, 3D structure loaders
├── frontend/     Next.js interface: components, pages, Tailwind theme
├── docking/      Docking microservice
├── fyp_info_files/   Thesis report
└── testing_samples/  Sample SMILES and FASTA files
Notes for contributors
Never commit .env or .env.local. The root .gitignore already excludes them.
Keep the **/esm2_cache/ rule in .gitignore. Without it, git tries to stage gigabytes of cached tensors.
Restrict your MongoDB Atlas cluster to known IP addresses.
<div align="center">

Built by Syed Hassan Raza · GitHub · Portfolio

</div>
