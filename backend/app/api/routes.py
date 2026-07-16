from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session_factory
from app.models.repository import RepositoryAnalysis, ChatHistory, Repository
from app.schemas.repository import (
    RepositoryCreate, RepositoryResponse, RepositoryFileResponse,
    RepositoryAnalysisResponse, ChatRequest, ChatResponse, ChatHistoryResponse,
)
from app.services.repository_service import RepositoryService
from app.services.analysis_service import AnalysisService
from app.services.embedding_service import EmbeddingService
from app.services.openai_service import OpenAIService
from loguru import logger

from sqlalchemy import select

router = APIRouter()
openai_service = OpenAIService()


@router.post("/repositories/analyze", response_model=RepositoryResponse)
async def analyze_repository(
    data: RepositoryCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    repo_service = RepositoryService(db)

    try:
        owner, repo_name = repo_service._parse_github_url(data.github_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    existing = await repo_service.find_by_owner_repo(owner, repo_name)
    if existing:
        if existing.status == "completed":
            return RepositoryResponse(
                id=existing.id,
                github_url=existing.github_url,
                owner=existing.owner,
                repo_name=existing.repo_name,
                branch=existing.branch,
                language=existing.language,
                status=existing.status,
                created_at=existing.created_at,
            )
        elif existing.status == "failed" or existing.status == "pending":
            await repo_service.reset_for_reanalysis(existing.id)
            background_tasks.add_task(_run_analysis_pipeline, existing.id, db)
            return RepositoryResponse(
                id=existing.id,
                github_url=existing.github_url,
                owner=existing.owner,
                repo_name=existing.repo_name,
                branch=existing.branch,
                language=existing.language,
                status="pending",
                created_at=existing.created_at,
            )
        else:
            return RepositoryResponse(
                id=existing.id,
                github_url=existing.github_url,
                owner=existing.owner,
                repo_name=existing.repo_name,
                branch=existing.branch,
                language=existing.language,
                status=existing.status,
                created_at=existing.created_at,
            )

    try:
        repo = await repo_service.create_repository(
            data.github_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    background_tasks.add_task(
        _run_analysis_pipeline,
        repo.id, db,
    )
    return RepositoryResponse(
        id=repo.id,
        github_url=repo.github_url,
        owner=repo.owner,
        repo_name=repo.repo_name,
        branch=repo.branch,
        language=repo.language,
        status=repo.status,
        created_at=repo.created_at,
    )


async def _run_analysis_pipeline(repo_id: int, db: AsyncSession):
    async with async_session_factory() as session:
        try:
            repo_service = RepositoryService(session)
            repo = await repo_service.get_repository(repo_id)
            if not repo:
                return

            await repo_service.update_status(repo_id, "cloning")
            clone_dir = await repo_service.clone_repository(repo)

            await repo_service.update_status(repo_id, "indexing")
            await repo_service.index_files(repo, clone_dir)

            await repo_service.update_status(repo_id, "embedding")
            embedding_service = EmbeddingService(session, openai_service)
            await embedding_service.generate_and_store_embeddings(repo_id)

            await repo_service.update_status(repo_id, "analyzing")
            analysis_service = AnalysisService(session, openai_service, embedding_service)
            await analysis_service.analyze_repository(repo_id)

            await repo_service.update_status(repo_id, "completed")
        except Exception as e:
            logger.error(f"Analysis pipeline failed: {e}")
            try:
                await repo_service.update_status(repo_id, "failed")
            except Exception:
                pass


@router.get("/repositories/{repo_id}", response_model=RepositoryResponse)
async def get_repository(repo_id: int, db: AsyncSession = Depends(get_db)):
    repo_service = RepositoryService(db)
    repo = await repo_service.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return RepositoryResponse(
        id=repo.id,
        github_url=repo.github_url,
        owner=repo.owner,
        repo_name=repo.repo_name,
        branch=repo.branch,
        language=repo.language,
        status=repo.status,
        created_at=repo.created_at,
    )


@router.get("/repositories/{repo_id}/analysis", response_model=RepositoryAnalysisResponse)
async def get_analysis(repo_id: int, db: AsyncSession = Depends(get_db)):
    repo_service = RepositoryService(db)
    repo = await repo_service.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    analysis = await repo_service.get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return RepositoryAnalysisResponse(
        id=repo_id,
        overview=analysis["overview"],
        architecture=analysis["architecture"],
        folder_summary=analysis["folder_summary"],
        api_summary=analysis["api_summary"],
        database_summary=analysis["database_summary"],
        deployment_summary=analysis["deployment_summary"],
        dependencies=analysis["dependencies"],
        readme=analysis["readme"],
        mermaid_diagram=analysis["mermaid_diagram"],
        suggestions=analysis["suggestions"],
    )


@router.get("/repositories/{repo_id}/overview")
async def get_overview(repo_id: int, db: AsyncSession = Depends(get_db)):
    repo_service = RepositoryService(db)
    analysis = await repo_service.get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"overview": analysis["overview"]}


@router.get("/repositories/{repo_id}/architecture")
async def get_architecture(repo_id: int, db: AsyncSession = Depends(get_db)):
    repo_service = RepositoryService(db)
    analysis = await repo_service.get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"architecture": analysis["architecture"]}


@router.get("/repositories/{repo_id}/folders")
async def get_folders(repo_id: int, db: AsyncSession = Depends(get_db)):
    repo_service = RepositoryService(db)
    analysis = await repo_service.get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"folder_summary": analysis["folder_summary"]}


