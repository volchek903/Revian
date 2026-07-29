from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


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
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )
