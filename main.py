"""
╔══════════════════════════════════════════════════════════════╗
║           GitHub Cloud Connector  —  All-in-One              ║
║           FastAPI + Python  |  Run in VS Code                ║
╚══════════════════════════════════════════════════════════════╝

HOW TO RUN:
  1. pip install -r requirements.txt
  2. Copy .env.example → .env and add your GitHub token
  3. python main.py
  4. Open http://localhost:8000/docs
"""

# ─────────────────────────────────────────────────────────────
# Standard Library
# ─────────────────────────────────────────────────────────────
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
from typing import Any, List, Optional

# ─────────────────────────────────────────────────────────────
# Third-Party
# ─────────────────────────────────────────────────────────────
import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file early
load_dotenv()

# ══════════════════════════════════════════════════════════════
# SECTION 1 — CONFIGURATION
# ══════════════════════════════════════════════════════════════

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    github_token: str = ""
    github_api_base_url: str = "https://api.github.com"
    app_env: str = "development"
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def has_pat(self) -> bool:
        return bool(self.github_token)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# ══════════════════════════════════════════════════════════════
# SECTION 2 — LOGGING
# ══════════════════════════════════════════════════════════════

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# SECTION 3 — CUSTOM EXCEPTIONS
# ══════════════════════════════════════════════════════════════

class GitHubConnectorError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class AuthenticationError(GitHubConnectorError):
    def __init__(self, message: str = "GitHub authentication failed. Check your token."):
        super().__init__(message, status_code=401)

class NotFoundError(GitHubConnectorError):
    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found.", status_code=404)

class ForbiddenError(GitHubConnectorError):
    def __init__(self, message: str = "Insufficient permissions for this action."):
        super().__init__(message, status_code=403)

class RateLimitError(GitHubConnectorError):
    def __init__(self, reset_at: str = ""):
        msg = (f"GitHub API rate limit exceeded. Resets at: {reset_at}"
               if reset_at else "GitHub API rate limit exceeded.")
        super().__init__(msg, status_code=429)

class ValidationError(GitHubConnectorError):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)

class GitHubAPIError(GitHubConnectorError):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(f"GitHub API error: {message}", status_code=status_code)


# ══════════════════════════════════════════════════════════════
# SECTION 4 — PYDANTIC MODELS (Request & Response)
# ══════════════════════════════════════════════════════════════

# ── Request Models ────────────────────────────────────────────

class CreateIssueRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256, description="Issue title")
    body: Optional[str] = Field(None, description="Issue description (Markdown supported)")
    labels: Optional[List[str]] = Field(default=[], description="List of label names")
    assignees: Optional[List[str]] = Field(default=[], description="GitHub usernames to assign")
    milestone: Optional[int] = Field(None, description="Milestone number")

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title must not be blank")
        return v.strip()


class CreatePullRequestRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256, description="PR title")
    head: str = Field(..., description="Branch with your changes (e.g. 'feature/my-branch')")
    base: str = Field(..., description="Branch to merge into (e.g. 'main')")
    body: Optional[str] = Field(None, description="PR description")
    draft: bool = Field(False, description="Open as draft PR")
    maintainer_can_modify: bool = Field(True)

    @field_validator("head", "base")
    @classmethod
    def branch_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Branch name must not be blank")
        return v.strip()


# ── Response Models ───────────────────────────────────────────

class UserSummary(BaseModel):
    login: str
    html_url: str
    avatar_url: Optional[str] = None

class LabelSummary(BaseModel):
    name: str
    color: str
    description: Optional[str] = None

class RepositoryResponse(BaseModel):
    id: int
    name: str
    full_name: str
    description: Optional[str]
    private: bool
    html_url: str
    clone_url: str
    ssh_url: str
    language: Optional[str]
    stargazers_count: int
    forks_count: int
    open_issues_count: int
    default_branch: str
    created_at: datetime
    updated_at: datetime
    pushed_at: Optional[datetime]
    topics: List[str] = []
    owner: UserSummary

