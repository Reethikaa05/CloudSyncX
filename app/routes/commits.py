"""
Commits Routes
Endpoints for fetching commit history from GitHub repositories.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.services.github_service import GitHubService
from app.services.auth_service import get_github_service
from app.utils.response_formatter import format_commit, format_commits

router = APIRouter()


@router.get(
    "/{owner}/{repo}",
    summary="List Commits",
    description=(
        "Fetch commit history for a repository. "
        "Supports filtering by branch, author, and date range."
    ),
)
async def list_commits(
    owner: str,
    repo: str,
    branch: Optional[str] = Query(None, description="Branch name or commit SHA (default: repo default branch)"),
    author: Optional[str] = Query(None, description="GitHub username or email to filter commits by"),
    since: Optional[str] = Query(None, description="ISO 8601 date: show commits after this (e.g. 2024-01-01T00:00:00Z)"),
    until: Optional[str] = Query(None, description="ISO 8601 date: show commits before this (e.g. 2024-12-31T23:59:59Z)"),
    per_page: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    service: GitHubService = Depends(get_github_service),
):
    """List commits for a repository with optional filters."""
    commits = await service.list_commits(
        owner=owner,
        repo=repo,
        branch=branch,
        author=author,
        since=since,
        until=until,
        per_page=per_page,
        page=page,
    )
    return {
        "owner": owner,
        "repo": repo,
        "branch": branch or "default",
        "commits": format_commits(commits),
        "meta": {"page": page, "per_page": per_page, "count": len(commits)},
    }


@router.get(
    "/{owner}/{repo}/{sha}",
    summary="Get Commit",
    description="Get details of a specific commit by SHA.",
)
async def get_commit(
    owner: str,
    repo: str,
    sha: str,
    service: GitHubService = Depends(get_github_service),
):
    """Get details for a specific commit."""
    commit = await service.get_commit(owner=owner, repo=repo, sha=sha)
    return format_commit(commit, detailed=True)
