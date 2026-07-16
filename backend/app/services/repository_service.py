import os
import re
import asyncio
import shutil
from pathlib import Path
from typing import List, Optional, Set
from git import Repo, GitCommandError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger

from app.core.config import settings
from app.models.repository import Repository, RepositoryFile, RepositoryAnalysis
from app.utils.github import check_repo_exists


IGNORED_DIRS: Set[str] = {
    ".git", "node_modules", "dist", "build", "coverage",
    "__pycache__", "venv", ".venv", ".cache", ".next",
    ".turbo", "target", "vendor", ".eggs", "egg-info",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
}

BINARY_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac",
    ".pyc", ".pyo", ".pyd",
    ".ico", ".icns",
}

MAX_FILE_SIZE = 512 * 1024

META_FILES = {
    "README.md", "README.rst", "README.txt", "readme.md",
    "package.json", "requirements.txt", "Dockerfile",
    "docker-compose.yml", "docker-compose.yaml",
    "pyproject.toml", "go.mod", "Cargo.toml",
    "pom.xml", "build.gradle", "Makefile",
    "CMakeLists.txt", "composer.json", "Gemfile",
    "mix.exs", "Package.swift", "project.clj",
    "setup.py", "setup.cfg",
}


class RepositoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_repository(self, github_url: str) -> Repository:
        owner, repo_name = self._parse_github_url(github_url)

        branch = "main"
        language = None
        try:
            repo_info = await check_repo_exists(owner, repo_name)
            branch = repo_info.get("default_branch", "main")
            language = repo_info.get("language")
        except Exception:
            logger.warning(f"Could not detect default branch for {owner}/{repo_name}, defaulting to main")

        repo = Repository(
            github_url=github_url,
            owner=owner,
            repo_name=repo_name,
            branch=branch,
            language=language,
            status="pending",
        )
        self.db.add(repo)
        await self.db.commit()
        await self.db.refresh(repo)
        return repo

    def _parse_github_url(self, url: str) -> tuple:
        url = url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        match = re.match(r"(?:https?://(?:www\.)?github\.com/|git@github\.com:)([^/]+)/([^/]+)", url)
        if not match:
            raise ValueError(f"Invalid GitHub URL: {url}")
        return match.group(1), match.group(2)

    async def clone_repository(self, repo: Repository) -> Path:
        clone_dir = Path("/tmp/codelens") / f"{repo.owner}_{repo.repo_name}"
        if clone_dir.exists():
            shutil.rmtree(clone_dir)

        clone_url = f"https://github.com/{repo.owner}/{repo.repo_name}.git"
        if settings.github_token:
            clone_url = f"https://{settings.github_token}@github.com/{repo.owner}/{repo.repo_name}.git"

        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                Repo.clone_from(clone_url, clone_dir, depth=1)
                logger.info(f"Cloned {clone_url} to {clone_dir}")
                break
            except GitCommandError as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = 2 ** attempt * 2
                    logger.warning(f"Clone failed (attempt {attempt + 1}/{max_retries}), retrying in {wait}s: {e}")
                    await asyncio.sleep(wait)
                else:
                    raise RuntimeError(f"Failed to clone repository after {max_retries} attempts: {last_error}")

        repo.status = "cloned"
        await self.db.commit()
        return clone_dir

    async def index_files(self, repo: Repository, clone_dir: Path) -> List[RepositoryFile]:
        project_files = self._walk_directory(clone_dir)
        total_size = sum(f.stat().st_size for f in project_files)
        total_size_mb = total_size / (1024 * 1024)

        if total_size_mb > settings.max_repo_size_mb:
            raise RuntimeError(f"Repository exceeds maximum size of {settings.max_repo_size_mb}MB")

        if len(project_files) > settings.max_files:
            raise RuntimeError(f"Repository exceeds maximum file count of {settings.max_files}")

        meta_content = {}
        source_files = []

        for file_path in project_files:
            rel_path = str(file_path.relative_to(clone_dir))
            if file_path.name in META_FILES:
                try:
                    meta_content[file_path.name] = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass

            if file_path.stat().st_size > MAX_FILE_SIZE:
                continue

            if self._is_binary(rel_path):
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            source_files.append((rel_path, content, file_path.stat().st_size))

        logger.info(f"Indexed {len(source_files)} files from {repo.repo_name}")

        for rel_path, content, size in source_files:
            db_file = RepositoryFile(
                repository_id=repo.id,
                path=rel_path,
                size=size,
                content=content[:50000],
            )
            self.db.add(db_file)

        await self.db.commit()

        repo.status = "indexed"
        await self.db.commit()
        return await self._get_files(repo.id)

    def _walk_directory(self, path: Path) -> List[Path]:
        files = []
        try:
            for entry in path.rglob("*"):
                if entry.is_dir():
                    if entry.name in IGNORED_DIRS or entry.name.startswith("."):
                        continue
                if entry.is_file():
                    files.append(entry)
        except PermissionError:
            pass
        return files

    def _is_binary(self, path: str) -> bool:
        ext = Path(path).suffix.lower()
        return ext in BINARY_EXTENSIONS or any(part.startswith(".") for part in Path(path).parts)

    async def _get_files(self, repository_id: int) -> List[RepositoryFile]:
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        return list(result.scalars().all())

    async def find_by_owner_repo(self, owner: str, repo_name: str) -> Optional[Repository]:
        result = await self.db.execute(
            select(Repository).where(
                Repository.owner == owner,
                Repository.repo_name == repo_name,
            ).order_by(Repository.created_at.desc())
        )
        rows = result.scalars().all()
        if not rows:
            return None
        completed = [r for r in rows if r.status == "completed"]
        failed = [r for r in rows if r.status == "failed"]
        in_progress = [r for r in rows if r.status not in ("completed", "failed")]
        if completed:
            return completed[0]
        if in_progress:
            return in_progress[0]
        if failed:
            return failed[0]
        return rows[0]

    async def reset_for_reanalysis(self, repo_id: int):
        await self.db.execute(
            select(RepositoryAnalysis).where(RepositoryAnalysis.repository_id == repo_id)
        )
        analysis = (await self.db.execute(
            select(RepositoryAnalysis).where(RepositoryAnalysis.repository_id == repo_id)
        )).scalar_one_or_none()
        if analysis:
            await self.db.delete(analysis)

        files = (await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repo_id)
        )).scalars().all()
        for f in files:
            await self.db.delete(f)

        repo = await self.get_repository(repo_id)
        if repo:
            repo.status = "pending"
        await self.db.commit()

    async def get_repository(self, repo_id: int) -> Optional[Repository]:
        result = await self.db.execute(select(Repository).where(Repository.id == repo_id))
        return result.scalar_one_or_none()

    async def get_analysis(self, repo_id: int) -> Optional[dict]:
        result = await self.db.execute(
            select(RepositoryAnalysis).where(RepositoryAnalysis.repository_id == repo_id)
        )
        analysis = result.scalar_one_or_none()
        if not analysis:
            return None
        return {
            "overview": analysis.overview,
            "architecture": analysis.architecture,
            "folder_summary": analysis.folder_summary,
            "api_summary": analysis.api_summary,
            "database_summary": analysis.database_summary,
            "deployment_summary": analysis.deployment_summary,
            "dependencies": analysis.dependencies,
            "readme": analysis.readme,
            "mermaid_diagram": analysis.mermaid_diagram,
            "suggestions": analysis.suggestions,
        }

    async def get_files_list(self, repo_id: int) -> List[dict]:
        result = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repo_id).order_by(RepositoryFile.path)
        )
        return [{"id": f.id, "path": f.path, "size": f.size} for f in result.scalars().all()]

    async def update_status(self, repo_id: int, status: str):
        repo = await self.get_repository(repo_id)
        if repo:
            repo.status = status
            await self.db.commit()
