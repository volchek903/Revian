# app/keyboards/bot_keyboard.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ────────── статические клавиатуры (создаются один раз) ──────────

start_continue_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Продолжить", callback_data="start_continue")]
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
            [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")]
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
