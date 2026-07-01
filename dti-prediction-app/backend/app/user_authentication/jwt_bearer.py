# JWT Bearer Authentication
# This file contains the dependency for protecting routes with JWT

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.user_authentication.password_and_token_utils import decode_jwt_token

# This tells FastAPI to look for "Authorization: Bearer <token>" header
jwt_bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(jwt_bearer_scheme)
) -> dict:
    """
    Dependency to get the current authenticated user from JWT token.
    
    Use this as a dependency in any route that needs authentication:
    
    Example:
        @router.get("/protected")
        async def protected_route(current_user: dict = Depends(get_current_user)):
            return {"user_id": current_user["sub"]}
    
    Args:
        credentials: The Bearer token from Authorization header
        
    Returns:
        Decoded token data containing user_id (sub) and email
        
    Raises:
        HTTPException 401: If token is missing, invalid, or expired
    """
    token = credentials.credentials
    
    # Decode and validate the token
    payload = decode_jwt_token(token, expected_type="access")
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return payload
