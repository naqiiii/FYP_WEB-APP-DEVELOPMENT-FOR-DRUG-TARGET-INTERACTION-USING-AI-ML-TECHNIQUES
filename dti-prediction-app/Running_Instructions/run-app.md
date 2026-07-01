
How to run the DTI app locally for development/testing


Step 1 — Start the Backend
Open a terminal, navigate to the backend folder, and run:
cd "c:\Users\DrugTarget\OneDrive\Desktop\DTI_webapp\dti-prediction-app\backend";
conda run --no-capture-output -n drug_target_env python -m uvicorn app.server:app --host 127.0.0.1 --port 8000 --reload


Step 2 — Start the Frontend
Open a second terminal, navigate to the frontend folder, and run:
cd "c:\Users\DrugTarget\OneDrive\Desktop\DTI_webapp\dti-prediction-app\frontend";
npm run dev:clean



Step 3 — Open in Browser
|  Web App | http://localhost:3000 |
|  Backend API Docs (Swagger) | http://localhost:8000/docs |
|  Backend Health Check | http://localhost:8000/health |
