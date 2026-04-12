"""Authentication helpers: password verification, JWT creation/decoding, require_auth dependency."""
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request
from jose import JWTError, jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory fallback secret when JWT_SECRET_KEY is not configured.
# Tokens are invalidated on container restart — acceptable for initial setup.
_fallback_secret: str = secrets.token_hex(32)


def get_jwt_secret() -> str:
    return os.getenv("JWT_SECRET_KEY") or _fallback_secret


def verify_password(plain: str, stored: str) -> bool:
    """Verify a password against a stored value.

    ``stored`` may be a bcrypt hash (starts with ``$2b$``, ``$2a$``, or
    ``$2y$``) or a plaintext string.  Plaintext is compared directly so
    that simple .env configurations work without pre-hashing.
    """
    if stored.startswith(("$2b$", "$2a$", "$2y$")):
        try:
            return pwd_context.verify(plain, stored)
        except Exception:
            return False
    return plain == stored


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=24))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, get_jwt_secret(), algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
    except JWTError:
        return None


async def require_auth(request: Request) -> Optional[str]:
    """FastAPI dependency for write endpoints.

    Returns the authenticated username, or ``None`` when auth is disabled
    (``AUTH_USERNAME`` not set in environment).  Raises ``HTTPException(401)``
    when auth is enabled but the token is missing or invalid.
    """
    auth_username = os.getenv("AUTH_USERNAME")
    if not auth_username:
        return None  # Auth disabled — allow everything through

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header[7:]
    payload = decode_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload["sub"]
