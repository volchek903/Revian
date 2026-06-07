from sqlalchemy import update, select
from app.models.chat import Chat
from app.core.db import get_session


class CRUDChat:
    async def get_chat_by_chat_id(self, chat_id: str) -> Chat | None:
        async with get_session() as session:
            result = await session.execute(select(Chat).where(Chat.chat_id == chat_id))
            return result.scalar_one_or_none()

    async def ensure_chat_exists(self, chat_id: str, user_id: str) -> None:
        """
        Если строки в chats нет — создаём со status=True.
        """
        async with get_session() as session:
            result = await session.execute(
                select(Chat).where(
                    Chat.chat_id == chat_id,
                    Chat.user_id == user_id,
                )
            )
            if not result.scalar_one_or_none():
                new_chat = Chat(
                    chat_id=chat_id,
                    user_id=user_id,
                    status=True,
                )
                session.add(new_chat)
                await session.commit()

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
