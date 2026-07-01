from datetime import datetime, timedelta
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from app.settings import (
    JWT_SECRET_KEY, 
    JWT_ALGORITHM, 
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_MINUTES
)

def hash_password(plain_password: str) -> str:
    """
    Hash a plain text password.
    
    Args:
        plain_password: The user's plain text password
        
    Returns:
        Hashed password string (safe to store in database)
    """
    password_bytes = plain_password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    
    Args:
        plain_password: The password entered by user
        hashed_password: The hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(user_id: str, email: str) -> str:
    """
    Create a JWT access token for a user.
    
    The token contains:
    - sub (subject): user's ID
    - email: user's email
    - exp (expiration): when token expires
    - iat (issued at): when token was created
    
    Args:
        user_id: The user's unique ID from database
        email: The user's email
        
    Returns:
        JWT token string
    """
    expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    token_data = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": expire,
        "iat": datetime.utcnow()
    }
    
    encoded_jwt = jwt.encode(token_data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def create_refresh_token(user_id: str, email: str) -> str:
    """
    Create a JWT refresh token for a user.
    """
    expire = datetime.utcnow() + timedelta(minutes=JWT_REFRESH_TOKEN_EXPIRE_MINUTES)
    token_data = {
        "sub": user_id,
        "email": email,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(token_data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def create_reset_token(user_id: str, email: str, hashed_password: str) -> str:
    """
    Create a JWT reset token that becomes invalid when the user's password changes.
    This prevents token reuse.
    """
    expire = datetime.utcnow() + timedelta(minutes=15)
    token_data = {
        "sub": user_id,
        "email": email,
        "type": "reset",
        "hash_frag": hashed_password[-15:] if hashed_password else "",
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(token_data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def create_verify_token(user_id: str, email: str) -> str:
    """
    Create a JWT token specifically for email verification.
    """
    expire = datetime.utcnow() + timedelta(hours=24)
    token_data = {
        "sub": user_id,
        "email": email,
        "type": "verify",
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(token_data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str, expected_type: str = "access") -> Optional[dict]:
    """
    Decode and validate a JWT token, ensuring it strictly matches expected_type.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        # A token must match the route that is using it.
        if payload.get("type") != expected_type and payload.get("type") is not None:
            # Older tokens may not have a type field, so keep that migration path open.
            return None
        return payload
    except JWTError:
        return None
