"""
Authentication Service
Handles PAT token extraction, validation, and OAuth 2.0 flow.
"""

import os
import httpx
import secrets
from typing import Optional
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.github_service import GitHubService
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

# Security scheme for Swagger UI
security = HTTPBearer(
    scheme_name="GitHub PAT",
    description="Enter your GitHub Personal Access Token (PAT). Prefix: `Bearer <token>`",
)

# In-memory store for OAuth state (use Redis/DB in production)
_oauth_states: dict[str, bool] = {}


# ─────────────────────────────────────────────
# PAT Authentication Dependency
# ─────────────────────────────────────────────


async def get_github_service(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> GitHubService:
    """
    FastAPI dependency that extracts and validates the GitHub token.
    Falls back to GITHUB_TOKEN environment variable if no Authorization header provided.
    """
    token = credentials.credentials if credentials else None

    # Fallback to environment variable
    if not token:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise HTTPException(
                status_code=401,
                detail=(
                    "No authentication token provided. "
                    "Pass a Bearer token or set the GITHUB_TOKEN environment variable."
                ),
            )

    # Basic token format validation
    if len(token) < 10:
        raise HTTPException(
            status_code=401,
            detail="Invalid token format. GitHub PATs are typically 40+ characters.",
        )

    return GitHubService(token=token)


# ─────────────────────────────────────────────
# OAuth 2.0 Helpers (Bonus)
# ─────────────────────────────────────────────


def get_oauth_config() -> dict:
    """Load OAuth config from environment variables."""
    client_id = os.getenv("GITHUB_CLIENT_ID")
    client_secret = os.getenv("GITHUB_CLIENT_SECRET")
    redirect_uri = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/auth/callback")

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail=(
                "OAuth is not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET "
                "environment variables to enable OAuth 2.0 authentication."
            ),
        )
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }


def generate_oauth_state() -> str:
    """Generate a secure random state parameter for OAuth CSRF protection."""
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = True
    return state


def validate_oauth_state(state: str) -> bool:
    """Validate and consume a one-time OAuth state token."""
    if state in _oauth_states:
        del _oauth_states[state]
        return True
    return False


async def exchange_code_for_token(code: str, state: str) -> dict:
    """Exchange OAuth authorization code for an access token."""
    if not validate_oauth_state(state):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state parameter. Possible CSRF attack.",
        )

    config = get_oauth_config()

    payload = {
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "code": code,
        "redirect_uri": config["redirect_uri"],
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            json=payload,
            headers={"Accept": "application/json"},
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub OAuth token exchange failed: {response.text}",
        )

    data = response.json()
    if "error" in data:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth error: {data.get('error_description', data['error'])}",
        )

    logger.info("OAuth token exchange successful")
    return data
