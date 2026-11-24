<div align="center">

# Drug–Target Interaction Prediction Platform

### Graph Neural Networks × Protein Language Models

A deep learning platform for predicting drug–target binding affinity
using molecular graph learning, protein representations,
cross-attention and multi-task prediction.

<br/>

**Drug SMILES** → **Molecular Graph** → **AI Model** → **Binding Prediction**

<br/>

<sub>Final Year Project · BS Computer & Information Science · PIEAS</sub>

</div>

---

## Overview

Drug discovery involves identifying molecules capable of interacting with biological targets. Screening large numbers of drug candidates against proteins can require computationally intensive workflows, particularly when structural docking is involved.

This project explores a deep learning approach to drug–target interaction prediction by combining molecular graph learning with protein language model representations.

The platform accepts a drug molecule represented by a SMILES string and a protein represented by a FASTA sequence. Both inputs are processed through independent encoders, integrated through cross-attention and gated fusion, and passed to multi-task prediction heads.

The model predicts binding affinity and interaction probability, while the integrated web application provides molecular analysis, structure visualization, authentication and prediction history.

<div align="center">

**Molecular Structure + Protein Sequence**

↓

**Graph Transformer + ESM-2**

↓

**Cross-Attention & Gated Fusion**

↓

**Affinity & Interaction Prediction**

</div>

---

## What the Platform Provides

| Capability | Description |
|---|---|
| Molecular Representation | Converts drug SMILES into molecular graphs |
| Protein Representation | Generates contextual residue embeddings using ESM-2 |
| Interaction Modeling | Combines drug and protein representations through cross-attention |
| Binding Affinity | Predicts affinity in pKd |
| Kd Conversion | Converts affinity into nanomolar units |
| Interaction Classification | Predicts interaction probability |
| Drug-Likeness | Calculates molecular properties and Lipinski assessment |
| Protein Analysis | Calculates protein physicochemical properties |
| Structure Visualization | Visualizes drug and protein structures |
| Prediction History | Stores user-specific prediction records |
| Authentication | JWT-based authentication |
| Molecular Docking | Optional structural docking workflow |

---

# Model Architecture

The model combines two representation-learning branches, cross-attention fusion, a gated fusion mechanism and two prediction heads.

```text
                    DRUG–TARGET INPUTS

          Drug SMILES              Protein FASTA
               |                       |
               v                       v
             RDKit                   ESM-2
               |                    650M
               v                       |
       Molecular Graph                 v
               |               Residue Embeddings
               v                       |
      Graph Transformer                v
          3 Layers              Linear Projection
               |                       |
               v                       v
       Atom Embeddings          Protein Embeddings
           256-D                   256-D
               |                       |
               +----------+------------+
                          |
                          v
                 Cross-Attention Fusion
                          |
                          v
                   Gated Fusion
                    + Pooling
                          |
                          v
                Fused Representation
                          |
                +---------+---------+
                |                   |
                v                   v
         Regression Head     Classification Head
                |                   |
                v                   v
               pKd          Interaction Probability
                |
                v
              Kd (nM)
