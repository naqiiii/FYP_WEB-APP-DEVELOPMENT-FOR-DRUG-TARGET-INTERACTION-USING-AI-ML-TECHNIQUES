<div align="center">

<!-- HERO -->
<img src="assets/dti-banner.gif" width="100%" alt="Drug Target Interaction AI"/>

<br/>

# 🧬 Drug–Target Interaction Prediction

### Graph Neural Networks meet Protein Language Models

Predict drug–protein binding affinity using molecular graph learning,
protein embeddings, and cross-attention fusion.

<br/>

<p>
<img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white"/>
<img src="https://img.shields.io/badge/PyTorch_Geometric-3C3C3C?style=for-the-badge"/>
<img src="https://img.shields.io/badge/ESM--2-6C63FF?style=for-the-badge"/>
<img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
<img src="https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=next.js&logoColor=white"/>
<img src="https://img.shields.io/badge/MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white"/>
</p>

<br/>

**Drug SMILES + Protein FASTA → AI-Powered Binding Prediction**

<br/>

<sub>Final Year Project · BS Computer & Information Science · PIEAS</sub>

</div>

---

## ⚡ Overview

Early-stage drug discovery requires screening thousands of potential
molecules against biological targets. Traditional molecular docking
can be computationally expensive, particularly when screening at scale.

This platform uses a hybrid deep learning architecture combining
**Graph Transformers** and **ESM-2 protein embeddings** to predict
drug–target interactions directly from molecular structures and
protein sequences.

The model combines molecular graph learning, protein language
model representations, and cross-attention fusion to estimate
binding affinity and interaction probability.

<br/>

<div align="center">

| 🧪 Binding Affinity | ⚛️ Kd | 🎯 Confidence |
|:---:|:---:|:---:|
| Predicted pKd | Nanomolar | Interaction probability |

</div>

---

## 🚀 Application Preview

<!-- Replace these images with actual screenshots -->

<div align="center">

<img src="assets/dashboard.png" width="95%" alt="DTI Dashboard"/>

<br/><br/>

<img src="assets/prediction-result.png" width="95%" alt="Prediction Results"/>

<br/><br/>

<img src="assets/molecular-viewer.png" width="95%" alt="3D Molecular Viewer"/>

</div>

---

## 🧠 How It Works

<div align="center">

```mermaid
flowchart TD

    A["💊 Drug SMILES"] --> B["RDKit Molecular Graph"]
    B --> C["Graph Transformer"]

    D["🧬 Protein FASTA"] --> E["ESM-2 650M"]
    E --> F["Protein Residue Embeddings"]

    C --> G["Cross-Attention Fusion"]
    F --> G

    G --> H["Gated Fusion"]

    H --> I["pKd Regression"]
    H --> J["Interaction Classification"]

    I --> K["Binding Affinity"]
    K --> L["Kd in nM"]

    J --> M["Interaction Confidence"]

    class A,D fill:#172554,stroke:#60A5FA,color:#fff
    class B,C,E,F fill:#1E293B,stroke:#64748B,color:#fff
    class G,H fill:#312E81,stroke:#A78BFA,color:#fff
    class I,J,K,L,M fill:#064E3B,stroke:#34D399,color:#fff