class IssueResponse(BaseModel):
    id: int
    number: int
    title: str
    body: Optional[str]
    state: str
    html_url: str
    labels: List[LabelSummary] = []
    assignees: List[UserSummary] = []
    user: UserSummary
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    comments: int

class CommitAuthor(BaseModel):
    name: Optional[str]
    email: Optional[str]
    date: Optional[datetime]

class CommitResponse(BaseModel):
    sha: str
    short_sha: str
    message: str
    author: Optional[CommitAuthor]
    committer: Optional[CommitAuthor]
    html_url: str
    comment_count: int

class PullRequestResponse(BaseModel):
    id: int
    number: int
    title: str
    body: Optional[str]
    state: str
    draft: bool
    html_url: str
    head_branch: str
    base_branch: str
    user: UserSummary
    created_at: datetime
    updated_at: datetime
    merged_at: Optional[datetime] = None
    mergeable: Optional[bool] = None
    labels: List[LabelSummary] = []

class AuthenticatedUserResponse(BaseModel):
    login: str
    name: Optional[str]
    email: Optional[str]
    bio: Optional[str]
    company: Optional[str]
    location: Optional[str]
    public_repos: int
    followers: int
    following: int
    html_url: str
    avatar_url: str
    created_at: datetime


# ══════════════════════════════════════════════════════════════
# SECTION 5 — GITHUB HTTP CLIENT
# ══════════════════════════════════════════════════════════════

class GitHubClient:
    """Async HTTP client for the GitHub REST API."""

    def __init__(self, token: Optional[str] = None):
        cfg = get_settings()
        self._token = token or cfg.github_token
        self._base_url = cfg.github_api_base_url

        if not self._token:
            raise AuthenticationError(
                "No GitHub token found. Set GITHUB_TOKEN in your .env file."
            )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "GitHubCloudConnector/1.0",
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers(),
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        )

    def _raise_for_status(self, response: httpx.Response) -> None:
        code = response.status_code
        try:
            body = response.json()
            message = body.get("message", "Unknown error")
            errors = body.get("errors", [])
            if errors:
                details = "; ".join(
                    e.get("message", str(e)) if isinstance(e, dict) else str(e)
                    for e in errors
                )
                message = f"{message}: {details}"
        except Exception:
            message = response.text or "Unknown error"

        logger.warning("GitHub API %s: %s", code, message)

        if code == 401:
            raise AuthenticationError()
        if code == 403:
            if "rate limit" in message.lower():
                reset_ts = response.headers.get("X-RateLimit-Reset", "")
                reset_human = ""
                if reset_ts:
                    try:
                        reset_human = datetime.fromtimestamp(
                            int(reset_ts), tz=timezone.utc
                        ).strftime("%Y-%m-%d %H:%M:%S UTC")
                    except Exception:
                        pass
                raise RateLimitError(reset_human)
            raise ForbiddenError(message)
        if code == 404:
            raise NotFoundError(message)
        if code == 422:
            raise ValidationError(message)
        if code == 429:
            raise RateLimitError(response.headers.get("X-RateLimit-Reset", ""))
        raise GitHubAPIError(message, status_code=code)

    async def get(self, path: str, params: Optional[dict] = None) -> Any:
        async with self._client() as c:
            r = await c.get(path, params=params)
            if not r.is_success:
                self._raise_for_status(r)
            return r.json()

    async def post(self, path: str, payload: dict) -> Any:
        async with self._client() as c:
            r = await c.post(path, json=payload)
            if not r.is_success:
                self._raise_for_status(r)
            return r.json()


# ══════════════════════════════════════════════════════════════
# SECTION 6 — GITHUB SERVICE (Business Logic)
# ══════════════════════════════════════════════════════════════

def _user(d: dict) -> UserSummary:
    return UserSummary(login=d["login"], html_url=d["html_url"], avatar_url=d.get("avatar_url"))

