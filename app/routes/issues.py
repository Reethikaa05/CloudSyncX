"""
Issues Routes
Endpoints for creating, listing, and managing GitHub issues.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.services.github_service import GitHubService
from app.services.auth_service import get_github_service
from app.models.schemas import CreateIssueRequest, UpdateIssueRequest, IssueState
from app.utils.response_formatter import format_issue, format_issues

router = APIRouter()


@router.get(
    "/{owner}/{repo}",
    summary="List Issues",
    description="List issues for a repository. Supports filtering by state and labels.",
)
async def list_issues(
    owner: str,
    repo: str,
    state: IssueState = Query(IssueState.open, description="Filter by issue state"),
    labels: Optional[str] = Query(None, description="Comma-separated label names (e.g. bug,help wanted)"),
    per_page: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    service: GitHubService = Depends(get_github_service),
):
    """List issues for a specific repository."""
    issues = await service.list_issues(
        owner=owner,
        repo=repo,
        state=state.value,
        labels=labels,
        per_page=per_page,
        page=page,
    )
    # Filter out pull requests (GitHub issues endpoint returns PRs too)
    issues = [i for i in issues if "pull_request" not in i]
    return {
        "owner": owner,
        "repo": repo,
        "state": state.value,
        "issues": format_issues(issues),
        "meta": {"page": page, "per_page": per_page, "count": len(issues)},
    }


@router.get(
    "/{owner}/{repo}/{issue_number}",
    summary="Get Issue",
    description="Get details of a specific issue by its number.",
)
async def get_issue(
    owner: str,
    repo: str,
    issue_number: int,
    service: GitHubService = Depends(get_github_service),
):
    """Get a specific issue."""
    issue = await service.get_issue(owner=owner, repo=repo, issue_number=issue_number)
    return format_issue(issue, detailed=True)


@router.post(
    "/{owner}/{repo}",
    summary="Create Issue",
    description="Create a new issue in a repository.",
    status_code=201,
)
async def create_issue(
    owner: str,
    repo: str,
    body: CreateIssueRequest,
    service: GitHubService = Depends(get_github_service),
):
    """Create a new issue in the specified repository."""
    issue = await service.create_issue(
        owner=owner,
        repo=repo,
        title=body.title,
        body=body.body,
        labels=body.labels,
        assignees=body.assignees,
    )
    return {
        "message": "Issue created successfully",
        "issue": format_issue(issue, detailed=True),
    }


@router.patch(
    "/{owner}/{repo}/{issue_number}",
    summary="Update Issue",
    description="Update an existing issue's title, body, state, or labels.",
)
async def update_issue(
    owner: str,
    repo: str,
    issue_number: int,
    body: UpdateIssueRequest,
    service: GitHubService = Depends(get_github_service),
):
    """Update an existing issue."""
    issue = await service.update_issue(
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        title=body.title,
        body=body.body,
        state=body.state.value if body.state else None,
        labels=body.labels,
    )
    return {
        "message": "Issue updated successfully",
        "issue": format_issue(issue, detailed=True),
    }
