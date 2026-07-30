from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings

REFERRAL_STATUS_ACTIVE = "active"
APP_TZ = ZoneInfo(settings.APP_TZ)


def now_in_app_tz() -> datetime:
    return datetime.now(APP_TZ)


def normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=APP_TZ)
    return value.astimezone(APP_TZ)


def initial_trial_end(started_at: datetime | None = None) -> datetime:
    base = normalize_dt(started_at) or now_in_app_tz()
    return base + timedelta(hours=settings.TRIAL_PERIOD_HOURS)


def extend_trial(current_end: datetime | None, *, from_time: datetime | None = None) -> datetime:
    now = normalize_dt(from_time) or now_in_app_tz()
    current = normalize_dt(current_end)
    anchor = current if current and current > now else now
    return anchor + timedelta(hours=settings.REFERRAL_BONUS_HOURS)


@dataclass(frozen=True)
class TrialState:
    is_active: bool
    trial_ends_at: datetime
    remaining: timedelta


def build_trial_state(user) -> TrialState:
    now = now_in_app_tz()
    trial_ends_at = normalize_dt(getattr(user, "trial_ends_at", None))
    if trial_ends_at is None:
        trial_ends_at = initial_trial_end(getattr(user, "create_at", None))

    remaining = trial_ends_at - now
    return TrialState(
        is_active=remaining.total_seconds() > 0,
        trial_ends_at=trial_ends_at,
        remaining=remaining,
    )
