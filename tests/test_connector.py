"""
Test Suite for GitHub Cloud Connector
Tests for routes, auth, and service layer using mocking.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.services.github_service import GitHubService


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

MOCK_TOKEN = "ghp_testtoken1234567890abcdefghijklmn"
AUTH_HEADERS = {"Authorization": f"Bearer {MOCK_TOKEN}"}

MOCK_USER = {
    "login": "octocat",
    "name": "The Octocat",
    "email": "octocat@github.com",
    "avatar_url": "https://avatars.githubusercontent.com/u/583231",
    "html_url": "https://github.com/octocat",
    "public_repos": 8,
    "followers": 14000,
    "following": 9,
    "created_at": "2011-01-25T18:44:36Z",
    "bio": "I am the Octocat.",
    "company": "GitHub",
    "location": "San Francisco, CA",
}

MOCK_REPO = {
    "id": 1,
    "name": "Hello-World",
    "full_name": "octocat/Hello-World",
    "description": "My first repository",
    "html_url": "https://github.com/octocat/Hello-World",
    "private": False,
    "fork": False,
    "stargazers_count": 1800,
    "forks_count": 1500,
    "open_issues_count": 0,
    "language": "Python",
    "default_branch": "main",
    "updated_at": "2024-01-01T00:00:00Z",
    "created_at": "2011-01-26T19:01:12Z",
    "clone_url": "https://github.com/octocat/Hello-World.git",
    "ssh_url": "git@github.com:octocat/Hello-World.git",
    "size": 108,
    "watchers_count": 1800,
    "topics": ["python", "example"],
    "license": {"name": "MIT"},
    "has_issues": True,
    "has_wiki": True,
    "pushed_at": "2024-01-01T00:00:00Z",
    "owner": {
        "login": "octocat",
        "avatar_url": "https://avatars.githubusercontent.com/u/583231",
        "html_url": "https://github.com/octocat",
    },
}

MOCK_ISSUE = {
    "number": 1,
    "title": "Found a bug",
    "state": "open",
    "html_url": "https://github.com/octocat/Hello-World/issues/1",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-02T00:00:00Z",
    "labels": [{"name": "bug"}],
    "user": {"login": "octocat"},
    "comments": 0,
    "body": "This is a bug report.",
    "closed_at": None,
    "assignees": [],
    "milestone": None,
}

MOCK_COMMIT = {
    "sha": "abc1234567890abcdef1234567890abcdef12345",
    "commit": {
        "message": "Fix: resolve login issue",
        "author": {
            "name": "The Octocat",
            "email": "octocat@github.com",
            "date": "2024-01-01T12:00:00Z",
        },
        "committer": {"date": "2024-01-01T12:00:00Z"},
    },
    "author": {
        "login": "octocat",
        "avatar_url": "https://avatars.githubusercontent.com/u/583231",
    },
    "html_url": "https://github.com/octocat/Hello-World/commit/abc1234",
    "parents": [{"sha": "def5678901234567890abcdef5678901234567890"}],
    "stats": {"additions": 10, "deletions": 5, "total": 15},
    "files": [],
}

MOCK_PR = {
    "number": 1,
    "title": "feat: Add new feature",
    "state": "open",
    "draft": False,
    "html_url": "https://github.com/octocat/Hello-World/pull/1",
    "head": {"ref": "feature/new-thing"},
    "base": {"ref": "main"},
    "user": {"login": "octocat"},
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-02T00:00:00Z",
    "merged": False,
    "merged_at": None,
    "labels": [],
    "comments": 2,
    "commits": 3,
    "additions": 50,
    "deletions": 10,
    "body": "## Summary\nAdds a new feature.",
    "assignees": [],
    "requested_reviewers": [],
    "mergeable": True,
    "changed_files": 5,
    "closed_at": None,
    "merge_commit_sha": None,
}

MOCK_RATE_LIMIT = {
    "resources": {
        "core": {"limit": 5000, "used": 100, "remaining": 4900, "reset": 1704067200},
        "search": {"limit": 30, "used": 5, "remaining": 25},
    }
}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_service():
    service = AsyncMock(spec=GitHubService)
    service.get_authenticated_user = AsyncMock(return_value=MOCK_USER)
    service.get_rate_limit = AsyncMock(return_value=MOCK_RATE_LIMIT)
    service.list_user_repos = AsyncMock(return_value=[MOCK_REPO])
    service.get_repo = AsyncMock(return_value=MOCK_REPO)
    service.list_issues = AsyncMock(return_value=[MOCK_ISSUE])
    service.get_issue = AsyncMock(return_value=MOCK_ISSUE)
    service.create_issue = AsyncMock(return_value=MOCK_ISSUE)
    service.update_issue = AsyncMock(return_value=MOCK_ISSUE)
    service.list_commits = AsyncMock(return_value=[MOCK_COMMIT])
    service.get_commit = AsyncMock(return_value=MOCK_COMMIT)
    service.list_pull_requests = AsyncMock(return_value=[MOCK_PR])
    service.get_pull_request = AsyncMock(return_value=MOCK_PR)
    service.create_pull_request = AsyncMock(return_value=MOCK_PR)
    return service


# ─────────────────────────────────────────────
# Health Tests
# ─────────────────────────────────────────────

def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "GitHub Cloud Connector"
    assert "endpoints" in data


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


# ─────────────────────────────────────────────
# Auth Tests
# ─────────────────────────────────────────────

def test_validate_token(client, mock_service):
    with patch("app.routes.auth.get_github_service", return_value=mock_service):
        response = client.get("/auth/validate", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["user"]["login"] == "octocat"


def test_rate_limit(client, mock_service):
    with patch("app.routes.auth.get_github_service", return_value=mock_service):
        response = client.get("/auth/rate-limit", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "core" in data
    assert data["core"]["limit"] == 5000


def test_no_token_returns_401(client):
    response = client.get("/auth/validate")
    assert response.status_code in (401, 403)


# ─────────────────────────────────────────────
# Repository Tests
# ─────────────────────────────────────────────

def test_list_my_repos(client, mock_service):
    with patch("app.routes.repos.get_github_service", return_value=mock_service):
        response = client.get("/repos", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "repos" in data
    assert len(data["repos"]) == 1
    assert data["repos"][0]["name"] == "Hello-World"


def test_get_repo(client, mock_service):
    with patch("app.routes.repos.get_github_service", return_value=mock_service):
        response = client.get("/repos/octocat/Hello-World", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["name"] == "Hello-World"
    assert response.json()["stars"] == 1800


# ─────────────────────────────────────────────
# Issues Tests
# ─────────────────────────────────────────────

def test_list_issues(client, mock_service):
    with patch("app.routes.issues.get_github_service", return_value=mock_service):
        response = client.get("/issues/octocat/Hello-World", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "issues" in data
    assert data["issues"][0]["title"] == "Found a bug"


def test_create_issue(client, mock_service):
    payload = {"title": "New bug found", "body": "Details here.", "labels": ["bug"]}
    with patch("app.routes.issues.get_github_service", return_value=mock_service):
        response = client.post("/issues/octocat/Hello-World", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    assert response.json()["message"] == "Issue created successfully"


def test_create_issue_empty_title(client, mock_service):
    payload = {"title": "  ", "body": "Some body"}
    with patch("app.routes.issues.get_github_service", return_value=mock_service):
        response = client.post("/issues/octocat/Hello-World", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_update_issue(client, mock_service):
    payload = {"state": "closed"}
    with patch("app.routes.issues.get_github_service", return_value=mock_service):
        response = client.patch("/issues/octocat/Hello-World/1", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["message"] == "Issue updated successfully"


# ─────────────────────────────────────────────
# Commits Tests
# ─────────────────────────────────────────────

def test_list_commits(client, mock_service):
    with patch("app.routes.commits.get_github_service", return_value=mock_service):
        response = client.get("/commits/octocat/Hello-World", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "commits" in data
    assert data["commits"][0]["message"] == "Fix: resolve login issue"
    assert data["commits"][0]["short_sha"] == "abc1234"


# ─────────────────────────────────────────────
# Pull Request Tests
# ─────────────────────────────────────────────

def test_list_pull_requests(client, mock_service):
    with patch("app.routes.pull_requests.get_github_service", return_value=mock_service):
        response = client.get("/pulls/octocat/Hello-World", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "pull_requests" in data
    assert data["pull_requests"][0]["title"] == "feat: Add new feature"


def test_create_pull_request(client, mock_service):
    payload = {
        "title": "feat: New feature",
        "head": "feature/new",
        "base": "main",
        "body": "PR description",
        "draft": False,
    }
    with patch("app.routes.pull_requests.get_github_service", return_value=mock_service):
        response = client.post("/pulls/octocat/Hello-World", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    assert response.json()["message"] == "Pull request created successfully"