def _label(d: dict) -> LabelSummary:
    return LabelSummary(name=d["name"], color=d["color"], description=d.get("description"))

def _repo(d: dict) -> RepositoryResponse:
    return RepositoryResponse(
        id=d["id"], name=d["name"], full_name=d["full_name"],
        description=d.get("description"), private=d["private"],
        html_url=d["html_url"], clone_url=d["clone_url"], ssh_url=d["ssh_url"],
        language=d.get("language"), stargazers_count=d.get("stargazers_count", 0),
        forks_count=d.get("forks_count", 0), open_issues_count=d.get("open_issues_count", 0),
        default_branch=d.get("default_branch", "main"),
        created_at=d["created_at"], updated_at=d["updated_at"], pushed_at=d.get("pushed_at"),
        topics=d.get("topics", []), owner=_user(d["owner"]),
    )

def _issue(d: dict) -> IssueResponse:
    return IssueResponse(
        id=d["id"], number=d["number"], title=d["title"], body=d.get("body"),
        state=d["state"], html_url=d["html_url"],
        labels=[_label(l) for l in d.get("labels", [])],
        assignees=[_user(a) for a in d.get("assignees", [])],
        user=_user(d["user"]), created_at=d["created_at"], updated_at=d["updated_at"],
        closed_at=d.get("closed_at"), comments=d.get("comments", 0),
    )

def _commit(d: dict) -> CommitResponse:
    c = d.get("commit", {})
    a = c.get("author") or {}
    cm = c.get("committer") or {}
    sha = d["sha"]
    return CommitResponse(
        sha=sha, short_sha=sha[:7],
        message=c.get("message", "").split("\n")[0],
        author=CommitAuthor(name=a.get("name"), email=a.get("email"), date=a.get("date")) if a else None,
        committer=CommitAuthor(name=cm.get("name"), email=cm.get("email"), date=cm.get("date")) if cm else None,
        html_url=d.get("html_url", ""), comment_count=c.get("comment_count", 0),
    )

def _pull(d: dict) -> PullRequestResponse:
    return PullRequestResponse(
        id=d["id"], number=d["number"], title=d["title"], body=d.get("body"),
        state=d["state"], draft=d.get("draft", False), html_url=d["html_url"],
        head_branch=d["head"]["ref"], base_branch=d["base"]["ref"],
        user=_user(d["user"]), created_at=d["created_at"], updated_at=d["updated_at"],
        merged_at=d.get("merged_at"), mergeable=d.get("mergeable"),
        labels=[_label(l) for l in d.get("labels", [])],
    )


