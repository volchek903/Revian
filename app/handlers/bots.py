from html import escape as html_escape
from zoneinfo import ZoneInfo

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.core.config import settings
from app.keyboards.bot_keyboard import (
    about_kb,
    faq_back_kb,
    generate_faq_kb,
    has_referral_kb,
    instruction_kb,
    main_menu_kb,
    menu_kb,
    next_to_menu_kb,
    no_referral_from_has_kb,
    profile_kb,
    retry_kb,
    start_continue_kb,
    support_kb,
)
from app.repository.user import crud_user
from app.utils.faq_data import faq_items
from app.utils.trial import REFERRAL_STATUS_ACTIVE, build_trial_state, normalize_dt

router = Router()

Admin = "830091750"
APP_TZ = ZoneInfo(settings.APP_TZ)


class ReferralInput(StatesGroup):
    waiting_for_code = State()


def _display_name(user: types.User) -> str:
    return html_escape(user.full_name or user.first_name or "друг")


def _display_username(user: types.User) -> str:
    return f"@{html_escape(user.username)}" if user.username else "не указан"


def _connection_status(user) -> str:
    return "🟢 Подключён" if getattr(user, "connection_id", None) else "🟡 Не подключён"


def _referral_status(user) -> str:
    if getattr(user, "referral_status", None) == REFERRAL_STATUS_ACTIVE:
        return "активный"
    return "не использован"


def _format_dt(value) -> str:
    dt = normalize_dt(value)
    if dt is None:
        return "—"
    return dt.astimezone(APP_TZ).strftime("%d.%m.%Y %H:%M")


