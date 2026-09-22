import time
from dataclasses import dataclass

from openai import AsyncOpenAI
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.ai_configuration import AIConfiguration
from app.models.api_key import ApiKey
from app.schemas.ai_configuration import AIConfigurationResponse, AIConfigurationUpdate
from app.services.key_manager import key_manager
from app.services.master_key_store import MasterKeyError, master_key_store


SUPPORTED_CHAT_MODELS = ["gpt-4o-mini", "gpt-4o"]


class AIConfigurationRequiredError(RuntimeError):
    def __init__(self, missing: list[str] | None = None):
        super().__init__("AI service is temporarily unavailable")
        self.missing = missing or ["api_key"]

    def as_detail(self) -> dict:
        return {
            "code": "AI_CONFIGURATION_REQUIRED",
            "message": "AI service is temporarily unavailable. Please contact the site owner.",
            "missing": self.missing,
        }


class AIConfigurationValidationError(ValueError):
    pass


@dataclass(frozen=True)
class RuntimeAIConfiguration:
    provider: str
    chat_model: str
    embedding_model: str


class RuntimeAIConfigurationCache:
    def __init__(self):
        self._value: RuntimeAIConfiguration | None = None
        self._loaded_at = 0.0
        self._ttl_seconds = 60

    def invalidate(self) -> None:
        self._value = None
        self._loaded_at = 0.0

    async def get(self) -> RuntimeAIConfiguration:
        now = time.monotonic()
        if self._value and now - self._loaded_at < self._ttl_seconds:
            return self._value

        async with async_session_factory() as db:
            configuration = await db.get(AIConfiguration, 1)

        self._value = RuntimeAIConfiguration(
            provider=configuration.provider if configuration else settings.llm_provider,
            chat_model=configuration.chat_model if configuration else settings.openai_chat_model,
            embedding_model=(
                configuration.embedding_model
                if configuration
                else settings.openai_embedding_model
            ),
        )
        self._loaded_at = now
        return self._value


runtime_ai_configuration = RuntimeAIConfigurationCache()


async def validate_stored_api_key() -> None:
    """Fail startup when a persisted key cannot be decrypted by this deployment."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(ApiKey)
            .where(ApiKey.is_active.is_(True))
            .order_by(ApiKey.created_at.desc())
            .limit(1)
        )
        active_key = result.scalar_one_or_none()

    if active_key is None:
        return
    if not master_key_store.load_existing():
        raise RuntimeError(
            "An encrypted OpenAI key exists, but no ENCRYPTION_KEY or persisted master key is available"
        )
    try:
        key_manager.decrypt(active_key.key_encrypted)
    except Exception as exc:
        fingerprint = master_key_store.fingerprint or "unknown"
        raise RuntimeError(
            "The active OpenAI key cannot be decrypted. Restore the original "
            f"ENCRYPTION_KEY (loaded fingerprint: {fingerprint})."
        ) from exc


class AIConfigurationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_status(self) -> AIConfigurationResponse:
        configuration = await self.db.get(AIConfiguration, 1)
        active_key = await self._get_active_key()
        environment_key_available = bool(settings.openai_api_key)
        encryption_initialized = master_key_store.load_existing()

        database_key_usable = False
        if active_key and encryption_initialized:
            try:
                database_key_usable = bool(key_manager.decrypt(active_key.key_encrypted))
            except Exception:
                database_key_usable = False

        api_key_configured = database_key_usable or environment_key_available
        chat_model = configuration.chat_model if configuration else settings.openai_chat_model
        embedding_model = (
            configuration.embedding_model
            if configuration
            else settings.openai_embedding_model
        )
        provider = configuration.provider if configuration else settings.llm_provider
        provider_configured = (
            bool(chat_model and embedding_model)
            if provider == "ollama"
            else provider == "openai" and api_key_configured and bool(chat_model)
        )
        configured = settings.ai_features_enabled and provider_configured

        return AIConfigurationResponse(
            provider=provider,
            configured=configured,
            api_key_configured=api_key_configured,
            chat_model=chat_model,
            embedding_model=embedding_model,
            encryption_initialized=encryption_initialized,
            supported_chat_models=SUPPORTED_CHAT_MODELS,
        )

    async def require_ready(self) -> None:
        status = await self.get_status()
        if status.configured:
            return

        missing: list[str] = []
        if not status.api_key_configured:
            missing.append("api_key")
        if not status.chat_model:
            missing.append("chat_model")
        raise AIConfigurationRequiredError(missing)

    async def save(self, update_data: AIConfigurationUpdate) -> AIConfigurationResponse:
        api_key = update_data.api_key.get_secret_value().strip() if update_data.api_key else None
        active_key = await self._get_active_key()

        if not api_key and not active_key and not settings.openai_api_key:
            raise AIConfigurationValidationError(
                "An OpenAI API key is required for initial setup"
            )

        validation_key = api_key
        if not validation_key and active_key:
            try:
                validation_key = key_manager.decrypt(active_key.key_encrypted)
            except Exception as exc:
                raise AIConfigurationValidationError(
                    "The stored API key cannot be decrypted"
                ) from exc
        if not validation_key:
            validation_key = settings.openai_api_key

        await self._validate_openai(
            validation_key,
            update_data.chat_model,
            settings.openai_embedding_model,
        )

        if api_key:
            try:
                master_key_store.initialize()
            except MasterKeyError as exc:
                raise AIConfigurationValidationError(str(exc)) from exc

        if api_key:
            encrypted_key = key_manager.encrypt(api_key)
            await self.db.execute(
                update(ApiKey)
                .where(ApiKey.is_active.is_(True))
                .values(is_active=False)
            )
            self.db.add(
                ApiKey(
                    name="Admin configuration",
                    key_encrypted=encrypted_key,
                    key_prefix=api_key[:8],
                    is_active=True,
                )
            )

        configuration = await self.db.get(AIConfiguration, 1)
        if configuration is None:
            configuration = AIConfiguration(
                id=1,
                provider="openai",
                chat_model=update_data.chat_model,
                embedding_model=settings.openai_embedding_model,
            )
            self.db.add(configuration)
        else:
            configuration.provider = "openai"
            configuration.chat_model = update_data.chat_model
            configuration.embedding_model = settings.openai_embedding_model

        await self.db.commit()
        key_manager.invalidate()
        runtime_ai_configuration.invalidate()
        return await self.get_status()

    async def _get_active_key(self) -> ApiKey | None:
        result = await self.db.execute(
            select(ApiKey)
            .where(ApiKey.is_active.is_(True))
            .order_by(ApiKey.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _validate_openai(
        self, api_key: str, chat_model: str, embedding_model: str
    ) -> None:
        client = AsyncOpenAI(api_key=api_key, timeout=20.0, max_retries=1)
        try:
            await client.models.retrieve(chat_model)
            await client.models.retrieve(embedding_model)
        except Exception as exc:
            raise AIConfigurationValidationError(
                "OpenAI rejected the API key or selected model"
            ) from exc
        finally:
            await client.close()
