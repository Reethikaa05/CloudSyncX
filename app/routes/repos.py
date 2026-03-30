"""
Repositories Routes
Endpoints for listing, fetching, and searching GitHub repositories.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.services.github_service import GitHubService
from app.services.auth_service import get_github_service
from app.models.schemas import RepoSort
from app.utils.response_formatter import format_repo, format_repos

router = APIRouter()


@router.get(
    "",
    summary="List My Repositories",
    description="List repositories for the authenticated user.",
)
async def list_my_repos(
    sort: RepoSort = Query(RepoSort.updated, description="Sort by"),
    per_page: int = Query(30, ge=1, le=100, description="Results per page"),
    page: int = Query(1, ge=1, description="Page number"),
    service: GitHubService = Depends(get_github_service),
):
    """List all repositories for the authenticated user."""
    repos = await service.list_user_repos(sort=sort.value, per_page=per_page, page=page)
    return {
        "repos": format_repos(repos),
        "meta": {"page": page, "per_page": per_page, "count": len(repos)},
    }


@router.get(
    "/user/{username}",
    summary="List User Repositories",
    description="List public repositories for any GitHub user.",
)
async def list_user_repos(
    username: str,
    sort: RepoSort = Query(RepoSort.updated, description="Sort by"),
    per_page: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    service: GitHubService = Depends(get_github_service),
):
    """List public repos for a specific user."""
    repos = await service.list_user_repos(
        username=username, sort=sort.value, per_page=per_page, page=page
    )
    return {
        "username": username,
        "repos": format_repos(repos),
        "meta": {"page": page, "per_page": per_page, "count": len(repos)},
    }


@router.get(
    "/org/{org}",
    summary="List Organization Repositories",
    description="List repositories for a GitHub organization.",
)
async def list_org_repos(
    org: str,
    sort: RepoSort = Query(RepoSort.updated),
    per_page: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    service: GitHubService = Depends(get_github_service),
):
    """List repos for a GitHub organization."""
    repos = await service.list_org_repos(org=org, sort=sort.value, per_page=per_page, page=page)
    return {
        "org": org,
        "repos": format_repos(repos),
        "meta": {"page": page, "per_page": per_page, "count": len(repos)},
    }


@router.get(
    "/search",
    summary="Search Repositories",
    description="Search GitHub public repositories by keyword.",
)
async def search_repos(
    q: str = Query(..., description="Search query (e.g. 'fastapi stars:>1000')"),
    sort: str = Query("stars", description="Sort by: stars, forks, updated"),
    per_page: int = Query(10, ge=1, le=30),
    service: GitHubService = Depends(get_github_service),
):
    """Search public repositories on GitHub."""
    results = await service.search_repos(query=q, sort=sort, per_page=per_page)
    items = results.get("items", [])
    return {
        "query": q,
        "total_count": results.get("total_count", 0),
        "repos": format_repos(items),
    }


@router.get(
    "/{owner}/{repo}",
    summary="Get Repository",
    description="Get detailed information about a specific repository.",
)
async def get_repo(
    owner: str,
    repo: str,
    service: GitHubService = Depends(get_github_service),
):
    """Get details for a specific repository."""
    data = await service.get_repo(owner=owner, repo=repo)
    return format_repo(data, detailed=True)
