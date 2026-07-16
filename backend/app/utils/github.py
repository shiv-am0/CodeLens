import re
from typing import Optional
import httpx
from loguru import logger

from app.core.config import settings


def parse_github_url(url: str) -> tuple[str, str]:
    url = url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    pattern = r"(?:https?://(?:www\.)?github\.com/|git@github\.com:)([^/]+)/([^/]+)"
    match = re.match(pattern, url)
    if not match:
        raise ValueError(f"Invalid GitHub URL: {url}")
    return match.group(1), match.group(2)


async def check_repo_exists(owner: str, repo_name: str) -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if settings.github_token:
        headers["Authorization"] = f"token {settings.github_token}"

    url = f"https://api.github.com/repos/{owner}/{repo_name}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=30)

    if response.status_code == 404:
        raise ValueError(f"Repository {owner}/{repo_name} not found")
    if response.status_code == 403:
        raise ValueError("GitHub API rate limit exceeded. Try adding a GITHUB_TOKEN.")

    response.raise_for_status()
    data = response.json()

    if data.get("private"):
        raise ValueError("Private repositories are not supported")

    return {
        "owner": data["owner"]["login"],
        "repo_name": data["name"],
        "description": data.get("description", ""),
        "language": data.get("language"),
        "default_branch": data.get("default_branch", "main"),
        "size": data.get("size", 0),
    }


async def validate_github_url(url: str) -> dict:
    owner, repo_name = parse_github_url(url)
    repo_info = await check_repo_exists(owner, repo_name)

    size_mb = repo_info["size"] / 1024
    if size_mb > settings.max_repo_size_mb:
        raise ValueError(
            f"Repository too large ({size_mb:.1f}MB). Maximum is {settings.max_repo_size_mb}MB."
        )

    return repo_info
