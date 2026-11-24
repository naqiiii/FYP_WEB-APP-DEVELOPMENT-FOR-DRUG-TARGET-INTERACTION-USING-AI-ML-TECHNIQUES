<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=25&duration=3000&pause=1200&color=22D3EE&center=true&vCenter=true&width=900&lines=Drug%E2%80%93Target+Interaction+Prediction;Graph+Transformers+%2B+ESM-2;Cross-Attention+%2B+Multi-Task+Learning" alt="Animated title"/>

<br/>

# Drug–Target Interaction Prediction Platform

### A deep learning system for computational drug discovery

**Molecular Graph Learning · Protein Language Models · Cross-Attention**

<br/>

<a href="https://github.com/naqiiii">
<img src="https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"/>
</a>
<img src="https://img.shields.io/badge/PyTorch-Deep%20Learning-EE4C2C?style=flat-square&logo=pytorch&logoColor=white" alt="PyTorch"/>
<img src="https://img.shields.io/badge/PyTorch%20Geometric-GNN-3C3C3C?style=flat-square" alt="PyTorch Geometric"/>
<img src="https://img.shields.io/badge/ESM--2-Protein%20Language%20Model-6C63FF?style=flat-square" alt="ESM-2"/>
<img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
<img src="https://img.shields.io/badge/Next.js-Frontend-000000?style=flat-square&logo=next.js&logoColor=white" alt="Next.js"/>
<img src="https://img.shields.io/badge/MongoDB-Database-47A248?style=flat-square&logo=mongodb&logoColor=white" alt="MongoDB"/>

<br/><br/>

<sub>Final Year Project · BS Computer & Information Science · PIEAS</sub>

</div>

---

## Overview

Drug discovery involves identifying molecules capable of interacting with biological targets. Screening large numbers of drug candidates against proteins can require computationally intensive workflows, particularly when structural docking is involved.

This project explores a deep learning approach to drug–target interaction prediction by combining molecular graph learning with protein language model representations.

The platform accepts a drug molecule represented by a SMILES string and a protein represented by a FASTA sequence. The model processes both inputs through independent encoders, integrates their representations through cross-attention and gated fusion, and produces binding affinity and interaction probability predictions.

The trained model is integrated into a full-stack application that provides prediction access, molecular analysis, protein and ligand visualization, user authentication and prediction history.

<div align="center">

**SMILES + FASTA → Representation Learning → Cross-Attention → Prediction**

</div>

---

## What the System Does

| Capability | Description |
|---|---|
| Drug Representation | Converts SMILES into molecular graphs |
| Protein Representation | Extracts contextual residue embeddings using ESM-2 |
| Interaction Modeling | Combines drug and protein representations through cross-attention |
| Affinity Prediction | Predicts binding affinity as pKd |
| Kd Conversion | Converts predicted affinity into nanomolar units |
| Interaction Classification | Predicts interaction probability |
| Drug-Likeness Analysis | Calculates molecular properties and Lipinski assessment |
| Protein Analysis | Calculates protein-related physicochemical properties |
| Structure Visualization | Visualizes drug and protein structures |
| Prediction History | Stores predictions associated with authenticated users |
| Molecular Docking | Supports a separate docking workflow |

---

## Model Architecture

The model consists of two representation-learning branches, a cross-attention fusion mechanism, gated fusion and two prediction heads.

### Architecture Flow

```text
                          INPUTS
                 ┌────────────────────┐
                 │                    │
             Drug SMILES         Protein FASTA
                 │                    │
                 ▼                    ▼
              RDKit                 ESM-2
                 │                 650 Million
                 ▼                    │
         Molecular Graph              ▼
                 │             Residue Embeddings
                 ▼                    │
       Graph Transformer              ▼
           3 Layers             Linear Projection
                 │                    │
                 ▼                    ▼
        Atom Embeddings       Protein Embeddings
           256-D                  256-D
                 │                    │
                 └─────────┬──────────┘
                           │
                           ▼
                  Cross-Attention Fusion
                           │
                           ▼
                    Gated Fusion
                     + Pooling
                           │
                           ▼
                 Unified Representation
                           │
                 ┌─────────┴─────────┐
                 │                   │
                 ▼                   ▼
          Regression Head     Classification Head
                 │                   │
                 ▼                   ▼
                pKd           Interaction Probability
                 │
                 ▼
              Kd (nM)
