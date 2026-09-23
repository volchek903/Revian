from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.utils.subscriptions import SUBSCRIPTION_PLANS


start_continue_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✨ Начать настройку", callback_data="start_continue")]
    ]
)

faq_back_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️ К вопросам", callback_data="faq"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"),
        ]
    ]
)

welcome_revian_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="has_referral")
        ],
        [
            InlineKeyboardButton(
                text="➡️ Продолжить без промокода",
                callback_data="no_referral",
            )
        ],
        [InlineKeyboardButton(text="💳 Получить подписку", callback_data="subscription")],
    ]
)

has_referral_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="has_referral")
        ],
        [
            InlineKeyboardButton(
                text="➡️ Продолжить без промокода",
                callback_data="no_referral",
            )
        ],
        [InlineKeyboardButton(text="💳 Получить подписку", callback_data="subscription")],
    ]
)

no_referral_from_has_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➡️ Продолжить без промокода",
                callback_data="no_referral",
            )
        ],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu")],
        [InlineKeyboardButton(text="💳 Получить подписку", callback_data="subscription")],
    ]
)

next_to_menu_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Открыть главное меню", callback_data="main_menu")]
    ]
)


def generate_faq_kb(items: list[dict]) -> InlineKeyboardMarkup:
    keyboard = []

    for item in items:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=item.get("button", item["question"]),
                    callback_data=f"faq_q_{item['id']}",
                )
            ]
        )

    keyboard.append(
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def back_to_choice_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎟 Ввести промокод",
                    callback_data="has_referral",
                )
            ],
            [
                InlineKeyboardButton(
                    text="➡️ Продолжить без промокода",
                    callback_data="no_referral",
                )
            ],
            [InlineKeyboardButton(text="💳 Получить подписку", callback_data="subscription")],
        ]
    )


def menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ]
    )


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
                InlineKeyboardButton(text="🎁 Промокод", callback_data="has_referral"),
            ],
            [
                InlineKeyboardButton(text="💳 Подписка", callback_data="subscription"),
                InlineKeyboardButton(text="👥 Пригласить друга", callback_data="referral"),
            ],
            [
                InlineKeyboardButton(text="📘 Подключение", callback_data="instruction"),
                InlineKeyboardButton(text="❓ FAQ", callback_data="faq"),
            ],
            [
                InlineKeyboardButton(text="🛟 Поддержка", callback_data="support"),
                InlineKeyboardButton(text="ℹ️ О проекте", callback_data="about"),
            ],
        ]
    )


def instruction_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎟 Ввести промокод",
                    callback_data="has_referral",
                )
            ],
            [InlineKeyboardButton(text="💳 Получить подписку", callback_data="subscription")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )


def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎟 Активировать промокод",
                    callback_data="has_referral",
                )
            ],
            [InlineKeyboardButton(text="💳 Получить подписку", callback_data="subscription")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )


def support_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Канал Revian",
                    url="https://t.me/RevianNews",
                )
            ],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )


def about_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Новости",
                    url="https://t.me/RevianNews",
                ),
                InlineKeyboardButton(
                    text="👨‍💻 Команда",
                    url="https://t.me/TeamATechs",
                ),
            ],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )


def retry_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔁 Попробовать другой код",
                    callback_data="has_referral",
                )
            ],
            [
                InlineKeyboardButton(
                    text="➡️ Продолжить без промокода",
                    callback_data="no_referral",
                )
            ],
            [InlineKeyboardButton(text="💳 Получить подписку", callback_data="subscription")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )


def subscription_plans_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 30 дней — 350 ⭐", callback_data="subscription_plan:month")],
            [InlineKeyboardButton(text="📅 90 дней — 850 ⭐", callback_data="subscription_plan:quarter")],
            [InlineKeyboardButton(text="📅 180 дней — 1400 ⭐", callback_data="subscription_plan:halfyear")],
            [InlineKeyboardButton(text="♾ Безлимит — 2000 ⭐", callback_data="subscription_plan:unlimited")],
            [InlineKeyboardButton(text="👥 Пригласить друга — +7 дней", callback_data="referral")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )


def subscription_plan_kb(plan_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить подписку", callback_data=f"subscription_pay:{plan_code}")],
            [InlineKeyboardButton(text="👥 Пригласить друга — +7 дней", callback_data="referral")],
            [InlineKeyboardButton(text="◀️ Назад к тарифам", callback_data="subscription")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )


def referral_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Купить подписку", callback_data="subscription")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )
