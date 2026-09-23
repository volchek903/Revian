from dataclasses import dataclass


@dataclass(frozen=True)
class SubscriptionPlan:
    code: str
    title: str
    period: str
    hours: int
    stars: int
    value: str


SUBSCRIPTION_PLANS: dict[str, SubscriptionPlan] = {
    "month": SubscriptionPlan("month", "Подписка на 30 дней", "30 дней", 30 * 24, 350, "для регулярного использования"),
    "quarter": SubscriptionPlan("quarter", "Подписка на 90 дней", "90 дней", 90 * 24, 850, "экономия по сравнению с помесячной оплатой"),
    "halfyear": SubscriptionPlan("halfyear", "Подписка на 180 дней", "180 дней", 180 * 24, 1400, "выгодный вариант на полгода"),
    "unlimited": SubscriptionPlan("unlimited", "Безлимитный доступ", "навсегда", 0, 2000, "доступ без ограничения срока"),
}
