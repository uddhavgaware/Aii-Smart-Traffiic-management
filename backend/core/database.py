"""
Async SQLAlchemy engine, session factory, and declarative Base.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# Create async engine with connection pool settings (SQLite skips pool_size/overflow)
_engine_kwargs: dict = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}
if not settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update({
        "pool_size": settings.DB_POOL_MIN_SIZE,
        "max_overflow": settings.DB_POOL_MAX_SIZE - settings.DB_POOL_MIN_SIZE,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": 3600,
    })

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def init_db() -> None:
    """Create all tables (used in development; migrations handle production)."""
    async with engine.begin() as conn:
        # Import all models to ensure they are registered with Base
        from models import user, camera, traffic_event, signal_event  # noqa: F401
        from models import emergency_event, system_event  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_initialized", tables=list(Base.metadata.tables.keys()))


async def close_db() -> None:
    """Dispose the engine connection pool."""
    await engine.dispose()
    logger.info("database_connection_pool_closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for use outside of FastAPI dependency injection."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
