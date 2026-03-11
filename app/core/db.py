from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

Base = declarative_base()

engine = create_async_engine(settings.DATABASE_URL, future=True)


def async_session_generator():
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    # Ensure all ORM models are imported before create_all.
    from app.models.chat import Chat  # noqa: F401
    from app.models.message import Message  # noqa: F401
    from app.models.subscription import Subscription  # noqa: F401
    from app.models.user import User  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session():
    session = None
    try:
        async_session = async_session_generator()
        async with async_session() as session:
            yield session
    except Exception:
        if session is not None:
            await session.rollback()
        raise
    finally:
        if session is not None:
            await session.close()