def _format_remaining(remaining) -> str:
    total_seconds = int(max(remaining.total_seconds(), 0))
    if total_seconds <= 0:
        return "0 ч"

    hours_total, minutes = divmod(total_seconds // 60, 60)
    days, hours = divmod(hours_total, 24)

    parts: list[str] = []
    if days:
        parts.append(f"{days} д")
    if hours:
        parts.append(f"{hours} ч")
    if minutes and not days:
        parts.append(f"{minutes} мин")
    return " ".join(parts) or "0 ч"


def _trial_status_label(stored_user) -> str:
    trial_state = build_trial_state(stored_user)
    if trial_state.is_active:
        return (
            f"🟢 Активен до {_format_dt(trial_state.trial_ends_at)} "
            f"({_format_remaining(trial_state.remaining)})"
        )
    return f"🔴 Истёк {_format_dt(trial_state.trial_ends_at)}"


def _start_text() -> str:
    return (
        "<b>Revian</b>\n\n"
        "Приватный помощник для бизнес-переписки в Telegram.\n\n"
        "Ниже находится инструкция по подключению и использованию бота.\n\n"
        f"<b>Тестовый период:</b> {settings.TRIAL_PERIOD_HOURS} часов полного доступа.\n"
        "После этого доступ можно продлить с помощью реферальной системы.\n"
        f"За каждого нового реферала ты получаешь ещё {settings.REFERRAL_BONUS_HOURS} часов пользования ботом.\n\n"
        "Топ рефералов получает промокоды раз в месяц.\n"
        "Промокоды дают дополнительное увеличение времени пользования ботом.\n\n"
        "<b>Что умею:</b>\n"
        "• фиксирую удалённые сообщения\n"
        "• показываю, что изменили после редактирования\n"
        "• помогаю не потерять исчезающие фото и видео\n"
        "• работаю тихо в фоне после подключения\n\n"
        "<b>Приватность:</b>\n"
        "• данные шифруются\n"
        "• доступ к содержимому есть только у тебя\n\n"
        "Нажми кнопку ниже, и я покажу, как подключить меня за минуту."
    )


def _returning_user_text(user: types.User, stored_user) -> str:
    return (
        f"<b>С возвращением, {_display_name(user)}</b>\n\n"
        f"<b>Доступ:</b> {_trial_status_label(stored_user)}\n"
        f"<b>Статус подключения:</b> {_connection_status(stored_user)}\n"
        f"<b>Твой промокод:</b> <code>{html_escape(stored_user.ref_code)}</code>\n\n"
        "Нужный раздел уже в меню ниже."
    )


def _instruction_text() -> str:
    return (
        "<b>Как подключить Revian</b>\n\n"
        "1. Открой настройки Telegram.\n"
        "2. Перейди в раздел <code>Chat Automation</code>.\n"
        "3. Нажми <b>«Добавить бота»</b> и выбери <code>@RevianBot</code>.\n"
        "4. Разреши доступ к сообщениям и сохрани настройки.\n\n"
        "<b>После подключения Revian сможет:</b>\n"
        "• сообщать об удалении сообщений\n"
        "• сохранять исходный текст после правок\n"
        "• перехватывать важные исчезающие медиа\n\n"
        "<i>В старых клиентах Telegram этот раздел может называться иначе, "
        "но логика та же: подключение бота для автоматизации чатов.</i>"
    )


def _main_menu_text() -> str:
    return (
        "<b>Главное меню Revian</b>\n\n"
        "Здесь можно проверить статус подключения, открыть инструкцию, "
        "активировать промокод или быстро перейти в FAQ и поддержку."
    )


def _support_text() -> str:
    return (
        "<b>Поддержка</b>\n\n"
        "Если что-то работает не так или нужен ответ по подключению, "
        "пиши через официальный канал проекта.\n\n"
        "Там публикуются обновления и можно быстро связаться с командой."
    )


def _about_text() -> str:
    return (
        "<b>О проекте</b>\n\n"
        "Revian помогает владельцу бизнес-аккаунта не терять важные изменения в переписке: "
        "удаления, правки и исчезающие медиа.\n\n"
        "Проект сфокусирован на двух вещах: приватности и спокойном фоновом контроле."
    )


def _faq_intro_text() -> str:
    return (
        "<b>FAQ</b>\n\n"
        "Собрал короткие ответы на самые частые вопросы о приватности, подключении и работе бота."
    )


@router.message(F.text == "/userstats")
async def handle_user_stats(message: types.Message):
    if str(message.from_user.id) != Admin:
        return

    stats = await crud_user.get_user_stats()

    await message.answer(
        f"📊 <b>Статистика пользователей</b>\n\n"
        f"👥 Всего: <b>{stats['total']}</b>\n"
        f"📅 За месяц: <b>{stats['month']}</b>\n"
        f"🗓 За неделю: <b>{stats['week']}</b>\n"
        f"🕒 За 24 часа: <b>{stats['day']}</b>",
        parse_mode="HTML",
    )


@router.message(F.text == "/start")
async def handle_start_in_business(message: types.Message):
    tg_id = str(message.from_user.id)
    tg_login = message.from_user.username or message.from_user.full_name

    user = await crud_user.get_user_by_tg_id(tg_id)

    if user:
        await message.answer(
            _returning_user_text(message.from_user, user),
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
        return

    await crud_user.add_user(tg_id, tg_login)

    await message.answer(
        _start_text(),
        reply_markup=start_continue_kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "start_continue")
async def handle_continue_callback(callback: types.CallbackQuery):
    await callback.answer("Открываю инструкцию")
    await callback.message.delete()

    await callback.bot.send_message(
        chat_id=callback.message.chat.id,
        text=_instruction_text(),
        reply_markup=instruction_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "welcome_revian")
async def handle_welcome_revian(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer(
        "<b>Промокод</b>\n\n"
        "Если у тебя есть пригласительный код, активируй его сейчас. "
        "Если нет, можно продолжить и без него.",
        reply_markup=has_referral_kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "has_referral")
async def ask_referral_code(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ReferralInput.waiting_for_code)
    await callback.message.delete()
    await callback.message.answer(
        "<b>Активация промокода</b>\n\n"
        "Отправь код одним сообщением. Я сразу проверю его и открою доступ дальше.",
        reply_markup=no_referral_from_has_kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "instruction")
async def show_instruction(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        _instruction_text(),
        reply_markup=instruction_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.in_({"no_referral", "no_referral_from_has"}))
async def continue_without_referral(
    callback: types.CallbackQuery, state: FSMContext
):
    await callback.answer("Продолжаем без промокода")
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "<b>Готово</b>\n\n"
        "Промокод можно ввести позже. Сейчас открою главное меню.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


@router.message(ReferralInput.waiting_for_code)
async def handle_referral_code_input(message: types.Message, state: FSMContext):
    code = (message.text or "").strip().upper()
    tg_id = str(message.from_user.id)

    if not code:
        await message.answer(
            "Нужен непустой промокод. Отправь его ещё раз одним сообщением.",
            reply_markup=retry_kb(),
            parse_mode="HTML",
        )
        await state.clear()
        return

    result = await crud_user.update_referral_user(tg_id=tg_id, ref_code=code)

    if result == 1:
        await message.answer(
            f"<b>Промокод принят</b>\n\n"
            f"Код <code>{html_escape(code)}</code> успешно активирован.\n"
            f"Пользователь, который тебя пригласил, получил ещё {settings.REFERRAL_BONUS_HOURS} часов доступа.",
            reply_markup=next_to_menu_kb,
            parse_mode="HTML",
        )
    elif result == -1:
        await message.answer(
            "<b>Промокод не подходит</b>\n\n"
            "Нельзя активировать собственный код. Поделись им с друзьями, "
            "а для себя используй только приглашение от другого пользователя.",
            reply_markup=retry_kb(),
            parse_mode="HTML",
        )
    elif result == -2:
        await message.answer(
            "<b>Промокод уже использован</b>\n\n"
            "Для этого аккаунта приглашение уже было активировано раньше.",
            reply_markup=menu_kb(),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"<b>Код не найден</b>\n\n"
            f"Промокод <code>{html_escape(code)}</code> не распознан. "
            "Проверь написание и попробуй ещё раз.",
            reply_markup=retry_kb(),
            parse_mode="HTML",
        )

    await state.clear()


@router.callback_query(F.data == "support")
async def show_support(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()

    await callback.message.answer(
        _support_text(),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=support_kb(),
    )


@router.callback_query(F.data == "about")
async def show_about(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()

    await callback.message.answer(
        _about_text(),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=about_kb(),
    )


@router.callback_query(F.data == "faq")
async def show_faq_menu(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer(
        _faq_intro_text(),
        reply_markup=generate_faq_kb(faq_items),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("faq_q_"))
async def handle_faq_answer(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()

    question_id = callback.data.split("_")[-1]

    answer = next((item for item in faq_items if item["id"] == question_id), None)
    if not answer:
        await callback.message.answer(
            "Не удалось найти этот вопрос. Вернись в список и выбери другой.",
            reply_markup=faq_back_kb,
            parse_mode="HTML",
        )
        return

    await callback.message.answer(
        f"<b>{html_escape(answer['question'])}</b>\n\n{answer['answer']}",
        parse_mode="HTML",
        reply_markup=faq_back_kb,
        disable_web_page_preview=answer.get("disable_preview", False),
    )


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer(
        _main_menu_text(),
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()

    user = await crud_user.get_user_by_tg_id(str(callback.from_user.id))

    if not user:
        await callback.message.answer(
            "<b>Профиль пока не найден</b>\n\n"
            "Нажми /start, чтобы заново инициализировать аккаунт.",
            reply_markup=menu_kb(),
            parse_mode="HTML",
        )
        return

    referral_summary = await crud_user.get_referral_summary(str(callback.from_user.id))
    trial_state = build_trial_state(user)

    await callback.message.answer(
        f"<b>Твой профиль</b>\n\n"
        f"<b>Имя:</b> {_display_name(callback.from_user)}\n"
        f"<b>Username:</b> {_display_username(callback.from_user)}\n"
        f"<b>ID:</b> <code>{callback.from_user.id}</code>\n"
        f"<b>Доступ:</b> {'🟢 Активен' if trial_state.is_active else '🔴 Истёк'}\n"
        f"<b>Доступ до:</b> {_format_dt(trial_state.trial_ends_at)}\n"
        f"<b>Осталось:</b> {_format_remaining(trial_state.remaining)}\n"
        f"<b>Статус подключения:</b> {_connection_status(user)}\n"
        f"<b>Твой промокод:</b> <code>{html_escape(user.ref_code)}</code>\n"
        f"<b>Входной промокод:</b> {_referral_status(user)}\n"
        f"<b>Приглашён:</b> {_format_dt(getattr(user, 'referred_at', None))}\n"
        f"<b>Активных приглашений:</b> {referral_summary.active_count}\n"
        f"<b>Последний приглашён:</b> {_format_dt(referral_summary.latest_referred_at)}",
        parse_mode="HTML",
        reply_markup=profile_kb(),
    )
