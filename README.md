<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=28&duration=3000&pause=1200&color=22D3EE&center=true&vCenter=true&width=850&lines=Drug%E2%80%93Target+Interaction+Prediction;Graph+Transformers+%2B+Protein+Language+Models;AI+for+Computational+Drug+Discovery" alt="Animated project title"/>

<br/>

<h1>Drug–Target Interaction Prediction</h1>

<p>
<b>Predicting molecular binding affinity through graph learning and protein language models.</b>
</p>

<p>
Drug Molecular Graphs &nbsp;×&nbsp; Protein Sequence Embeddings &nbsp;×&nbsp; Cross-Attention
</p>

<br/>

<img src="https://img.shields.io/badge/PyTorch-Deep_Learning-EE4C2C?style=flat-square&logo=pytorch&logoColor=white"/>
<img src="https://img.shields.io/badge/PyTorch_Geometric-Graph_Learning-3C3C3C?style=flat-square"/>
<img src="https://img.shields.io/badge/ESM--2-Protein_Language_Model-6C63FF?style=flat-square"/>
<img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi&logoColor=white"/>
<img src="https://img.shields.io/badge/Next.js-Frontend-000000?style=flat-square&logo=next.js&logoColor=white"/>
<img src="https://img.shields.io/badge/MongoDB-Database-47A248?style=flat-square&logo=mongodb&logoColor=white"/>

<br/><br/>

<sub>Final Year Project · BS Computer & Information Science · PIEAS</sub>

</div>

---

<div align="center">

### From molecular structure to predicted interaction

</div>

A deep learning platform for predicting drug–target interaction affinity using molecular graphs, protein sequence representations and cross-attention fusion.

The system combines a Graph Transformer-based drug encoder with ESM-2 protein embeddings to model drug–protein relationships and produce binding affinity and interaction probability predictions.

---

## The Model

<div align="center">

```mermaid
flowchart TD
    A["Drug SMILES"] --> B["RDKit Molecular Graph"]
    B --> C["Graph Transformer"]

    D["Protein FASTA"] --> E["ESM-2 · 650M"]
    E --> F["Protein Residue Embeddings"]

    C --> G["Cross-Attention Fusion"]
    F --> G

    G --> H["Gated Fusion & Pooling"]

    H --> I["Affinity Regression"]
    H --> J["Interaction Classification"]

    I --> K["Predicted pKd"]
    K --> L["Kd · nM"]

    J --> M["Interaction Probability"]

    class A,D fill:#0f172a,stroke:#38bdf8,color:#ffffff
    class B,C,E,F fill:#1e293b,stroke:#64748b,color:#ffffff
    class G,H fill:#312e81,stroke:#a78bfa,color:#ffffff
    class I,J,K,L,M fill:#064e3b,stroke:#34d399,color:#ffffff
