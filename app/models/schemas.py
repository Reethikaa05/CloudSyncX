"""
Data Models
Pydantic schemas for request validation and response serialization.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from enum import Enum


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────


class IssueState(str, Enum):
    open = "open"
    closed = "closed"
    all = "all"


class PRState(str, Enum):
    open = "open"
    closed = "closed"
    all = "all"


class RepoSort(str, Enum):
    created = "created"
    updated = "updated"
    pushed = "pushed"
    full_name = "full_name"


class CommitSort(str, Enum):
    author_date = "author-date"
    committer_date = "committer-date"


# ─────────────────────────────────────────────
# Issue Models
# ─────────────────────────────────────────────


class CreateIssueRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256, description="Issue title")
    body: Optional[str] = Field(None, description="Issue body (supports Markdown)")
    labels: Optional[List[str]] = Field(default=[], description="List of label names")
    assignees: Optional[List[str]] = Field(default=[], description="GitHub usernames to assign")

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Issue title cannot be blank or whitespace.")
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Bug: Login page crashes on mobile",
                "body": "## Description\nThe login page crashes on iOS Safari.\n\n## Steps\n1. Open app on iPhone\n2. Tap Login\n3. App crashes",
                "labels": ["bug", "mobile"],
                "assignees": ["octocat"],
            }
        }
    }


class UpdateIssueRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=256)
    body: Optional[str] = None
    state: Optional[IssueState] = None
    labels: Optional[List[str]] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Updated title",
                "state": "closed",
                "labels": ["bug", "fixed"],
            }
        }
    }


# ─────────────────────────────────────────────
# Pull Request Models
# ─────────────────────────────────────────────


class CreatePullRequestRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256, description="PR title")
    head: str = Field(
        ...,
        description="Branch containing your changes (e.g. 'feature/my-branch' or 'user:branch')",
    )
    base: str = Field(
        ...,
        description="Branch to merge into (e.g. 'main' or 'develop')",
    )
    body: Optional[str] = Field(None, description="PR description (supports Markdown)")
    draft: bool = Field(False, description="Mark as draft pull request")

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("PR title cannot be blank.")
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "feat: Add OAuth 2.0 authentication",
                "head": "feature/oauth-support",
                "base": "main",
                "body": "## Summary\nAdds GitHub OAuth 2.0 flow.\n\n## Changes\n- Added OAuth routes\n- Secure state management",
                "draft": False,
            }
        }
    }


# ─────────────────────────────────────────────
# Response Wrappers
# ─────────────────────────────────────────────


class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[dict] = None


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    count: int
