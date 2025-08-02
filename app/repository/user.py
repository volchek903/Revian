from app.core.db import get_session
from sqlalchemy import select, update
from app.models.user import User
import hashlib
from datetime import datetime
import pytz


def generate_referral_from_user_id(user_id: int | str, length: int = 6) -> str:
    hash_digest = hashlib.sha256(str(user_id).encode()).hexdigest().upper()
    return hash_digest[:length]


class CRUDUser:

    async def update_connection_id(self, user_id: str, connection_id: str):
        async with get_session() as session:
            stmt = (
                update(User)
                .where(User.tgID == user_id)
                .values(connection_id=connection_id)
            )
            await session.execute(stmt)
            await session.commit()

    async def get_user_by_connection_id(self, connection_id: str):
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.connection_id == connection_id)
            )
            return result.scalar_one_or_none()

    async def add_user(self, tg_id: str, tg_login: str):
        async with get_session() as session:
            # Проверка: существует ли пользователь с таким tgID
            result = await session.execute(select(User).where(User.tgID == tg_id))
            existing_user = result.scalar_one_or_none()
            if existing_user:
                return
            moscow_tz = pytz.timezone("Europe/Moscow")
            now_msk = datetime.now(moscow_tz)
            max_attempts = 10
            for _ in range(max_attempts):
                new_code = generate_referral_from_user_id(str(tg_id))
                result = await session.execute(
                    select(User).where(User.ref_code == new_code)
                )
                code_conflict = result.scalar_one_or_none()
                if not code_conflict:
                    break
            else:
                raise ValueError(
                    "⚠️ Не удалось сгенерировать уникальный реферальный код"
                )

            user = User(
                tgID=tg_id,
                tgLog=tg_login,
                ref_code=new_code,
                create_at=now_msk,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

    async def update_referral_user(self, tg_id: str, ref_code: str) -> int:
        async with get_session() as session:
            # Проверка: существует ли пользователь с таким реф. кодом
            result = await session.execute(
                select(User).where(User.ref_code == ref_code)
            )
            referrer = result.scalar_one_or_none()

            if not referrer:
                # Реферальный код не существует
                return 0

            if referrer.tgID == tg_id:
                # Нельзя ввести свой собственный код
                return -1

            # Проверка: текущий пользователь уже привязан?
            result = await session.execute(select(User).where(User.tgID == tg_id))
            user = result.scalar_one_or_none()

            if not user or user.referral_id:
                # Либо пользователь не найден, либо уже привязан
                return -2

            # Обновляем поле referral_id
            stmt = (
                update(User).where(User.tgID == tg_id).values(referral_id=referrer.tgID)
            )
            await session.execute(stmt)
            await session.commit()
            return 1  # Успешно

    async def is_user_exists(self, tg_id: str) -> bool:
        async with get_session() as session:
            result = await session.execute(select(User).where(User.tgID == tg_id))
            return result.scalar_one_or_none() is not None


crud_user = CRUDUser()
