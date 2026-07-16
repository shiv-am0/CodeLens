from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class RepositoryCreate(BaseModel):
    github_url: str


class RepositoryResponse(BaseModel):
    id: int
    github_url: str
    owner: str
    repo_name: str
    branch: str
    language: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class RepositoryFileResponse(BaseModel):
    id: int
    path: str
    size: int

    class Config:
        from_attributes = True


class RepositoryAnalysisResponse(BaseModel):
    id: Optional[int] = None
    overview: Optional[str] = None
    architecture: Optional[str] = None
    folder_summary: Optional[str] = None
    api_summary: Optional[str] = None
    database_summary: Optional[str] = None
    deployment_summary: Optional[str] = None
    dependencies: Optional[dict] = None
    readme: Optional[str] = None
    mermaid_diagram: Optional[str] = None
    suggestions: Optional[str] = None

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str


class ChatHistoryResponse(BaseModel):
    id: int
    question: str
    answer: str
    timestamp: datetime

    class Config:
        from_attributes = True
