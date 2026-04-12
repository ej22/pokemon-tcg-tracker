"""Authentication endpoints: login, status, logout."""
import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from services.auth import verify_password, create_access_token, decode_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginRequest):
    """Validate credentials and return a 24-hour JWT."""
    auth_username = os.getenv("AUTH_USERNAME")
    auth_password = os.getenv("AUTH_PASSWORD", "")

    if not auth_username:
        # Auth is disabled on this instance — return a sentinel response.
        return {"token": "disabled", "expires_in": 0, "auth_enabled": False}

    if body.username != auth_username or not verify_password(body.password, auth_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": auth_username})
    return {"token": token, "expires_in": 86400, "auth_enabled": True}


@router.get("/status")
async def auth_status(request: Request):
    """Return whether auth is enabled and whether the current request is authenticated."""
    auth_username = os.getenv("AUTH_USERNAME")
    if not auth_username:
        return {"auth_enabled": False, "authenticated": True}

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return {"auth_enabled": True, "authenticated": False}

    token = auth_header[7:]
    payload = decode_token(token)
    if payload and payload.get("sub"):
        return {"auth_enabled": True, "authenticated": True, "username": payload["sub"]}

    return {"auth_enabled": True, "authenticated": False}


@router.post("/logout")
async def logout():
    """Client-side logout — token is discarded by the client."""
    return {"detail": "Logged out"}
