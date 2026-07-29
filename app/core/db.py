from contextlib import asynccontextmanager

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

Base = declarative_base()

engine = create_async_engine(
    settings.DATABASE_URL,
    future=True,
    connect_args={"timeout": 30},
)


if engine.url.get_backend_name() == "sqlite":
    @event.listens_for(engine.sync_engine, "connect")
    def _configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


async def _optimize_sqlite_schema(conn) -> None:
    statements = (
        """
        DELETE FROM chats
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM chats
            GROUP BY chat_id, user_id
        )
        """,
        """
        DELETE FROM messages
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM messages
            GROUP BY msg_id, from_user, to_user
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_messages_create_at ON messages (create_at)",
        (
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_messages_lookup "
            "ON messages (msg_id, from_user, to_user)"
        ),
        "CREATE INDEX IF NOT EXISTS ix_chats_chat_id ON chats (chat_id)",
        "CREATE INDEX IF NOT EXISTS ix_chats_user_id ON chats (user_id)",
        (
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_chats_chat_user "
            "ON chats (chat_id, user_id)"
        ),
        "CREATE INDEX IF NOT EXISTS ix_users_connection_id ON users (connection_id)",
        "CREATE INDEX IF NOT EXISTS ix_users_ref_code ON users (ref_code)",
    )

    for statement in statements:
        await conn.exec_driver_sql(statement)


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
        if engine.url.get_backend_name() == "sqlite":
            await _optimize_sqlite_schema(conn)


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