class GitHubService:
    def __init__(self, token: Optional[str] = None):
        self.client = GitHubClient(token=token)

    # ── Auth ──────────────────────────────────────────────────
    async def get_authenticated_user(self) -> AuthenticatedUserResponse:
        d = await self.client.get("/user")
        return AuthenticatedUserResponse(
            login=d["login"], name=d.get("name"), email=d.get("email"),
            bio=d.get("bio"), company=d.get("company"), location=d.get("location"),
            public_repos=d.get("public_repos", 0), followers=d.get("followers", 0),
            following=d.get("following", 0), html_url=d["html_url"],
            avatar_url=d["avatar_url"], created_at=d["created_at"],
        )

    # ── Repos ─────────────────────────────────────────────────
    async def list_user_repos(self, username: Optional[str] = None,
                               page: int = 1, per_page: int = 30,
                               sort: str = "updated") -> List[RepositoryResponse]:
        path = f"/users/{username}/repos" if username else "/user/repos"
        data = await self.client.get(path, params={"page": page, "per_page": min(per_page, 100), "sort": sort})
        return [_repo(r) for r in data]

    async def list_org_repos(self, org: str, page: int = 1,
                              per_page: int = 30) -> List[RepositoryResponse]:
        data = await self.client.get(f"/orgs/{org}/repos",
                                     params={"page": page, "per_page": min(per_page, 100)})
        return [_repo(r) for r in data]

    async def get_repo(self, owner: str, repo: str) -> RepositoryResponse:
        return _repo(await self.client.get(f"/repos/{owner}/{repo}"))

    # ── Issues ────────────────────────────────────────────────
    async def list_issues(self, owner: str, repo: str, state: str = "open",
                           page: int = 1, per_page: int = 30,
                           label: Optional[str] = None) -> List[IssueResponse]:
        params: dict = {"state": state, "page": page, "per_page": min(per_page, 100)}
        if label:
            params["labels"] = label
        data = await self.client.get(f"/repos/{owner}/{repo}/issues", params=params)
        return [_issue(i) for i in data if "pull_request" not in i]  # filter PRs

    async def get_issue(self, owner: str, repo: str, number: int) -> IssueResponse:
        return _issue(await self.client.get(f"/repos/{owner}/{repo}/issues/{number}"))

    async def create_issue(self, owner: str, repo: str,
                            payload: CreateIssueRequest) -> IssueResponse:
        body: dict = {"title": payload.title}
        if payload.body:      body["body"] = payload.body
        if payload.labels:    body["labels"] = payload.labels
        if payload.assignees: body["assignees"] = payload.assignees
        if payload.milestone: body["milestone"] = payload.milestone
        return _issue(await self.client.post(f"/repos/{owner}/{repo}/issues", body))

    # ── Commits ───────────────────────────────────────────────
    async def list_commits(self, owner: str, repo: str, branch: Optional[str] = None,
                            page: int = 1, per_page: int = 30,
                            author: Optional[str] = None) -> List[CommitResponse]:
        params: dict = {"page": page, "per_page": min(per_page, 100)}
        if branch: params["sha"] = branch
        if author: params["author"] = author
        data = await self.client.get(f"/repos/{owner}/{repo}/commits", params=params)
        return [_commit(c) for c in data]

    # ── Pull Requests ─────────────────────────────────────────
    async def list_pull_requests(self, owner: str, repo: str, state: str = "open",
                                  page: int = 1, per_page: int = 30) -> List[PullRequestResponse]:
        data = await self.client.get(f"/repos/{owner}/{repo}/pulls",
                                     params={"state": state, "page": page, "per_page": min(per_page, 100)})
        return [_pull(p) for p in data]

    async def create_pull_request(self, owner: str, repo: str,
                                   payload: CreatePullRequestRequest) -> PullRequestResponse:
        body: dict = {"title": payload.title, "head": payload.head, "base": payload.base,
                      "draft": payload.draft, "maintainer_can_modify": payload.maintainer_can_modify}
        if payload.body: body["body"] = payload.body
        return _pull(await self.client.post(f"/repos/{owner}/{repo}/pulls", body))


# ══════════════════════════════════════════════════════════════
# SECTION 7 — DEPENDENCY INJECTION
# ══════════════════════════════════════════════════════════════

async def get_service(authorization: Optional[str] = Header(default=None)) -> GitHubService:
    """
    Resolves token from Authorization header first, then falls back to GITHUB_TOKEN env var.
    Pass header as:  Authorization: Bearer ghp_your_token
    """
    token: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    return GitHubService(token=token)


# ══════════════════════════════════════════════════════════════
# SECTION 8 — FASTAPI APPLICATION
# ══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 GitHub Cloud Connector starting [env=%s]", settings.app_env)
    if not settings.has_pat:
        logger.warning("⚠️  GITHUB_TOKEN not set — add it to your .env file")
    yield
    logger.info("🛑 GitHub Cloud Connector stopped")


