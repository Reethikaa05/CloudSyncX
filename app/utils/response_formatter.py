"""
Response Formatters
Clean, consistent response shaping for GitHub API data.
"""

from typing import Optional


def format_user(user: dict) -> dict:
    """Format GitHub user data for API response."""
    return {
        "login": user.get("login"),
        "name": user.get("name"),
        "email": user.get("email"),
        "avatar_url": user.get("avatar_url"),
        "html_url": user.get("html_url"),
        "public_repos": user.get("public_repos"),
        "followers": user.get("followers"),
        "following": user.get("following"),
        "created_at": user.get("created_at"),
        "bio": user.get("bio"),
        "company": user.get("company"),
        "location": user.get("location"),
    }


def format_rate_limit(data: dict) -> dict:
    """Format GitHub rate limit data."""
    core = data.get("resources", {}).get("core", {})
    search = data.get("resources", {}).get("search", {})
    return {
        "core": {
            "limit": core.get("limit"),
            "used": core.get("used"),
            "remaining": core.get("remaining"),
            "reset_at": core.get("reset"),
        },
        "search": {
            "limit": search.get("limit"),
            "used": search.get("used"),
            "remaining": search.get("remaining"),
        },
    }


def format_repo(repo: dict, detailed: bool = False) -> dict:
    """Format a repository object."""
    base = {
        "id": repo.get("id"),
        "name": repo.get("name"),
        "full_name": repo.get("full_name"),
        "description": repo.get("description"),
        "html_url": repo.get("html_url"),
        "private": repo.get("private"),
        "fork": repo.get("fork"),
        "stars": repo.get("stargazers_count"),
        "forks": repo.get("forks_count"),
        "open_issues": repo.get("open_issues_count"),
        "language": repo.get("language"),
        "default_branch": repo.get("default_branch"),
        "updated_at": repo.get("updated_at"),
        "created_at": repo.get("created_at"),
    }
    if detailed:
        base.update(
            {
                "clone_url": repo.get("clone_url"),
                "ssh_url": repo.get("ssh_url"),
                "size_kb": repo.get("size"),
                "watchers": repo.get("watchers_count"),
                "topics": repo.get("topics", []),
                "license": repo.get("license", {}).get("name") if repo.get("license") else None,
                "has_issues": repo.get("has_issues"),
                "has_wiki": repo.get("has_wiki"),
                "pushed_at": repo.get("pushed_at"),
                "owner": {
                    "login": repo.get("owner", {}).get("login"),
                    "avatar_url": repo.get("owner", {}).get("avatar_url"),
                    "html_url": repo.get("owner", {}).get("html_url"),
                },
            }
        )
    return base


def format_repos(repos: list) -> list:
    """Format a list of repositories."""
    return [format_repo(r) for r in repos]


def format_issue(issue: dict, detailed: bool = False) -> dict:
    """Format a GitHub issue."""
    base = {
        "number": issue.get("number"),
        "title": issue.get("title"),
        "state": issue.get("state"),
        "html_url": issue.get("html_url"),
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "labels": [label.get("name") for label in issue.get("labels", [])],
        "author": issue.get("user", {}).get("login"),
        "comments": issue.get("comments"),
    }
    if detailed:
        base.update(
            {
                "body": issue.get("body"),
                "closed_at": issue.get("closed_at"),
                "assignees": [a.get("login") for a in issue.get("assignees", [])],
                "milestone": issue.get("milestone", {}).get("title") if issue.get("milestone") else None,
            }
        )
    return base


def format_issues(issues: list) -> list:
    """Format a list of issues."""
    return [format_issue(i) for i in issues]


def format_commit(commit: dict, detailed: bool = False) -> dict:
    """Format a GitHub commit."""
    commit_data = commit.get("commit", {})
    author = commit_data.get("author", {})
    committer = commit_data.get("committer", {})
    gh_author = commit.get("author") or {}

    base = {
        "sha": commit.get("sha"),
        "short_sha": commit.get("sha", "")[:7],
        "message": commit_data.get("message", "").split("\n")[0],
        "author": {
            "name": author.get("name"),
            "email": author.get("email"),
            "date": author.get("date"),
            "login": gh_author.get("login"),
            "avatar_url": gh_author.get("avatar_url"),
        },
        "html_url": commit.get("html_url"),
        "committed_at": committer.get("date"),
    }
    if detailed:
        base.update(
            {
                "full_message": commit_data.get("message"),
                "stats": commit.get("stats", {}),
                "files_changed": [
                    {
                        "filename": f.get("filename"),
                        "status": f.get("status"),
                        "additions": f.get("additions"),
                        "deletions": f.get("deletions"),
                    }
                    for f in commit.get("files", [])
                ],
                "parents": [p.get("sha")[:7] for p in commit.get("parents", [])],
            }
        )
    return base


def format_commits(commits: list) -> list:
    """Format a list of commits."""
    return [format_commit(c) for c in commits]


def format_pull_request(pr: dict, detailed: bool = False) -> dict:
    """Format a GitHub pull request."""
    base = {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "state": pr.get("state"),
        "draft": pr.get("draft"),
        "html_url": pr.get("html_url"),
        "head": pr.get("head", {}).get("ref"),
        "base": pr.get("base", {}).get("ref"),
        "author": pr.get("user", {}).get("login"),
        "created_at": pr.get("created_at"),
        "updated_at": pr.get("updated_at"),
        "merged": pr.get("merged"),
        "merged_at": pr.get("merged_at"),
        "labels": [label.get("name") for label in pr.get("labels", [])],
        "comments": pr.get("comments"),
        "commits": pr.get("commits"),
        "additions": pr.get("additions"),
        "deletions": pr.get("deletions"),
    }
    if detailed:
        base.update(
            {
                "body": pr.get("body"),
                "assignees": [a.get("login") for a in pr.get("assignees", [])],
                "reviewers": [r.get("login") for r in pr.get("requested_reviewers", [])],
                "mergeable": pr.get("mergeable"),
                "changed_files": pr.get("changed_files"),
                "closed_at": pr.get("closed_at"),
                "merge_commit_sha": pr.get("merge_commit_sha"),
            }
        )
    return base


def format_pull_requests(prs: list) -> list:
    """Format a list of pull requests."""
    return [format_pull_request(p) for p in prs]
