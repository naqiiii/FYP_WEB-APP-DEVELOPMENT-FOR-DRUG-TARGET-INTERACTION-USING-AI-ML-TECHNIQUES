<div align="center">

# 🧬 Drug–Target Interaction Prediction

### An AI-powered platform for computational drug discovery

**Graph Transformers · ESM-2 · Cross-Attention · Multi-Task Learning**

<br/>

<p>
Drug Molecular Graphs
&nbsp; × &nbsp;
Protein Language Models
&nbsp; × &nbsp;
Interaction Modeling
</p>

<br/>

<sub>Final Year Project · BS Computer & Information Science · PIEAS</sub>

</div>

---

<div align="center">

### The idea

**A molecule is more than a string. A protein is more than a sequence.**

</div>

This project combines molecular graph learning and pretrained protein language models to predict drug–target interactions.

Given a drug SMILES string and a protein FASTA sequence, the model learns representations from both inputs, integrates them through cross-attention and gated fusion, and produces binding affinity and interaction probability predictions.

The model is integrated into a full-stack platform featuring prediction workflows, molecular analysis, interactive structure visualization, authentication and prediction history.

---

# 01 · The Prediction Pipeline

<div align="center">

```text
    MOLECULE                         PROTEIN
       │                                 │
   SMILES STRING                    FASTA SEQUENCE
       │                                 │
       ▼                                 ▼
      RDKit                            ESM-2
       │                              650M
       ▼                                 │
 MOLECULAR GRAPH                        ▼
       │                         RESIDUE EMBEDDINGS
       ▼                                 │
 GRAPH TRANSFORMER                       ▼
       │                         LINEAR PROJECTION
       ▼                                 │
 ATOM EMBEDDINGS                         ▼
       │                                 │
       └───────────────┬─────────────────┘
                       │
                       ▼
              CROSS-ATTENTION
                       │
                       ▼
                GATED FUSION
                 + POOLING
                       │
                       ▼
              FUSED REPRESENTATION
                       │
              ┌────────┴────────┐
              ▼                 ▼
         REGRESSION       CLASSIFICATION
              │                 │
              ▼                 ▼
             pKd          INTERACTION
              │            PROBABILITY
              ▼
             Kd