@router.get("/repositories/{repo_id}/api")
async def get_api_docs(repo_id: int, db: AsyncSession = Depends(get_db)):
    repo_service = RepositoryService(db)
    analysis = await repo_service.get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"api_summary": analysis["api_summary"]}


@router.get("/repositories/{repo_id}/database")
async def get_database(repo_id: int, db: AsyncSession = Depends(get_db)):
    repo_service = RepositoryService(db)
    analysis = await repo_service.get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"database_summary": analysis["database_summary"]}


@router.get("/repositories/{repo_id}/diagram")
async def get_diagram(repo_id: int, db: AsyncSession = Depends(get_db)):
    repo_service = RepositoryService(db)
    analysis = await repo_service.get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"mermaid_diagram": analysis["mermaid_diagram"]}


@router.get("/repositories/{repo_id}/readme")
async def get_readme(repo_id: int, db: AsyncSession = Depends(get_db)):
    repo_service = RepositoryService(db)
    analysis = await repo_service.get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"readme": analysis["readme"]}


@router.get("/repositories/{repo_id}/suggestions")
async def get_suggestions(repo_id: int, db: AsyncSession = Depends(get_db)):
    repo_service = RepositoryService(db)
    analysis = await repo_service.get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"suggestions": analysis["suggestions"]}


@router.get("/repositories/{repo_id}/files", response_model=list[RepositoryFileResponse])
async def get_files(repo_id: int, db: AsyncSession = Depends(get_db)):
    repo_service = RepositoryService(db)
    return await repo_service.get_files_list(repo_id)


@router.post("/repositories/{repo_id}/chat", response_model=ChatResponse)
async def chat(
    repo_id: int,
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    repo_service = RepositoryService(db)
    repo = await repo_service.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    embedding_service = EmbeddingService(db, openai_service)
    context = await embedding_service.get_context_for_chat(repo_id, data.question)

    result = await db.execute(
        select(ChatHistory).where(ChatHistory.repository_id == repo_id).order_by(ChatHistory.timestamp.asc())
    )
    history = [
        {"question": h.question, "answer": h.answer}
        for h in result.scalars().all()
    ]

    answer = await openai_service.chat_with_context(
        data.question, context, repo.repo_name, history
    )

    chat_entry = ChatHistory(
        repository_id=repo_id,
        question=data.question,
        answer=answer,
    )
    db.add(chat_entry)
    await db.commit()

    return ChatResponse(answer=answer)


@router.get("/repositories/{repo_id}/chat-history", response_model=list[ChatHistoryResponse])
async def get_chat_history(repo_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatHistory)
        .where(ChatHistory.repository_id == repo_id)
        .order_by(ChatHistory.timestamp.asc())
    )
    return result.scalars().all()
