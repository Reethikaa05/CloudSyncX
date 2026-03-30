"""
Authentication Routes
Endpoints for token validation and OAuth 2.0 flow.
"""

import os
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from app.services.github_service import GitHubService
from app.services.auth_service import (
    get_github_service,
    get_oauth_config,
    generate_oauth_state,
    exchange_code_for_token,
)
from app.utils.response_formatter import format_user, format_rate_limit

router = APIRouter()


@router.get(
    "/validate",
    summary="Validate Token",
    description="Validates your GitHub token and returns authenticated user info.",
)
async def validate_token(service: GitHubService = Depends(get_github_service)):
    """Validate the provided token and return authenticated user profile."""
    user = await service.get_authenticated_user()
    rate_limit = await service.get_rate_limit()
    return {
        "authenticated": True,
        "user": format_user(user),
        "rate_limit": format_rate_limit(rate_limit),
    }


@router.get(
    "/rate-limit",
    summary="GitHub Rate Limit",
    description="Check current GitHub API rate limit status for your token.",
)
async def get_rate_limit(service: GitHubService = Depends(get_github_service)):
    """Return current GitHub API rate limit status."""
    data = await service.get_rate_limit()
    return format_rate_limit(data)


# ─────────────────────────────────────────────
# OAuth 2.0 Routes (Bonus)
# ─────────────────────────────────────────────


@router.get(
    "/oauth/authorize",
    summary="Start OAuth 2.0 Flow",
    description="Redirects to GitHub for OAuth 2.0 authorization. Requires `GITHUB_CLIENT_ID` env var.",
    tags=["OAuth 2.0"],
)
async def oauth_authorize():
    """Initiate OAuth 2.0 authorization code flow."""
    config = get_oauth_config()
    state = generate_oauth_state()
    scopes = "repo,read:user,read:org"

    auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={config['client_id']}"
        f"&redirect_uri={config['redirect_uri']}"
        f"&scope={scopes}"
        f"&state={state}"
    )
    return RedirectResponse(url=auth_url)


@router.get(
    "/oauth/callback",
    summary="OAuth 2.0 Callback",
    description="GitHub redirects here with authorization code. Exchanges code for access token.",
    tags=["OAuth 2.0"],
)
async def oauth_callback(code: str, state: str):
    """Handle OAuth 2.0 callback and exchange code for access token."""
    token_data = await exchange_code_for_token(code, state)

    access_token = token_data.get("access_token")
    token_type = token_data.get("token_type", "bearer")
    scope = token_data.get("scope", "")

    # Validate token by fetching user
    service = GitHubService(token=access_token)
    user = await service.get_authenticated_user()

    return {
        "message": "OAuth 2.0 authentication successful",
        "token_type": token_type,
        "scope": scope,
        "access_token": access_token,
        "note": "Store this token securely and pass it as: Authorization: Bearer <token>",
        "authenticated_user": format_user(user),
    }
