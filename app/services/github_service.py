"""
GitHub API Service
Core integration layer handling all GitHub API requests.
"""

import httpx
from typing import Optional
from fastapi import HTTPException

from app.utils.logger import setup_logger

logger = setup_logger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"


class GitHubService:
    """
    Service class encapsulating all GitHub API interactions.
    Handles authentication, request building, error mapping, and response parsing.
    """

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "GitHub-Cloud-Connector/1.0",
        }

    # ─────────────────────────────────────────────
    # Internal HTTP helpers
    # ─────────────────────────────────────────────

    async def _get(self, path: str, params: Optional[dict] = None) -> dict | list:
        """Execute an authenticated GET request to the GitHub API."""
        url = f"{GITHUB_API_BASE}{path}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                return self._handle_response(response)
            except httpx.TimeoutException:
                raise HTTPException(status_code=504, detail="GitHub API request timed out.")
            except httpx.ConnectError:
                raise HTTPException(status_code=503, detail="Cannot connect to GitHub API.")

    async def _post(self, path: str, payload: dict) -> dict:
        """Execute an authenticated POST request to the GitHub API."""
        url = f"{GITHUB_API_BASE}{path}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, headers=self.headers, json=payload)
                return self._handle_response(response)
            except httpx.TimeoutException:
                raise HTTPException(status_code=504, detail="GitHub API request timed out.")
            except httpx.ConnectError:
                raise HTTPException(status_code=503, detail="Cannot connect to GitHub API.")

    async def _patch(self, path: str, payload: dict) -> dict:
        """Execute an authenticated PATCH request to the GitHub API."""
        url = f"{GITHUB_API_BASE}{path}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.patch(url, headers=self.headers, json=payload)
                return self._handle_response(response)
            except httpx.TimeoutException:
                raise HTTPException(status_code=504, detail="GitHub API request timed out.")
            except httpx.ConnectError:
                raise HTTPException(status_code=503, detail="Cannot connect to GitHub API.")

    def _handle_response(self, response: httpx.Response) -> dict | list:
        """Map GitHub API HTTP status codes to meaningful exceptions."""
        if response.status_code == 200 or response.status_code == 201:
            return response.json()
        elif response.status_code == 204:
            return {"message": "Success (no content)"}
        elif response.status_code == 401:
            raise HTTPException(
                status_code=401,
                detail="GitHub authentication failed. Check your token.",
            )
        elif response.status_code == 403:
            detail = "GitHub API access forbidden."
            if "rate limit" in response.text.lower():
                detail = "GitHub API rate limit exceeded. Please wait before retrying."
            raise HTTPException(status_code=403, detail=detail)
        elif response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="GitHub resource not found. Check the owner/repo name.",
            )
        elif response.status_code == 422:
            errors = response.json().get("errors", [])
            raise HTTPException(
                status_code=422,
                detail=f"Validation error from GitHub: {errors}",
            )
        else:
            logger.error(f"Unexpected GitHub API status {response.status_code}: {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}",
            )

    # ─────────────────────────────────────────────
    # Auth
    # ─────────────────────────────────────────────

    async def get_authenticated_user(self) -> dict:
        """Fetch the authenticated user's profile."""
        return await self._get("/user")

    async def get_rate_limit(self) -> dict:
        """Get current GitHub API rate limit status."""
        return await self._get("/rate_limit")

    # ─────────────────────────────────────────────
    # Repositories
    # ─────────────────────────────────────────────

    async def list_user_repos(
        self,
        username: Optional[str] = None,
        sort: str = "updated",
        per_page: int = 30,
        page: int = 1,
    ) -> list:
        """List repos for authenticated user or a specific user."""
        params = {"sort": sort, "per_page": per_page, "page": page}
        if username:
            return await self._get(f"/users/{username}/repos", params=params)
        return await self._get("/user/repos", params=params)

    async def list_org_repos(
        self,
        org: str,
        sort: str = "updated",
        per_page: int = 30,
        page: int = 1,
    ) -> list:
        """List repos for an organization."""
        params = {"sort": sort, "per_page": per_page, "page": page}
        return await self._get(f"/orgs/{org}/repos", params=params)

    async def get_repo(self, owner: str, repo: str) -> dict:
        """Get details of a specific repository."""
        return await self._get(f"/repos/{owner}/{repo}")

    async def search_repos(self, query: str, sort: str = "stars", per_page: int = 10) -> dict:
        """Search public repositories."""
        params = {"q": query, "sort": sort, "per_page": per_page}
        return await self._get("/search/repositories", params=params)

    # ─────────────────────────────────────────────
    # Issues
    # ─────────────────────────────────────────────

    async def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        labels: Optional[str] = None,
        per_page: int = 30,
        page: int = 1,
    ) -> list:
        """List issues for a repository."""
        params = {"state": state, "per_page": per_page, "page": page}
        if labels:
            params["labels"] = labels
        return await self._get(f"/repos/{owner}/{repo}/issues", params=params)

    async def get_issue(self, owner: str, repo: str, issue_number: int) -> dict:
        """Get a specific issue."""
        return await self._get(f"/repos/{owner}/{repo}/issues/{issue_number}")

    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: Optional[str] = None,
        labels: Optional[list] = None,
        assignees: Optional[list] = None,
    ) -> dict:
        """Create a new issue in a repository."""
        payload = {"title": title}
        if body:
            payload["body"] = body
        if labels:
            payload["labels"] = labels
        if assignees:
            payload["assignees"] = assignees
        return await self._post(f"/repos/{owner}/{repo}/issues", payload)

    async def update_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[str] = None,
        labels: Optional[list] = None,
    ) -> dict:
        """Update an existing issue."""
        payload = {}
        if title:
            payload["title"] = title
        if body:
            payload["body"] = body
        if state:
            payload["state"] = state
        if labels is not None:
            payload["labels"] = labels
        return await self._patch(f"/repos/{owner}/{repo}/issues/{issue_number}", payload)

    # ─────────────────────────────────────────────
    # Commits
    # ─────────────────────────────────────────────

    async def list_commits(
        self,
        owner: str,
        repo: str,
        branch: Optional[str] = None,
        author: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        per_page: int = 30,
        page: int = 1,
    ) -> list:
        """List commits for a repository with optional filters."""
        params = {"per_page": per_page, "page": page}
        if branch:
            params["sha"] = branch
        if author:
            params["author"] = author
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        return await self._get(f"/repos/{owner}/{repo}/commits", params=params)

    async def get_commit(self, owner: str, repo: str, sha: str) -> dict:
        """Get a specific commit by SHA."""
        return await self._get(f"/repos/{owner}/{repo}/commits/{sha}")

    # ─────────────────────────────────────────────
    # Pull Requests (Bonus)
    # ─────────────────────────────────────────────

    async def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        sort: str = "created",
        per_page: int = 30,
        page: int = 1,
    ) -> list:
        """List pull requests for a repository."""
        params = {"state": state, "sort": sort, "per_page": per_page, "page": page}
        return await self._get(f"/repos/{owner}/{repo}/pulls", params=params)

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict:
        """Get a specific pull request."""
        return await self._get(f"/repos/{owner}/{repo}/pulls/{pr_number}")

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: Optional[str] = None,
        draft: bool = False,
    ) -> dict:
        """Create a new pull request."""
        payload = {
            "title": title,
            "head": head,
            "base": base,
            "draft": draft,
        }
        if body:
            payload["body"] = body
        return await self._post(f"/repos/{owner}/{repo}/pulls", payload)
