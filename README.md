# Web App development for DTI using AI/ML techniques
> **Final Year Project (FYP): High-Performance Drug-Target Interaction Prediction Web Application**

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-black?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-%23EE4C2C.svg?style=for-the-badge&logo=PyTorch&logoColor=white)](https://pytorch.org/)
[![PyTorch Geometric](https://img.shields.io/badge/PyG-%233C2179.svg?style=for-the-badge&logoColor=white)](https://pytorch-geometric.readthedocs.io/)
[![MongoDB](https://img.shields.io/badge/MongoDB-%234ea94b.svg?style=for-the-badge&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![TailwindCSS](https://img.shields.io/badge/tailwindcss-%2338B2AC.svg?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)

An end-to-end, high-performance web application designed to predict **Drug-Target Interactions (DTI)** using state-of-the-art Deep Learning models. The system integrates a **Graph Neural Network (GNN)** with **ESM-2 (Evolutionary Scale Modeling)** protein language models to predict binding affinities and interaction confidence between drug molecules and target proteins.

---

## Table of Contents
1. [Project Overview](#-project-overview)
2. [Machine Learning Pipeline](#-machine-learning-pipeline)
   - [Drug Featurization & Graph Transformer](#1-drug-featurization--graph-transformer)
   - [Protein Embedding (ESM-2)](#2-protein-embedding-esm-2)
   - [Cross-Attention Fusion Engine](#3-cross-attention-fusion-engine)
   - [Multi-Task Prediction Heads](#4-multi-task-prediction-heads)
3. [System Architecture](#-system-architecture)
4. [High-Performance Optimizations](#-high-performance-optimizations)
5. [Repository Structure](#-repository-structure)
6. [Local Installation & Setup](#-local-installation--setup)
7. [API Contract & Schema](#-api-contract--schema)
8. [Database Schema](#-database-schema)
9. [Verification & Testing](#-verification--testing)
10. [GitHub Security Best Practices](#-github-security-best-practices)

---

## Project Overview

Identifying Drug-Target Interactions (DTI) is a crucial step in early-stage computer-aided drug discovery. Classic computational methods (like molecular docking) are computationally heavy and scale poorly for high-throughput screening. This application implements a hybrid deep-learning architecture that takes a **Drug SMILES** string and a **Protein FASTA** sequence and outputs:
1.  **$pK_d$ Binding Affinity**: The predicted log dissociation constant ($pK_d = -\log_{10}(K_d)$).
2.  **Dissociation Constant ($K_d$ in nM)**: Quantified binding affinity in nanomolar units.
3.  **Interaction Probability (Confidence)**: The probability that an interaction occurs.

---

##  Machine Learning Pipeline

The machine learning model (`AdvancedDTIModel`) utilizes a late-fusion design that combines a graph-based drug representation and a language-based protein representation.

```
       [Drug SMILES]                                [Protein FASTA]
            │                                              │
     (RDKit Parsing)                              (ESM-2 650M Model)
            │                                              │
    [Molecular Graph]                          [Residue Embeddings (L × 1280)]
            │                                              │
 (GNN Graph Transformer)                            (Linear Projection)
            │                                              │
 [Atom Embeddings (N × 256)]                    [Protein Context (L × 256)]
            └───────────────────────┬──────────────────────┘
                                    │
                       (Multi-Head Cross-Attention)
                                    │
                         (Gated Fusion Pooling)
                                    │
                         [Fused Context (256)]
                                    ├──> [Regressor Head] ──> pKd (Binding Affinity)
                                    └──> [Classifier Head] ──> Interaction Probability
```

### 1. Drug Featurization & Graph Transformer
Molecules are parsed using RDKit into a graph $G=(V,E)$ where atoms are nodes and bonds are edges.
*   **Atom Node Features (41 dimensions)**: Includes atomic symbol one-hot vectors, atom degree, total hydrogens, implicit valence, aromaticity, ring membership, and **Gasteiger partial charge** (for electrostatic modeling).
*   **Bond Edge Features (6 dimensions)**: One-hot representation of bond type (Single, Double, Triple, Aromatic), ring membership, and conjugation.
*   **AdvancedDrugEncoder**: A 3-layer Graph Transformer network that uses PyTorch Geometric's `TransformerConv` layers. It computes multi-head self-attention over neighboring atoms to learn representations that incorporate local chemical environments.

### 2. Protein Embedding (ESM-2)
*   **ESM-2 Model**: The model uses `facebook/esm2_t33_650M_UR50D`, a **650 Million parameter** transformer pre-trained on evolutionary sequences.
*   For each amino acid sequence, it extracts a representation of shape `(Sequence_Length, 1280)`.
*   Special tokens `[CLS]` and `[EOS]` are removed to preserve only actual residue positions.

### 3. Cross-Attention Fusion Engine
Rather than simple concatenation, the model uses an attention mechanism to model binding pockets:
*   The 1280-dimensional protein embeddings are projected to 256 dimensions.
*   **Cross-Attention**: Drug atom features query ($Q$) the protein residue embeddings ($K$ & $V$). This allows the model to match drug functional groups to candidate binding residues.
*   **Gating Mechanism**: A neural gate controls the flow of drug and protein contexts into the final representation.

### 4. Multi-Task Prediction Heads
*   **Regression Head**: Projects the fused representation to predict $pK_d$. The system automatically translates this to nanomolar units:
    $$K_d(\text{nM}) = 10^{(9 - pK_d)}$$
*   **Classifier Head**: Predicts binary interaction classification. The probability score represents the interaction confidence.

---

##  System Architecture

*   **Next.js 14 Web UI**: Built with React hooks, featuring interactive 3D visualizations for proteins (via AlphaFold/PDB structure loaders) and ligands (via PubChem structural models).
*   **FastAPI Backend**: Asynchronous endpoint routing using Python's `asyncio` event loop. Pushes PyTorch model runs to a worker threadpool using `run_in_threadpool()` to prevent event-loop blocking.
*   **FastAPI Docking Microservice**: A secondary service wrapper that handles 3D docking calculations (such as AutoDock Vina or GNINA workflows), keeping heavy structural modeling isolated from user-facing API routes.
*   **MongoDB Atlas Cloud Database**: Logs user details (JWT authentication) and logs prediction query history alongside calculated Lipinski molecular properties.

---

##  High-Performance Optimizations

1.  **Protein Cache (`esm2_cache/`)**: ESM-2 embedding generation can be computationally slow. The backend computes the MD5 hash of input sequences and saves generated embeddings as individual `.pt` files. Future requests on cached sequences return results in **sub-millisecond** times.
2.  **Parallel Batch Inference**: Batch prediction routes bundle individual drug graphs into a unified `torch_geometric.data.Batch` object and pad protein tensors. The model executes the entire batch in a single forward pass on the GPU.
3.  **VRAM Management**: Triggers Python garbage collection (`gc.collect()`) and PyTorch CUDA cache flushing (`torch.cuda.empty_cache()`) post-inference to prevent memory accumulation.

---

##  Repository Structure

```directory
DTI_webapp/
├── .gitignore                         # Local caches, dependencies, and credential ignore rules
├── README.md                          # Comprehensive project guide (this file)
└── dti-prediction-app/
    ├── backend/                       # FastAPI Server and PyTorch DL model
    │   ├── app/                       
    │   │   ├── drug_target_prediction/ # GNN models, preprocessing, translation services
    │   │   ├── user_authentication/   # JWT verification, register/login logic
    │   │   ├── prediction_history/    # History query controllers
    │   │   ├── visualization/         # 3D loaders (UniProt, AlphaFold, PDB, ESMFold API)
    │   │   ├── mongodb_connection.py  # Async Mongo Atlas integration
    │   │   └── server.py              # Root FastAPI application router
    │   ├── best_production_dti_weights.pt # Production Graph Transformer weights
    │   ├── requirements.txt           # Python backend dependencies
    │   └── .env.example               # Template environment settings
    ├── frontend/                      # Next.js UI web interface
    │   ├── src/                       
    │   │   ├── components/            # UI components (3D viewers, gauges, charts)
    │   │   └── pages/                 # Routing pages (Authentication, Screeners, History)
    │   ├── package.json               # Next.js configurations
    │   └── tailwind.config.js         # CSS theme parameters
    ├── docking/                       # Docking engine API wrapper
    │   ├── app/main.py                # Main docking routes (Mock/Real AutoDock Vina)
    │   └── requirements.txt           # Docking dependencies
    ├── fyp_info_files/                # Academic documents
    │   └── FYP_REPORT.docx            # Complete FYP Thesis
    └── testing_samples/               # SMILES and FASTA sample files for validation
```

---

##  Local Installation & Setup

### 1. Set Up Environment Variables
Copy template settings files to active configurations:
*   **Backend**: Navigate to `dti-prediction-app/backend/`. Copy `.env.example` to `.env` and fill in your database, secret key, and email settings.
*   **Docking**: Navigate to `dti-prediction-app/docking/`. Copy `.env.example` to `.env`.
*   **Frontend**: Navigate to `dti-prediction-app/frontend/`. Create a `.env.local` containing:
    ```env
    NEXT_PUBLIC_API_URL=http://localhost:8000
    ```

### 2. Run the Backend Server
1. Navigate to the backend directory:
   ```bash
   cd dti-prediction-app/backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the server:
   ```bash
   uvicorn app.server:app --host 127.0.0.1 --port 8000 --reload
   ```
   *   **API Root URL**: `http://localhost:8000`
   *   **Swagger Docs**: `http://localhost:8000/docs`

### 3. Run the Frontend Client
1. Navigate to the frontend directory:
   ```bash
   cd dti-prediction-app/frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the Next.js development client:
   ```bash
   npm run dev
   ```
   *   **App UI URL**: `http://localhost:3000`

---

## 🔌 API Contract & Schema

### `POST /api/predict`
Calculates interaction variables for a single drug-target pair.

*   **Request Body**:
    ```json
    {
      "smiles": "CC(=O)NC1=CC=C(O)C=C1",
      "drug_name": "Paracetamol",
      "sequence": "MNGTEGPNFYVPFSNKTGVVRSPFEAPQYYLAEPWQFML...",
      "protein_name": "Rhodopsin",
      "min_affinity_checkpoint": 6.0
    }
    ```
*   **Response Body**:
    ```json
    {
      "affinity": 32.551,
      "log_affinity": 7.487,
      "confidence": 0.9412,
      "model_name": "AdvancedDTIModel (TransformerConv+CrossAttentionFusion)",
      "drug_smiles": "CC(=O)NC1=CC=C(O)C=C1",
      "protein_sequence": "MNGTEGPNFYVPFSNKTGVVRSPFEAPQYYLAEPWQFML...",
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
    ```

---

##  Database Schema

The logs collected inside the MongoDB collection `prediction_history` use the following schema structure:

```json
{
  "_id": "ObjectId",
  "user_id": "string (JWT sub token)",
  "drug_smiles": "string",
  "protein_sequence": "string",
  "drug_label": "string",
  "protein_label": "string",
  "affinity": "double",
  "log_affinity": "double",
  "confidence": "double",
  "model_name": "string",
  "created_at": "ISODate",
  "drug_likeness": {
    "molecular_weight": "double",
    "logp": "double",
    "h_bond_donors": "int",
    "h_bond_acceptors": "int",
    "rotatable_bonds": "int",
    "tpsa": "double",
    "lipinski_violations": "int",
    "passes_lipinski": "boolean"
  },
  "protein_info": {
    "length": "int",
    "molecular_weight": "double",
    "aromaticity": "double",
    "instability_index": "double",
    "isoelectric_point": "double",
    "gravy": "double"
  }
}
```

---

##  Verification & Testing

To confirm correct system setup:
1.  **Register a Test Account**: Visit `http://localhost:3000/register`.
2.  **Verify Backend Connections**: Ensure that your backend terminal displays:
    `Connecting to MongoDB... Connected successfully!`
    `Starting up DTI Prediction API... Preloading ESM-2... API is ready!`
3.  **Run a Test Prediction**: Use these structures from `testing_samples/`:
    *   **Drug SMILES**: `CC(=O)NC1=CC=C(O)C=C1` (Paracetamol)
    *   **Protein FASTA**: `MNGTEGPNFYVPFSNKTGVVRSPFEAPQYYLAEPWQFMLAAYMFLLIVLGFPINFLTLYVTVQHKKLRTPLNYILLNLAVADLFMVFGGFTTTLYTSLHGYFVFGPTGCNLEGFFATLGGEIALWSLVVLAIERWVVVCKPMSNFRFGENHAIMGVAFTWVMALACAAPPLVGWSRYIPEGMQCSCGIDYYTPHEETNNESFVIYMFVVHFIIPLIVIFFCYGQLVFTVKEAAAQQQESATTQKAEKEVTRMVIIMVIAFLICWLPYAGVAFYIFTHQGSDFGPIFMTIPAFFAKTSAVYNPVIYIMMNKQFRNCMVTTLCCGKNPLGDDEASTTVSKTETSQVAPA` (Rhodopsin)
4.  **Confirm Results**: A successful execution displays output values for $K_d$ and $pK_d$ along with 3D structural mappings.

---

##  GitHub Security Best Practices

1.  **Never Push Sensitive Keys**: The root `.gitignore` will automatically prevent pushing active configuration `.env` or `.env.local` files containing passwords.
2.  **Hashed ML Artifact Caching**: Do not remove the `**/esm2_cache/` rule in `.gitignore`. If deleted, git will attempt to stage gigabytes of cache tensors, which will cause push failures.
3.  **Hacking Prevention**: Ensure that your MongoDB Atlas instance uses IP Whitelisting (restricting connection access to specified deployment addresses only).
