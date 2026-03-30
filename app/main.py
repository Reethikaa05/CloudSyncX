"""
GitHub Cloud Connector - Main Application
A professional REST API connector for GitHub using FastAPI
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import logging

from app.routes import repos, issues, commits, pull_requests, auth
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.utils.logger import setup_logger

# Setup logging
logger = setup_logger(__name__)

# ─────────────────────────────────────────────
# App Initialization
# ─────────────────────────────────────────────
app = FastAPI(
    title="GitHub Cloud Connector",
    description="""
## 🚀 GitHub Cloud Connector API

A professional cloud connector that integrates with the GitHub API to expose
a clean, structured set of endpoints for repository and issue management.

### Features
- 🔐 **Secure Authentication** via Personal Access Token (PAT) or OAuth 2.0
- 📦 **Repository Management** — list, search, and inspect repositories
- 🐛 **Issue Tracking** — create, list, update, and close issues
- 🔀 **Pull Requests** — create and list pull requests *(Bonus)*
- 📝 **Commit History** — fetch commits with filtering
- ⚡ **Rate Limit Awareness** — built-in GitHub rate limit tracking
    """,
    version="1.0.0",
    contact={
        "name": "GitHub Connector",
        "url": "https://github.com",
    },
    license_info={
        "name": "MIT",
    },
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimiterMiddleware)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add X-Process-Time header to all responses."""
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
    return response


# ─────────────────────────────────────────────
# Exception Handlers
# ─────────────────────────────────────────────
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"The endpoint {request.url.path} does not exist.",
            "docs": "/docs",
        },
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again.",
        },
    )


# ─────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(repos.router, prefix="/repos", tags=["Repositories"])
app.include_router(issues.router, prefix="/issues", tags=["Issues"])
app.include_router(commits.router, prefix="/commits", tags=["Commits"])
app.include_router(pull_requests.router, prefix="/pulls", tags=["Pull Requests"])


# ─────────────────────────────────────────────
# Root & Health Endpoints
# ─────────────────────────────────────────────
@app.get("/", tags=["Health"], summary="API Root")
async def root():
    """Welcome endpoint with API overview."""
    return {
        "service": "GitHub Cloud Connector",
        "version": "1.0.0",
        "status": "online",
        "description": "A professional REST API connector for GitHub",
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
            "auth": "/auth/validate",
            "repos": "/repos",
            "issues": "/issues/{owner}/{repo}",
            "commits": "/commits/{owner}/{repo}",
            "pulls": "/pulls/{owner}/{repo}",
        },
    }


@app.get("/health", tags=["Health"], summary="Health Check")
async def health_check():
    """Check if the connector service is running."""
    return {
        "status": "healthy",
        "service": "github-cloud-connector",
        "version": "1.0.0",
        "timestamp": time.time(),
    }
