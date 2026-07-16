from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "CodeLens"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/codelens"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/codelens"
    llm_provider: str = "openai"

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dim: int = 1536

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_chat_model: str = "llama3.1:8b"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_embedding_dim: int = 768

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    github_token: Optional[str] = None

    max_repo_size_mb: int = 100
    max_files: int = 3000
    analysis_timeout_seconds: int = 300

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
