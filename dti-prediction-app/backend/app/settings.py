import os
from dotenv import load_dotenv

load_dotenv(override=True)


def _get_bool_env(name: str, default: bool) -> bool:
    """Read a boolean environment variable in a friendly way."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# Local MongoDB is the default so the app can run during development.
# In production, override this with a remote database connection string.
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://127.0.0.1:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "dti_prediction")

# Replace the fallback secret before deploying.
# This secret signs the tokens that prove who is logged in.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 10
JWT_REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

API_VERSION = "1.0.0"
API_TITLE = "DTI Prediction API"
API_DESCRIPTION = "Drug-Target Interaction Prediction Backend API"

# Email settings are used only if you want account verification + password reset.
SMTP_SERVER = os.getenv("SMTP_SERVER", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_VERIFICATION_REQUIRED = _get_bool_env("EMAIL_VERIFICATION_REQUIRED", False)

print(f"[Email] Email verification required: {EMAIL_VERIFICATION_REQUIRED}")

# Frontend URL is used to build links in verification/reset emails.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
