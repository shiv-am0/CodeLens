import itertools
import time

from openai import AsyncOpenAI
from loguru import logger
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.services.master_key_store import master_key_store


class KeyManager:
    def __init__(self):
        self._keys: list[str] = []
        self._cycle = itertools.cycle([])
        self._last_refresh = 0.0
        self._refresh_interval = 300
        self._fallback_key = settings.openai_api_key

    def initialize(self) -> None:
        master_key_store.load_existing()
        self._fallback_key = settings.openai_api_key
        self.invalidate()

    def init_encryption(self, key: str, fallback_key: str = "") -> None:
        """Backward-compatible entry point for the existing admin interface."""
        if key:
            master_key_store.initialize(key)
        self._fallback_key = fallback_key
        self.invalidate()

    def encrypt(self, plaintext: str) -> str:
        if not master_key_store.is_initialized:
            master_key_store.initialize()
        return master_key_store.encrypt(plaintext)

    def decrypt(self, ciphertext: str) -> str:
        return master_key_store.decrypt(ciphertext)

    def invalidate(self) -> None:
        self._last_refresh = 0.0
        self._keys = []
        self._cycle = itertools.cycle([])

    async def _refresh(self) -> None:
        from app.models.api_key import ApiKey

        async with async_session_factory() as db:
            result = await db.execute(
                select(ApiKey)
                .where(ApiKey.is_active.is_(True))
                .order_by(ApiKey.created_at)
            )
            rows = result.scalars().all()

        decrypted = []
        for row in rows:
            try:
                decrypted.append(self.decrypt(row.key_encrypted))
            except Exception:
                logger.warning("Skipping an active API key that could not be decrypted")
        if not decrypted and self._fallback_key:
            decrypted = [self._fallback_key]

        self._keys = decrypted
        self._cycle = itertools.cycle(decrypted)
        self._last_refresh = time.monotonic()

    async def get_next_key(self) -> str | None:
        now = time.monotonic()
        if (now - self._last_refresh) > self._refresh_interval or not self._keys:
            await self._refresh()
        if not self._keys:
            return None
        return next(self._cycle)

    async def get_client(self) -> AsyncOpenAI | None:
        key = await self.get_next_key()
        if not key:
            return None
        return AsyncOpenAI(api_key=key)

    async def load_keys_sync(self, db_session=None):
        from app.models.api_key import ApiKey

        if db_session:
            result = await db_session.execute(select(ApiKey).order_by(ApiKey.created_at))
            return result.scalars().all()
        async with async_session_factory() as db:
            result = await db.execute(select(ApiKey).order_by(ApiKey.created_at))
            return result.scalars().all()


key_manager = KeyManager()
