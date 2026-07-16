from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.models.repository import Repository, RepositoryFile, RepositoryAnalysis
from app.services.openai_service import OpenAIService
from app.services.embedding_service import EmbeddingService
from app.prompts.analysis_prompts import (
    OVERVIEW_PROMPT, ARCHITECTURE_PROMPT, FOLDER_EXPLORER_PROMPT,
    API_DOCUMENTATION_PROMPT, DATABASE_ANALYSIS_PROMPT,
    MERMAID_DIAGRAM_PROMPT, README_GENERATOR_PROMPT,
    SUGGESTIONS_PROMPT,
)


class AnalysisService:
    def __init__(self, db: AsyncSession, openai_service: OpenAIService, embedding_service: EmbeddingService):
        self.db = db
        self.openai = openai_service
        self.embedding = embedding_service

    async def analyze_repository(self, repository_id: int) -> RepositoryAnalysis:
        repo = await self.db.execute(select(Repository).where(Repository.id == repository_id))
        repo = repo.scalar_one_or_none()
        if not repo:
            raise ValueError("Repository not found")

        files = await self.db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
        files = list(files.scalars().all())

        logger.info(f"Analyzing repository {repo.repo_name} with {len(files)} files")
        repo.status = "analyzing"
        await self.db.commit()

        project_summary = self._build_project_summary(files)

        overview = await self._generate_section(OVERVIEW_PROMPT, project_summary, repo.repo_name)
        architecture = await self._generate_section(ARCHITECTURE_PROMPT, project_summary, repo.repo_name)
        folder_summary = await self._generate_section(FOLDER_EXPLORER_PROMPT, project_summary, repo.repo_name)
        api_summary = await self._generate_section(API_DOCUMENTATION_PROMPT, project_summary, repo.repo_name)
        database_summary = await self._generate_section(DATABASE_ANALYSIS_PROMPT, project_summary, repo.repo_name)
        mermaid_diagram = await self._generate_section(MERMAID_DIAGRAM_PROMPT, project_summary, repo.repo_name)
        readme = await self._generate_section(README_GENERATOR_PROMPT, project_summary, repo.repo_name)
        suggestions = await self._generate_section(SUGGESTIONS_PROMPT, project_summary, repo.repo_name)

        existing = await self.db.execute(
            select(RepositoryAnalysis).where(RepositoryAnalysis.repository_id == repository_id)
        )
        existing_analysis = existing.scalar_one_or_none()

        if existing_analysis:
            existing_analysis.overview = overview
            existing_analysis.architecture = architecture
            existing_analysis.folder_summary = folder_summary
            existing_analysis.api_summary = api_summary
            existing_analysis.database_summary = database_summary
            existing_analysis.deployment_summary = ""
            existing_analysis.dependencies = {}
            existing_analysis.readme = readme
            existing_analysis.mermaid_diagram = mermaid_diagram
            existing_analysis.suggestions = suggestions
            analysis = existing_analysis
        else:
            analysis = RepositoryAnalysis(
                repository_id=repository_id,
                overview=overview,
                architecture=architecture,
                folder_summary=folder_summary,
                api_summary=api_summary,
                database_summary=database_summary,
                deployment_summary="",
                dependencies={},
                readme=readme,
                mermaid_diagram=mermaid_diagram,
                suggestions=suggestions,
            )
            self.db.add(analysis)

        repo.status = "completed"
        await self.db.commit()
        await self.db.refresh(analysis)
        logger.info(f"Analysis complete for {repo.repo_name}")
        return analysis

    def _build_project_summary(self, files: List[RepositoryFile]) -> str:
        summary_parts = []
        for f in files:
            ext = f.path.split(".")[-1] if "." in f.path else ""
            summary_parts.append(f"{f.path} (Language: {ext}, Size: {f.size} bytes)")
        return "\n".join(summary_parts[:500])

    async def _generate_section(self, prompt_template: str, project_summary: str, repo_name: str) -> str:
        try:
            user_prompt = f"Repository: {repo_name}\n\nFiles:\n{project_summary}"
            return await self.openai.generate_completion(prompt_template, user_prompt, max_tokens=4096)
        except Exception as e:
            logger.error(f"Failed to generate section: {e}")
            return f"Analysis section could not be generated due to: {str(e)}"
