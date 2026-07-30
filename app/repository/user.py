import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy import select, update

from app.core.db import get_session
from app.models.user import User
from app.utils.trial import (
    REFERRAL_STATUS_ACTIVE,
    extend_trial,
    initial_trial_end,
    normalize_dt,
    now_in_app_tz,
)


def generate_referral_from_user_id(user_id: int | str, length: int = 6) -> str:
    hash_digest = hashlib.sha256(str(user_id).encode()).hexdigest().upper()
    return hash_digest[:length]


@dataclass(frozen=True)
class ReferralSummary:
    active_count: int
    latest_referred_at: datetime | None


class CRUDUser:

    async def get_user_by_tg_id(self, tg_id: str):
        async with get_session() as session:
            result = await session.execute(select(User).where(User.tgID == tg_id))
            return result.scalar_one_or_none()

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

    async def get_user_stats(self):
        async with get_session() as session:
            now = now_in_app_tz()

            time_24h = now - timedelta(days=1)
            time_7d = now - timedelta(days=7)
            time_30d = now - timedelta(days=30)

            total = await session.execute(select(func.count()).select_from(User))
            month = await session.execute(
                select(func.count()).select_from(User).where(User.create_at >= time_30d)
            )
            week = await session.execute(
                select(func.count()).select_from(User).where(User.create_at >= time_7d)
            )
            day = await session.execute(
                select(func.count()).select_from(User).where(User.create_at >= time_24h)
            )

            return {
                "total": total.scalar(),
                "month": month.scalar(),
                "week": week.scalar(),
                "day": day.scalar(),
            }

    async def add_user(self, tg_id: str, tg_login: str):
        async with get_session() as session:
            # Проверка: существует ли пользователь с таким tgID
            result = await session.execute(select(User).where(User.tgID == tg_id))
            existing_user = result.scalar_one_or_none()
            if existing_user:
                return
            now = now_in_app_tz()
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
                create_at=now,
                trial_ends_at=initial_trial_end(now),
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

    async def update_referral_user(self, tg_id: str, ref_code: str) -> int:
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.ref_code == ref_code)
            )
            referrer = result.scalar_one_or_none()

            if not referrer:
                return 0

            if referrer.tgID == tg_id:
                return -1

            result = await session.execute(select(User).where(User.tgID == tg_id))
            user = result.scalar_one_or_none()

            if not user or user.referral_id:
                return -2

            now = now_in_app_tz()
            user.referral_id = referrer.tgID
            user.referral_status = REFERRAL_STATUS_ACTIVE
            user.referred_at = now
            referrer.trial_ends_at = extend_trial(
                getattr(referrer, "trial_ends_at", None),
                from_time=now,
            )
            await session.commit()
            return 1

    async def get_referral_summary(self, tg_id: str):
        async with get_session() as session:
            result = await session.execute(
                select(
                    func.count(),
                    func.max(User.referred_at),
                ).select_from(User).where(
                    User.referral_id == tg_id,
                    User.referral_status == REFERRAL_STATUS_ACTIVE,
                )
            )
            active_count, latest_referred_at = result.one()
            return ReferralSummary(
                active_count=int(active_count or 0),
                latest_referred_at=normalize_dt(latest_referred_at),
            )

    async def is_user_exists(self, tg_id: str) -> bool:
        async with get_session() as session:
            result = await session.execute(select(User).where(User.tgID == tg_id))
            return result.scalar_one_or_none() is not None


crud_user = CRUDUser()
