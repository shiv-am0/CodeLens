import time
import itertools
from cryptography.fernet import Fernet
from sqlalchemy import select
from openai import AsyncOpenAI
from app.core.database import async_session_factory


class KeyManager:
    def __init__(self):
        self._keys = []
        self._cycle = itertools.cycle([])
        self._last_refresh = 0
        self._refresh_interval = 300
        self._fernet = None

    def init_encryption(self, key: str, fallback_key: str = ""):
        key_bytes = key.encode() if isinstance(key, str) else key
        self._fernet = Fernet(key_bytes)
        if fallback_key:
            self._keys = [fallback_key]
            self._cycle = itertools.cycle([fallback_key])

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()

    async def _refresh(self):
        from app.models.api_key import ApiKey

        async with async_session_factory() as db:
            result = await db.execute(
                select(ApiKey).where(ApiKey.is_active == True).order_by(ApiKey.created_at)
            )
            rows = result.scalars().all()
            decrypted = [self.decrypt(r.key_encrypted) for r in rows]
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
            result = await db_session.execute(
                select(ApiKey).order_by(ApiKey.created_at)
            )
            return result.scalars().all()
        async with async_session_factory() as db:
            result = await db.execute(
                select(ApiKey).order_by(ApiKey.created_at)
            )
            return result.scalars().all()


key_manager = KeyManager()
