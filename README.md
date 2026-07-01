# 🧬 DTI Prediction Web App
> **Final Year Project (FYP): Drug-Target Interaction Prediction Web Application**

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-black?style=for-the-badge&logo=next.design&logoColor=white)](https://nextjs.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-%23EE4C2C.svg?style=for-the-badge&logo=PyTorch&logoColor=white)](https://pytorch.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-%234ea94b.svg?style=for-the-badge&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![TailwindCSS](https://img.shields.io/badge/tailwindcss-%2338B2AC.svg?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)

An end-to-end, high-performance web application designed to predict **Drug-Target Interactions (DTI)** using state-of-the-art Deep Learning models. The system leverages **ESM-2 (Evolutionary Scale Modeling)** protein language models alongside PyTorch to predict binding affinities and interaction probabilities between drug molecules (represented as SMILES strings) and target proteins (represented as FASTA amino acid sequences).

---

## 🚀 Key Features

*   **Deep Learning Predictor**: Integrates pre-trained **ESM-2** embeddings and PyTorch models for robust, high-accuracy DTI affinity predictions.
*   **Modern Frontend UI**: Built on **Next.js 14**, featuring responsive layouts, custom interactive components, and premium styling via Tailwind CSS.
*   **Secure Backend API**: Developed using **FastAPI**, with built-in JWT-based authentication, rate limiting (SlowAPI), and global exception handling.
*   **Database Integration**: Relies on **MongoDB Atlas** (using the asynchronous `motor` driver) to persist user profiles, history, and prediction records.
*   **Prediction History & Tracking**: Allows users to manage past prediction queries, analyze results, and search historical runs.
*   **Visualizations**: Includes interactive visualization components to analyze drug structures and protein-target binding details.
*   **Modular Molecular Docking**: Features a docking engine (supporting AutoDock Vina integrations and mock mode) for structural verification.

---

## 📁 Repository Structure

```directory
DTI_webapp/
├── .gitignore                         # Configured rules to ignore dependencies, caches, and secrets
├── README.md                          # Main project documentation (this file)
└── dti-prediction-app/
    ├── backend/                       # FastAPI server logic & Machine Learning models
    │   ├── app/                       # Core python app modules (auth, predictions, visualization)
    │   ├── best_production_dti_weights.pt # Saved weights for the DTI prediction neural network
    │   ├── requirements.txt           # Python dependency specifications for the backend
    │   └── .env.example               # Template environment configurations
    ├── frontend/                      # Next.js web interface
    │   ├── src/                       # React components, pages, context, and styles
    │   ├── package.json               # Frontend dependencies and run scripts
    │   └── tailwind.config.js         # Custom UI theme guidelines and configurations
    ├── docking/                       # Modular AutoDock Vina molecular docking service
    │   ├── app/                       # Docking execution code
    │   ├── requirements.txt           # Docking python library dependencies
    │   └── .env.example               # Docking runtime configurations
    ├── fyp_info_files/                # Official documentation and FYP academic report files
    │   └── FYP_REPORT.docx            # Comprehensive FYP Thesis/Report
    └── testing_samples/               # Collection of sample proteins, SMILES strings, and CSVs
```

---

## 🛠️ System Requirements

Ensure you have the following installed on your machine:
*   **Python 3.10+** (Conda manager recommended)
*   **Node.js 18.x** or higher (with `npm` or `yarn`)
*   **MongoDB Atlas Account** (or a local MongoDB instance running on port `27017`)

---

## ⚙️ Local Installation & Setup

Follow these steps to run the complete DTI Prediction stack on your machine:

### 1. Configure Environment Variables
Both backend and frontend require configuration files to operate. Templates are provided as `.env.example` in their respective folders.

*   **Backend**: Navigate to `dti-prediction-app/backend/`. Copy `.env.example` to a new file named `.env`, and populate it with your actual MongoDB connection URI, JWT secret keys, and SMTP email credentials.
*   **Docking**: Navigate to `dti-prediction-app/docking/`. Copy `.env.example` to `.env`.
*   **Frontend**: Navigate to `dti-prediction-app/frontend/`. Create a `.env.local` file containing:
    ```env
    NEXT_PUBLIC_API_URL=http://localhost:8000
    ```

> [!WARNING]
> Never commit `.env` or `.env.local` files containing real production credentials to public GitHub repositories. They are ignored by default via the root `.gitignore`.

---

### 2. Set Up the Backend
1. Open a terminal and navigate to the backend directory:
   ```bash
   cd dti-prediction-app/backend
   ```
2. Create and activate a Python virtual environment (or use a Conda environment):
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the FastAPI development server:
   ```bash
   uvicorn app.server:app --host 127.0.0.1 --port 8000 --reload
   ```
   *   **API Root URL**: `http://localhost:8000`
   *   **Interactive API Docs (Swagger)**: `http://localhost:8000/docs`
   *   **Health Status**: `http://localhost:8000/health`

---

### 3. Set Up the Frontend
1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd dti-prediction-app/frontend
   ```
2. Install Node dependencies:
   ```bash
   npm install
   ```
3. Start the Next.js development client:
   ```bash
   npm run dev
   ```
   *   **Web App UI URL**: `http://localhost:3000`

---

## 🧪 Testing and Verification

To verify that the system runs correctly:
1. Register a new account through the Web Interface (`http://localhost:3000/register`).
2. Verify email (if `EMAIL_VERIFICATION_REQUIRED=true` is enabled in backend `.env`).
3. Navigate to the Predict page.
4. Input a sample drug SMILES string and target FASTA sequence from the `testing_samples/` folder.
5. Click **Predict** to view binding interaction results, affinity score, and associated visualizations.

---

## 🔒 Security Best Practices for GitHub Pushing

1. **Verify Ignored Files**: Before pushing, run `git status` to ensure that virtual environments (`venv/`), Node dependencies (`node_modules/`), local build folders (`.next/`), and environment files containing credentials (`.env`, `.env.local`) are not marked for addition.
2. **Secrets Scanning**: If you accidentally commit a secret key, revoke the credentials immediately (e.g., change your MongoDB Atlas password and Gmail App Password).
3. **Repository Settings**: In your GitHub repository settings, enable **Secret Scanning** to detect any accidental leaks.
