# Pydantic schemas for auth requests, responses, and database structure.

import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator

# --- Request Models ---

class UserSignupRequest(BaseModel):
    """Schema for new user registration."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="Password (8+ chars, 1 uppercase, 1 digit)")
    full_name: str = Field(..., min_length=2, description="User's full name")
    client_url: Optional[str] = Field(None, description="Frontend URL for email links")

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Ensure password meets complexity requirements."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit.")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "Secure1234",
                "full_name": "John Doe"
            }
        }

class UserLoginRequest(BaseModel):
    """Schema for authentication requests."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "Secure1234"
            }
        }

class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="JWT refresh token")

class VerifyEmailRequest(BaseModel):
    token: str = Field(..., description="JWT verification token")

class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    client_url: Optional[str] = Field(None, description="Frontend URL for email links")

class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="JWT reset token")
    new_password: str = Field(..., min_length=8, description="New strong password")

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Must contain an uppercase letter.")
        if not re.search(r"\d", v):
            raise ValueError("Must contain a digit.")
        return v

class UserProfileUpdateRequest(BaseModel):
    profile_picture: Optional[str] = Field(None, description="Base64 encoded image")

# --- Response Models ---

class UserResponse(BaseModel):
    """Standard user info returned after auth (excludes sensitive data)."""
    id: str
    email: str
    full_name: str
    created_at: datetime
    profile_picture: Optional[str] = None

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class SignupResponse(BaseModel):
    message: str = "User created successfully"
    user: UserResponse

# --- Database Schema ---

class UserInDB(BaseModel):
    """How the user object is structured in MongoDB."""
    email: str
    hashed_password: str
    full_name: str
    created_at: datetime
    is_verified: bool = False
    profile_picture: Optional[str] = None
