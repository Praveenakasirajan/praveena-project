"""
auth.py - Secure authentication, password hashing, and session token verification.
Ensures strict user isolation across all interview sessions and history.
"""

import os
import hmac
import hashlib
import json
import base64
import time
from typing import Optional, Dict, Any
from fastapi import Request, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from dotenv import load_dotenv

import models
from database import get_db

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "ai_interview_coach_secret_key_2026_expo_secure").encode("utf-8")
TOKEN_EXPIRY_SECONDS = 86400 * 7  # 7 days
SALT_LENGTH = 16
PBKDF2_ITERATIONS = 120_000

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash password securely using PBKDF2-HMAC-SHA256 with a unique random salt."""
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    salt = os.urandom(SALT_LENGTH)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against stored salt$hash string using constant-time comparison."""
    if not plain_password or not hashed_password or "$" not in hashed_password:
        return False
    try:
        salt_hex, key_hex = hashed_password.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        computed_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        return hmac.compare_digest(expected_key, computed_key)
    except Exception:
        return False


def create_access_token(user_id: int, email: str, name: str) -> str:
    """Create a tamper-proof cryptographically signed URL-safe session token."""
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_EXPIRY_SECONDS,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    
    signature = hmac.new(SECRET_KEY, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    
    return f"{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify cryptographic signature and expiration of session token."""
    if not token or "." not in token:
        return None
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        
        # Verify signature
        expected_sig = hmac.new(SECRET_KEY, payload_b64.encode("utf-8"), hashlib.sha256).digest()
        
        # Add padding back if necessary
        sig_padding = 4 - (len(sig_b64) % 4) if len(sig_b64) % 4 != 0 else 0
        actual_sig = base64.urlsafe_b64decode(sig_b64 + "=" * sig_padding)
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        
        payload_padding = 4 - (len(payload_b64) % 4) if len(payload_b64) % 4 != 0 else 0
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + "=" * payload_padding)
        payload = json.loads(payload_bytes.decode("utf-8"))
        
        # Check expiration
        if payload.get("exp", 0) < int(time.time()):
            return None
        
        return payload
    except Exception:
        return None


def extract_token_from_request(request: Request) -> Optional[str]:
    """Extract token from Authorization header or cookie."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    
    # Check cookie
    cookie_token = request.cookies.get("session_token")
    if cookie_token:
        return cookie_token.strip()
    
    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> models.User:
    """Dependency for strictly authenticating a user. Raises 401 if invalid."""
    token = extract_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    user = db.query(models.User).filter(models.User.id == user_id, models.User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    """Dependency that returns current user if authenticated, or None if guest."""
    token = extract_token_from_request(request)
    if not token:
        return None
    
    payload = decode_access_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    return db.query(models.User).filter(models.User.id == user_id, models.User.is_active == True).first()
