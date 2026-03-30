"""
Pull Requests Routes (Bonus Feature)
Endpoints for creating and listing GitHub pull requests.
"""

from fastapi import APIRouter, Depends, Query

from app.services.github_service import GitHubService
from app.services.auth_service import get_github_service
from app.models.schemas import CreatePullRequestRequest, PRState
from app.utils.response_formatter import format_pull_request, format_pull_requests

router = APIRouter()


@router.get(
    "/{owner}/{repo}",
    summary="List Pull Requests",
    description="List pull requests for a repository. Filter by state: open, closed, or all.",
)
async def list_pull_requests(
    owner: str,
    repo: str,
    state: PRState = Query(PRState.open, description="Filter by PR state"),
    sort: str = Query("created", description="Sort by: created, updated, popularity, long-running"),
    per_page: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    service: GitHubService = Depends(get_github_service),
):
    """List pull requests for a repository."""
    prs = await service.list_pull_requests(
        owner=owner,
        repo=repo,
        state=state.value,
        sort=sort,
        per_page=per_page,
        page=page,
    )
    return {
        "owner": owner,
        "repo": repo,
        "state": state.value,
        "pull_requests": format_pull_requests(prs),
        "meta": {"page": page, "per_page": per_page, "count": len(prs)},
    }


@router.get(
    "/{owner}/{repo}/{pr_number}",
    summary="Get Pull Request",
    description="Get details of a specific pull request.",
)
async def get_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
    service: GitHubService = Depends(get_github_service),
):
    """Get details for a specific pull request."""
    pr = await service.get_pull_request(owner=owner, repo=repo, pr_number=pr_number)
    return format_pull_request(pr, detailed=True)


@router.post(
    "/{owner}/{repo}",
    summary="Create Pull Request",
    description=(
        "Create a new pull request. "
        "The `head` branch must exist and have commits not in `base`."
    ),
    status_code=201,
)
async def create_pull_request(
    owner: str,
    repo: str,
    body: CreatePullRequestRequest,
    service: GitHubService = Depends(get_github_service),
):
    """Create a new pull request in the specified repository."""
    pr = await service.create_pull_request(
        owner=owner,
        repo=repo,
        title=body.title,
        head=body.head,
        base=body.base,
        body=body.body,
        draft=body.draft,
    )
    return {
        "message": "Pull request created successfully",
        "pull_request": format_pull_request(pr, detailed=True),
    }