app = FastAPI(
    title="GitHub Cloud Connector",
    description="""
A production-ready REST API connector for the GitHub API.

## Quick Start
1. Add `GITHUB_TOKEN=ghp_...` to your `.env` file
2. Open **/docs** and click **Authorize** (optional — token from `.env` is used automatically)
3. Try any endpoint!

## Authentication
Token is read from `GITHUB_TOKEN` in your `.env` file.  
You can also override it per-request:
```
Authorization: Bearer ghp_your_token
```

## Endpoints
| Group | What you can do |
|---|---|
| **Auth** | Verify token, get your GitHub profile |
| **Repos** | List your repos, org repos, or get repo details |
| **Issues** | List, get, and create issues |
| **Commits** | Fetch commit history with filters |
| **Pull Requests** | List and create pull requests |
""",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(GitHubConnectorError)
async def connector_error_handler(request: Request, exc: GitHubConnectorError):
    return JSONResponse(status_code=exc.status_code, content={"success": False, "detail": exc.message})

@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.exception("Unexpected error: %s", str(exc))
    return JSONResponse(status_code=500, content={"success": False, "detail": "An unexpected error occurred."})


# ══════════════════════════════════════════════════════════════
# SECTION 9 — ROUTE HANDLERS
# ══════════════════════════════════════════════════════════════

PREFIX = "/api/v1"

# ── Health ────────────────────────────────────────────────────

@app.get("/", tags=["Health"], include_in_schema=False)
async def root():
    return {"message": "GitHub Cloud Connector", "docs": "/docs", "health": "/health"}

@app.get("/health", tags=["Health"], summary="Health check")
async def health():
    return {"status": "healthy", "version": "1.0.0", "env": settings.app_env,
            "github_token_configured": settings.has_pat}


# ── Auth ──────────────────────────────────────────────────────

@app.get(f"{PREFIX}/auth/me", tags=["Authentication"],
         response_model=AuthenticatedUserResponse,
         summary="Get authenticated user",
         description="Returns your GitHub profile. Use this to verify your token is working.")
async def get_me(svc: GitHubService = Depends(get_service)):
    try:
        return await svc.get_authenticated_user()
    except GitHubConnectorError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@app.get(f"{PREFIX}/auth/verify", tags=["Authentication"],
         summary="Verify token",
         description="Quick check — returns your login name if the token is valid.")
async def verify_token(svc: GitHubService = Depends(get_service)):
    try:
        user = await svc.get_authenticated_user()
        return {"valid": True, "login": user.login, "name": user.name,
                "message": f"Authenticated as @{user.login}"}
    except GitHubConnectorError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ── Repositories ──────────────────────────────────────────────

@app.get(f"{PREFIX}/repos", tags=["Repositories"],
         response_model=List[RepositoryResponse],
         summary="List repositories",
         description="List repos for the authenticated user, or pass `?username=` for any public user.")
async def list_repos(
    username: Optional[str] = Query(None, description="GitHub username (leave blank for your own)"),
    page: int = Query(1, ge=1), per_page: int = Query(30, ge=1, le=100),
    sort: str = Query("updated", description="Sort: created | updated | pushed | full_name"),
    svc: GitHubService = Depends(get_service),
):
    try:
        return await svc.list_user_repos(username=username, page=page, per_page=per_page, sort=sort)
    except GitHubConnectorError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@app.get(f"{PREFIX}/repos/org/{{org}}", tags=["Repositories"],
         response_model=List[RepositoryResponse],
         summary="List organization repositories")
async def list_org_repos(
    org: str, page: int = Query(1, ge=1), per_page: int = Query(30, ge=1, le=100),
    svc: GitHubService = Depends(get_service),
):
    try:
        return await svc.list_org_repos(org=org, page=page, per_page=per_page)
    except GitHubConnectorError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@app.get(f"{PREFIX}/repos/{{owner}}/{{repo}}", tags=["Repositories"],
         response_model=RepositoryResponse,
         summary="Get repository details")
async def get_repo(owner: str, repo: str, svc: GitHubService = Depends(get_service)):
    try:
        return await svc.get_repo(owner=owner, repo=repo)
    except GitHubConnectorError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ── Issues ────────────────────────────────────────────────────

@app.get(f"{PREFIX}/repos/{{owner}}/{{repo}}/issues", tags=["Issues"],
         response_model=List[IssueResponse],
         summary="List issues",
         description="List issues for a repo. Pull requests are automatically excluded.")
async def list_issues(
    owner: str, repo: str,
    state: str = Query("open", description="open | closed | all"),
    label: Optional[str] = Query(None, description="Filter by label name"),
    page: int = Query(1, ge=1), per_page: int = Query(30, ge=1, le=100),
    svc: GitHubService = Depends(get_service),
):
    try:
        return await svc.list_issues(owner=owner, repo=repo, state=state,
                                     page=page, per_page=per_page, label=label)
    except GitHubConnectorError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@app.get(f"{PREFIX}/repos/{{owner}}/{{repo}}/issues/{{issue_number}}", tags=["Issues"],
         response_model=IssueResponse, summary="Get a single issue")
async def get_issue(
    owner: str, repo: str,
    issue_number: int = Path(..., ge=1, description="Issue number"),
    svc: GitHubService = Depends(get_service),
):
    try:
        return await svc.get_issue(owner=owner, repo=repo, number=issue_number)
    except GitHubConnectorError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@app.post(f"{PREFIX}/repos/{{owner}}/{{repo}}/issues", tags=["Issues"],
          response_model=IssueResponse, status_code=201,
          summary="Create an issue",
          description="Create a new issue in a repository. Requires write access.")
async def create_issue(
    owner: str, repo: str,
    payload: CreateIssueRequest,
    svc: GitHubService = Depends(get_service),
):
    try:
        return await svc.create_issue(owner=owner, repo=repo, payload=payload)
    except GitHubConnectorError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ── Commits ───────────────────────────────────────────────────

@app.get(f"{PREFIX}/repos/{{owner}}/{{repo}}/commits", tags=["Commits"],
         response_model=List[CommitResponse],
         summary="List commits",
         description="Fetch commit history. Filter by `branch` or `author`.")
async def list_commits(
    owner: str, repo: str,
    branch: Optional[str] = Query(None, description="Branch name, tag, or commit SHA"),
    author: Optional[str] = Query(None, description="GitHub login or email to filter by"),
    page: int = Query(1, ge=1), per_page: int = Query(30, ge=1, le=100),
    svc: GitHubService = Depends(get_service),
):
    try:
        return await svc.list_commits(owner=owner, repo=repo, branch=branch,
                                      page=page, per_page=per_page, author=author)
    except GitHubConnectorError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ── Pull Requests ─────────────────────────────────────────────

@app.get(f"{PREFIX}/repos/{{owner}}/{{repo}}/pulls", tags=["Pull Requests"],
         response_model=List[PullRequestResponse],
         summary="List pull requests")
async def list_pulls(
    owner: str, repo: str,
    state: str = Query("open", description="open | closed | all"),
    page: int = Query(1, ge=1), per_page: int = Query(30, ge=1, le=100),
    svc: GitHubService = Depends(get_service),
):
    try:
        return await svc.list_pull_requests(owner=owner, repo=repo, state=state,
                                            page=page, per_page=per_page)
    except GitHubConnectorError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@app.post(f"{PREFIX}/repos/{{owner}}/{{repo}}/pulls", tags=["Pull Requests"],
          response_model=PullRequestResponse, status_code=201,
          summary="Create a pull request",
          description="Creates a PR. The `head` branch must exist and have commits ahead of `base`.")
async def create_pull(
    owner: str, repo: str,
    payload: CreatePullRequestRequest,
    svc: GitHubService = Depends(get_service),
):
    try:
        return await svc.create_pull_request(owner=owner, repo=repo, payload=payload)
    except GitHubConnectorError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ══════════════════════════════════════════════════════════════
# SECTION 10 — ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "═" * 55)
    print("  GitHub Cloud Connector")
    print("  http://localhost:8000/docs  ← Interactive API docs")
    print("  http://localhost:8000/health")
    print("═" * 55 + "\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
