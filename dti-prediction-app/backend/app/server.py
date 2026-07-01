from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.concurrency import run_in_threadpool

from app.mongodb_connection import connect_to_mongodb, close_mongodb_connection, get_database_status
from app.settings import API_TITLE, API_DESCRIPTION, API_VERSION

from app.user_authentication.auth_routes import router as auth_router
from app.drug_target_prediction.prediction_routes import router as prediction_router
from app.prediction_history.history_routes import router as history_router
from app.visualization.visualization_routes import router as visualization_router
from app.drug_target_prediction.real_ml_model import preload_esm2

# The rate limiter prevents a single user or IP from overwhelming the service.
# This keeps the server stable for everyone and avoids accidental abuse from chatty clients.
limiter = Limiter(key_func=get_remote_address, default_limits=["50/minute"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup and shutdown tasks when the app begins and ends."""
    print("Starting up DTI Prediction API...")
    # Connect to the database before any request arrives.
    await connect_to_mongodb()
    
    # Pre-load ESM-2 model in a background thread to prevent lazy-loading freezes
    asyncio.create_task(run_in_threadpool(preload_esm2))
    
    print("API is ready!")
    
    yield
    
    # Cleanly close the database connection during shutdown.
    print("Shutting down...")
    await close_mongodb_connection()
    print("ALLAH HAFIZ!")

app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    lifespan=lifespan
)

# SlowAPI reads the limiter from app state when handling decorated routes.
app.state.limiter = limiter

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

import traceback
import uuid
from fastapi.exceptions import HTTPException

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # If the exception is already an HTTPException, return its specific status and detail
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
        
    # Generate a unique tracking code for debugging on the server logs
    error_id = f"ERR-{uuid.uuid4().hex[:8].upper()}"
    
    # Print the detailed traceback with error ID to the server console
    print("\n" + "="*80)
    print(f"[ERROR] [{error_id}] UNHANDLED EXCEPTION OCCURRED:")
    traceback.print_exc()
    print("="*80 + "\n")
    
    # Return a sanitized response to the frontend
    return JSONResponse(
        status_code=500,
        content={"detail": f"An unexpected system error occurred. Reference ID: {error_id}. Please try again later or contact support."}
    )

# CORS allows the browser frontend to talk to this backend when they are on different addresses.
# The allowed origins list should match the frontend URLs used during development and deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://dti-webapp.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(auth_router)
app.include_router(prediction_router)
app.include_router(history_router)
app.include_router(visualization_router)

@app.get("/")
async def root():
    """A simple welcome page for the API.

    This is a human-readable endpoint that anyone can visit in a browser.
    It confirms the service is running and points to the interactive API docs.
    """
    return {
        "message": "DTI Prediction API",
        "version": API_VERSION,
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """A machine-friendly endpoint used by health checks and uptime monitors."""
    return {"status": "healthy", "database": get_database_status()}
