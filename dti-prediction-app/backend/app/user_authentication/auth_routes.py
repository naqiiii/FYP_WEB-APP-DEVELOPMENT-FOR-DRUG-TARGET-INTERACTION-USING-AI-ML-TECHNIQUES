from datetime import datetime
import traceback
from bson.objectid import ObjectId
from fastapi import APIRouter, HTTPException, status, Request, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.mongodb_connection import get_database
from app.settings import EMAIL_VERIFICATION_REQUIRED
from app.user_authentication.user_schemas import (
    UserSignupRequest, UserLoginRequest, UserResponse,
    LoginResponse, SignupResponse, ForgotPasswordRequest,
    ResetPasswordRequest, TokenRefreshRequest, RefreshResponse,
    UserProfileUpdateRequest
)
from app.user_authentication.password_and_token_utils import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, create_reset_token, create_verify_token,
    decode_jwt_token
)
from app.user_authentication.email_service import (
    send_verification_email, send_password_reset_email,
    send_login_alert_email, is_email_configured
)
from app.user_authentication.jwt_bearer import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address)

@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def signup(request: Request, user_data: UserSignupRequest):
    """Register a new user account."""
    try:
        db = get_database()
        users = db["users"]
        
        # Do not allow the same email to register twice.
        if await users.find_one({"email": user_data.email}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email is already registered."
            )
        
        new_user = {
            "email": user_data.email,
            "hashed_password": hash_password(user_data.password),
            "full_name": user_data.full_name,
            "created_at": datetime.utcnow(),
            "is_verified": False
        }
        
        # Passwords are never stored in plain text. We store a hashed version only.
        result = await users.insert_one(new_user)
        user_id = str(result.inserted_id)
        
        token = create_verify_token(user_id=user_id, email=new_user["email"])
        
        # In development, we often skip email verification to avoid blocking the flow.
        if not EMAIL_VERIFICATION_REQUIRED:
            await users.update_one({"_id": result.inserted_id}, {"$set": {"is_verified": True}})
            message = "Account created. Auto-verified for local development."
        else:
            if not is_email_configured():
                await users.update_one({"_id": result.inserted_id}, {"$set": {"is_verified": True}})
                message = "Account created. Auto-verified because email is not configured."
            else:
                email_sent = send_verification_email(
                    new_user["email"],
                    new_user["full_name"],
                    token,
                    user_data.client_url
                )
                if email_sent:
                    message = "Account created. Please check your email to verify."
                else:
                    await users.update_one({"_id": result.inserted_id}, {"$set": {"is_verified": True}})
                    message = "Account created. Auto-verified because the verification email could not be sent."
        
        return SignupResponse(
            message=message,
            user=UserResponse(
                id=user_id,
                email=new_user["email"],
                full_name=new_user["full_name"],
                created_at=new_user["created_at"]
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Signup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again later."
        )

@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(request: Request, login_data: UserLoginRequest):
    """Authenticate user and return JWT tokens."""
    try:
        db = get_database()
        user = await db["users"].find_one({"email": login_data.email})
        print(f"[DEBUG] EMAIL_VERIFICATION_REQUIRED: {EMAIL_VERIFICATION_REQUIRED}")
        print(f"[DEBUG] User found: {bool(user)}")
        if user:
            print(f"[DEBUG] User is_verified: {user.get('is_verified', None)}")
        
        if not user or not verify_password(login_data.password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password."
            )
        
        # If email verification is enforced, block login until the user completes it.
        is_verified = user.get("is_verified", True)
        if not EMAIL_VERIFICATION_REQUIRED or not is_email_configured():
            print("[DEBUG] Skipping verification check due to config.")
            is_verified = True
        else:
            print("[DEBUG] Verification required and email is configured.")
        
        if not is_verified:
            print("[DEBUG] Blocking login: user not verified.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please verify your email before logging in."
            )
        
        # Create short-lived and long-lived tokens for session management.
        user_id = str(user["_id"])
        access_token = create_access_token(user_id=user_id, email=user["email"])
        refresh_token = create_refresh_token(user_id=user_id, email=user["email"])
        
        # Send the alert only when email is already part of the auth flow.
        if EMAIL_VERIFICATION_REQUIRED and is_email_configured():
            send_login_alert_email(
                user["email"], 
                user["full_name"], 
                request.client.host or "Unknown", 
                request.headers.get("User-Agent", "Unknown")
            )
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse(
                id=user_id,
                email=user["email"],
                full_name=user["full_name"],
                created_at=user["created_at"],
                profile_picture=user.get("profile_picture")
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again later."
        )

@router.get("/verify-email")
async def verify_email(token: str):
    """Handle email verification links."""
    try:
        db = get_database()
        payload = decode_jwt_token(token, expected_type="verify")
        if not payload or not payload.get("email"):
            raise HTTPException(status_code=400, detail="Invalid or expired token.")
            
        email = payload["email"]
        result = await db["users"].update_one({"email": email}, {"$set": {"is_verified": True}})
        
        if result.modified_count == 0:
            user = await db["users"].find_one({"email": email})
            if user and user.get("is_verified"):
                return {"message": "Email already verified."}
            raise HTTPException(status_code=404, detail="User not found.")
            
        return {"message": "Email verified successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, data: ForgotPasswordRequest):
    """Initiate password reset flow."""
    try:
        db = get_database()
        user = await db["users"].find_one({"email": data.email})
        if user:
            token = create_reset_token(
                user_id=str(user["_id"]), 
                email=user["email"], 
                hashed_password=user.get("hashed_password", "")
            )
            send_password_reset_email(user["email"], user["full_name"], token, data.client_url)
        
        # For privacy, always return the same message whether or not the email existed.
        return {"message": "If that email exists, a reset link has been sent."}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to process request.")

@router.post("/reset-password")
@limiter.limit("3/minute")
async def reset_password(request: Request, data: ResetPasswordRequest):
    """Handle the actual password reset using a token."""
    try:
        db = get_database()
        payload = decode_jwt_token(data.token, expected_type="reset")
        if not payload:
            raise HTTPException(status_code=400, detail="Invalid token.")
            
        email = payload.get("email")
        user = await db["users"].find_one({"email": email})
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
            
        # Password changes invalidate older reset links.
        current_hash = user.get("hashed_password", "")
        if current_hash[-15:] != payload.get("hash_frag") and current_hash:
            raise HTTPException(status_code=400, detail="Token already used.")
            
        await db["users"].update_one(
            {"email": email},
            {"$set": {"hashed_password": hash_password(data.new_password)}}
        )
        return {"message": "Password updated successfully."}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Reset failed.")

@router.put("/profile", response_model=UserResponse)
@limiter.limit("5/minute")
async def update_profile(
    request: Request,
    data: UserProfileUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update user profile details."""
    try:
        db = get_database()
        user_id = current_user["sub"]
        
        update_fields = {}
        if data.profile_picture is not None:
            update_fields["profile_picture"] = data.profile_picture
            
        if update_fields:
            await db["users"].update_one({"_id": ObjectId(user_id)}, {"$set": update_fields})
            
        user = await db["users"].find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
            
        return UserResponse(
            id=str(user["_id"]),
            email=user["email"],
            full_name=user["full_name"],
            created_at=user["created_at"],
            profile_picture=user.get("profile_picture")
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Profile update failed.")

@router.post("/refresh", response_model=RefreshResponse)
@limiter.limit("20/minute")
async def refresh_access_token(request: Request, data: TokenRefreshRequest):
    """Exchange refresh token for a new access token."""
    try:
        payload = decode_jwt_token(data.refresh_token, expected_type="refresh")
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid session.")
        
        new_token = create_access_token(user_id=payload["sub"], email=payload["email"])
        return RefreshResponse(access_token=new_token)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Token refresh failed.")

@router.post("/logout")
async def logout(request: Request):
    """Audit endpoint for logging out."""
    return {"message": "Logged out successfully."}
