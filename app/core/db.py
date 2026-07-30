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
        "CREATE INDEX IF NOT EXISTS ix_users_trial_ends_at ON users (trial_ends_at)",
        "CREATE INDEX IF NOT EXISTS ix_users_referral_lookup ON users (referral_id, referral_status)",
    )

    for statement in statements:
        await conn.exec_driver_sql(statement)


async def _get_sqlite_table_columns(conn, table_name: str) -> set[str]:
    result = await conn.exec_driver_sql(f"PRAGMA table_info({table_name})")
    return {row[1] for row in result.fetchall()}


async def _upgrade_sqlite_users_schema(conn) -> None:
    columns = await _get_sqlite_table_columns(conn, "users")
    alter_statements: list[str] = []

    if "referral_status" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN referral_status VARCHAR")
    if "referred_at" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN referred_at DATETIME")
    if "lifetime_access" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN lifetime_access BOOLEAN DEFAULT 0")
    if "lifetime_activated_at" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN lifetime_activated_at DATETIME")
    if "trial_ends_at" not in columns:
        alter_statements.append("ALTER TABLE users ADD COLUMN trial_ends_at DATETIME")

    for statement in alter_statements:
        await conn.exec_driver_sql(statement)

    await conn.exec_driver_sql(
        "UPDATE users "
        "SET referral_status = 'active' "
        "WHERE referral_id IS NOT NULL AND (referral_status IS NULL OR referral_status = '')"
    )
    await conn.exec_driver_sql(
        "UPDATE users "
        "SET referred_at = COALESCE(referred_at, create_at) "
        "WHERE referral_id IS NOT NULL AND referred_at IS NULL"
    )
    await conn.exec_driver_sql(
        "UPDATE users "
        "SET lifetime_access = COALESCE(lifetime_access, 0)"
    )
    await conn.exec_driver_sql(
        "UPDATE users "
        "SET trial_ends_at = CASE "
        "WHEN trial_ends_at IS NOT NULL THEN trial_ends_at "
        "ELSE datetime("
        "COALESCE(create_at, CURRENT_TIMESTAMP), "
        "'+' || ("
        f"{int(settings.TRIAL_PERIOD_HOURS)} + ("
        "SELECT COUNT(*) * "
        f"{int(settings.REFERRAL_BONUS_HOURS)} "
        "FROM users AS invited "
        "WHERE invited.referral_id = users.tgID "
        "AND invited.referral_status = 'active'"
        ")"
        ") || ' hours'"
        ") "
        "END"
    )


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
            await _upgrade_sqlite_users_schema(conn)
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
