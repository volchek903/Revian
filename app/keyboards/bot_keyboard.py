# app/keyboards/bot_keyboard.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ────────── статические клавиатуры (создаются один раз) ──────────

start_continue_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Продолжить", callback_data="start_continue")]
    ]
)
faq_back_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к вопросам", callback_data="faq")]
    ]
)
welcome_revian_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🚀 Добро пожаловать к Revian",
                callback_data="welcome_revian",
            )
        ]
    ]
)


def generate_faq_kb(items: list[dict]) -> InlineKeyboardMarkup:
    keyboard = []

    for item in items:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=item["question"], callback_data=f"faq_q_{item['id']}"
                )
            ]
        )

    keyboard.append(
        [InlineKeyboardButton(text="🔙 Вернуться в меню", callback_data="main_menu")]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


has_referral_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Есть", callback_data="has_referral"),
            InlineKeyboardButton(text="❌ Нет", callback_data="no_referral"),
        ]
    ]
)

no_referral_from_has_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="↩️ Ошибся, промокода нет",
                callback_data="no_referral_from_has",
            )
        ]
    ]
)

next_to_menu_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="➡️ Далее", callback_data="main_menu")]]
)

# ────────── динамические клавиатуры (функции создают экземпляр при вызове) ──────────


def back_to_choice_kb() -> InlineKeyboardMarkup:
    """Кнопка «Ошибся, промокода нет» — возвращает к выбору промокода."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Ошибся, промокода нет",
                    callback_data="no_referral_from_has",
                )
            ]
        ]
    )


def menu_kb() -> InlineKeyboardMarkup:
    """Простая кнопка, ведущая в главное меню."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu")]
        ]
    )


def main_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню (пока только пункт «Профиль»)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
            [InlineKeyboardButton(text="📘 Инструкция", callback_data="instruction")],
            [InlineKeyboardButton(text="🧑‍💻 Поддержка", callback_data="support")],
            [InlineKeyboardButton(text="🧠 О нас", callback_data="about")],
            [InlineKeyboardButton(text="ℹ️ FAQ", callback_data="faq")],
        ]
    )


def retry_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура для повторного ввода промокода:
    1) «❌ Ошибся…»  – отказаться от промокода
    2) «🔄 Попробовать другой промокод»
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Ошибся, промокода нет",
                    callback_data="no_referral_from_has",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Попробовать другой промокод",
                    callback_data="has_referral",
                )
            ],
        ]
    )
