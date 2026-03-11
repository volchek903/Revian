# app/repository/message.py
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, insert, select, update

from app.core.db import get_session
from app.models.message import Message


class CRUDMessage:
    async def add_message(
        self,
        msg_id: int,
        from_user: str,
        to_user: str,
        content: str,
        m_type: str = "text",
    ):
        async with get_session() as session:
            stmt = insert(Message).values(
                msg_id=str(msg_id),
                from_user=from_user,
                to_user=to_user,
                content=content,
                type=m_type,
            )
            await session.execute(stmt)
            await session.commit()

    async def get_message_by_ids(
        self, msg_id: str, from_user: str, to_user: str
    ) -> Message | None:
        async with get_session() as session:
            result = await session.execute(
                select(Message).where(
                    Message.msg_id == msg_id,
                    Message.from_user == from_user,
                    Message.to_user == to_user,
                )
            )
            return result.scalar_one_or_none()

    async def update_message_content(
        self, msg_id: str, from_user: str, to_user: str, new_content: str
    ):
        async with get_session() as session:
            stmt = (
                update(Message)
                .where(
                    Message.msg_id == msg_id,
                    Message.from_user == from_user,
                    Message.to_user == to_user,
                )
                .values(content=new_content)
            )
            await session.execute(stmt)
            await session.commit()

    async def delete_messages_older_than(self, days: int = 30) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=int(days))

        async with get_session() as session:
            rows = await session.execute(
                select(Message.id).where(Message.create_at < cutoff)
            )
            ids_to_delete = [row[0] for row in rows.fetchall()]

            if not ids_to_delete:
                return 0

            await session.execute(delete(Message).where(Message.id.in_(ids_to_delete)))
            await session.commit()
            return len(ids_to_delete)


crud_message = CRUDMessage()
