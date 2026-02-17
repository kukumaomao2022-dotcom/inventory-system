from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy import create_engine

from app.core.config import settings


class Base(DeclarativeBase):
    pass


async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT.lower() == "dev",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    echo=settings.ENVIRONMENT.lower() == "dev",
    pool_pre_ping=True,
)

SyncSessionFactory = sessionmaker(
    sync_engine,
    class_=Session,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


def get_sync_session() -> Session:
    with SyncSessionFactory() as session:
        yield session
