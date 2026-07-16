from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    github_url: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True, index=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False)
    branch: Mapped[str] = mapped_column(String(255), default="main")
    language: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="repositories")
    files = relationship("RepositoryFile", back_populates="repository", cascade="all, delete-orphan")
    analysis = relationship("RepositoryAnalysis", back_populates="repository", uselist=False, cascade="all, delete-orphan")
    chat_messages = relationship("ChatHistory", back_populates="repository", cascade="all, delete-orphan")


class RepositoryFile(Base):
    __tablename__ = "repository_files"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    size: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    embedding = mapped_column(Text, nullable=True)

    repository = relationship("Repository", back_populates="files")


class RepositoryAnalysis(Base):
    __tablename__ = "repository_analysis"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, unique=True)
    overview: Mapped[str] = mapped_column(Text, nullable=True)
    architecture: Mapped[str] = mapped_column(Text, nullable=True)
    folder_summary: Mapped[str] = mapped_column(Text, nullable=True)
    api_summary: Mapped[str] = mapped_column(Text, nullable=True)
    database_summary: Mapped[str] = mapped_column(Text, nullable=True)
    deployment_summary: Mapped[str] = mapped_column(Text, nullable=True)
    dependencies: Mapped[dict] = mapped_column(JSON, nullable=True)
    readme: Mapped[str] = mapped_column(Text, nullable=True)
    mermaid_diagram: Mapped[str] = mapped_column(Text, nullable=True)
    suggestions: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    repository = relationship("Repository", back_populates="analysis")


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    repository = relationship("Repository", back_populates="chat_messages")
