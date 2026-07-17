from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.core.config import settings


def _sanitize_db_url(url: str) -> str:
    """Convert URL to psycopg format and strip unsupported params for PgBouncer."""
    # Convert asyncpg prefix to psycopg if needed
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    for key in ("pgbouncer", "connection_limit"):
        params.pop(key, None)
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


engine = create_async_engine(
    _sanitize_db_url(settings.database_url),
    echo=settings.debug,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
