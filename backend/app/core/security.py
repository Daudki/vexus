"""
Core security utilities for VEXUS.

Provides password hashing, token creation/validation, and security helpers.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import secrets
import re

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config.settings import get_settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ==================== PASSWORD FUNCTIONS ====================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def hash_password(password: str) -> str:
    """Alias for get_password_hash."""
    return get_password_hash(password)


def is_password_strong(password: str) -> bool:
    """Check if a password meets strength requirements."""
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True


# ==================== TOKEN FUNCTIONS ====================

def create_token(
    user_id: str,
    token_type: str = "access",
    extra_claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT token for authentication.
    
    Args:
        user_id: The user's ID
        token_type: 'access' or 'refresh'
        extra_claims: Additional claims to include
        expires_delta: Custom expiration time
    
    Returns:
        Encoded JWT token string
    """
    settings = get_settings()
    
    if extra_claims is None:
        extra_claims = {}
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    elif token_type == "refresh":
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    claims = {
        "sub": str(user_id),
        "type": token_type,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    claims.update(extra_claims)
    
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create an access token (alias for create_token)."""
    user_id = data.get("sub")
    extra_claims = {k: v for k, v in data.items() if k != "sub"}
    return create_token(user_id, "access", extra_claims, expires_delta)


def create_refresh_token(data: dict) -> str:
    """Create a refresh token (alias for create_token)."""
    user_id = data.get("sub")
    extra_claims = {k: v for k, v in data.items() if k != "sub"}
    return create_token(user_id, "refresh", extra_claims)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        Token claims if valid, None otherwise
    """
    settings = get_settings()
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ==================== SECURE RANDOM ====================

def generate_secure_token(length: int = 32) -> str:
    """Generate a secure random token."""
    return secrets.token_hex(length // 2)


def generate_secure_urlsafe_token(length: int = 32) -> str:
    """Generate a URL-safe secure random token."""
    return secrets.token_urlsafe(length // 2)