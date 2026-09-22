from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "CodeLens"
    debug: bool = False
    app_environment: str = "development"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/codelens"
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

    allowed_origins: str = ""
    # ADMIN_PASSWORD is retained for local development only. Production must
    # use a bcrypt ADMIN_PASSWORD_HASH so the password itself is not stored.
    admin_password: str = ""
    admin_password_hash: str = ""
    admin_session_secret: str = ""
    admin_session_hours: int = 8
    encryption_key: str = ""
    master_key_path: str = "./data/master.key"
    github_token: Optional[str] = None

    max_repo_size_mb: int = 100
    max_files: int = 3000
    analysis_timeout_seconds: int = 300
    max_concurrent_analyses: int = 2
    analysis_requests_per_hour: int = 5
    chat_requests_per_minute: int = 30
    ai_max_output_tokens: int = 4096
    ai_features_enabled: bool = True

    @property
    def is_production(self) -> bool:
        return self.app_environment.lower() == "production"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()


def validate_security_settings() -> None:
    """Fail closed when production secrets are missing or obviously unsafe."""
    if not settings.is_production:
        return

    errors: list[str] = []
    if not settings.admin_password_hash:
        errors.append("ADMIN_PASSWORD_HASH is required in production")
    if len(settings.admin_session_secret) < 32:
        errors.append("ADMIN_SESSION_SECRET must contain at least 32 characters")
    if not settings.encryption_key:
        errors.append("ENCRYPTION_KEY is required in production")
    if settings.admin_password:
        errors.append("ADMIN_PASSWORD must not be set in production; use ADMIN_PASSWORD_HASH")
    if errors:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(errors))
