from sqlalchemy import distinct, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models.chat import Chat
from app.core.db import get_session


class CRUDChat:
    async def get_chat_by_chat_id(self, chat_id: str) -> Chat | None:
        async with get_session() as session:
            result = await session.execute(
                select(Chat).where(Chat.chat_id == chat_id).order_by(Chat.id.desc()).limit(1)
            )
            return result.scalar_one_or_none()

    async def ensure_chat_exists(self, chat_id: str, user_id: str) -> None:
        """
        Если строки в chats нет — создаём со status=True.
        """
        async with get_session() as session:
            stmt = (
                sqlite_insert(Chat)
                .values(
                    chat_id=chat_id,
                    user_id=user_id,
                    status=True,
                )
                .on_conflict_do_nothing(index_elements=["chat_id", "user_id"])
            )
            await session.execute(stmt)
            await session.commit()

    async def get_active_user_ids_by_chat_id(self, chat_id: str) -> list[str]:
        async with get_session() as session:
            result = await session.execute(
                select(distinct(Chat.user_id)).where(
                    Chat.chat_id == chat_id,
                    Chat.status.is_(True),
                )
            )
            return [str(user_id) for user_id in result.scalars().all() if user_id is not None]

    async def activate_all_by_user_id(self, user_id: str) -> None:
        """
        Обновляет статус всех чатов, связанных с переданным user_id.
        """
        async with get_session() as session:
            # Обновляем все чаты, где user_id совпадает
            stmt = update(Chat).where(Chat.user_id == user_id).values(status=True)
            await session.execute(stmt)
            await session.commit()

    async def deactivate_all_by_user_id(self, user_id: str) -> None:
        """
        Отключает все чаты пользователя (устанавливает status = False),
        если бот был удалён из бизнес-аккаунта.
        """
        async with get_session() as session:
            stmt = update(Chat).where(Chat.user_id == user_id).values(status=False)
            await session.execute(stmt)
            await session.commit()

    async def is_chat_registered(self, chat_id: str) -> bool:
        """
        Проверка: зарегистрирован ли чат с данным chat_id.
        """
        async with get_session() as session:
            result = await session.execute(select(Chat).where(Chat.chat_id == chat_id))
            return result.scalar_one_or_none() is not None

    async def register_chat(self, chat_id: str, user_id: str, title: str | None = None):
        """
        Добавляет новый чат, если он ещё не зарегистрирован.
        """
        async with get_session() as session:
            result = await session.execute(select(Chat).where(Chat.chat_id == chat_id))
            existing_chat = result.scalar_one_or_none()
            if existing_chat:
                return

            from datetime import datetime

            now = datetime.utcnow()

            chat = Chat(
                chat_id=chat_id,
                user_id=user_id,
                status=False,
                create_at=now,
            )
            session.add(chat)
            await session.commit()
            await session.refresh(chat)


crud_chat = CRUDChat()
