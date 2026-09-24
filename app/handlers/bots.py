import asyncio
from contextlib import suppress
from html import escape as html_escape
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import LabeledPrice

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
    subscription_plan_kb,
    subscription_plans_kb,
    referral_kb,
)
from app.repository.user import crud_user
from app.utils.faq_data import faq_items
from app.utils.trial import REFERRAL_STATUS_ACTIVE, build_trial_state, normalize_dt
from app.utils.subscriptions import SUBSCRIPTION_PLANS

router = Router()
APP_TZ = ZoneInfo(settings.APP_TZ)
SUBSCRIPTION_PAYMENT_TIMEOUT = 10 * 60
# user_id -> (timeout task, bot, waiting message id, invoice payload, deadline)
_pending_subscription_payments: dict[int, tuple[asyncio.Task, Bot, int, str, float]] = {}


async def _expire_subscription_payment(user_id: int, payload: str, deadline: float) -> None:
    """Mark an unpaid invoice as cancelled after the user-facing grace period."""
    await asyncio.sleep(max(deadline - asyncio.get_running_loop().time(), 0))
    pending = _pending_subscription_payments.get(user_id)
    if not pending or pending[0] is not asyncio.current_task() or pending[3] != payload:
        return

    _, bot, message_id, _, _ = pending
    _pending_subscription_payments.pop(user_id, None)
    with suppress(Exception):
        await bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text="❌ Оплата не подтверждена за 10 минут, счёт отменён. Создай новый счёт в разделе подписки.",
        )


class ReferralInput(StatesGroup):
    waiting_for_code = State()


def _display_name(user: types.User) -> str:
    return html_escape(user.full_name or user.first_name or "друг")


def _is_admin_user(user_id: int | str | None) -> bool:
    return bool(settings.ADMIN_TG_ID and str(user_id) == settings.ADMIN_TG_ID)


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
    if trial_state.is_lifetime:
        return "♾ Без ограничений"
    if trial_state.is_active:
        return (
            f"🟢 Активен до {_format_dt(trial_state.trial_ends_at)} "
            f"({_format_remaining(trial_state.remaining)})"
        )
    return f"🔴 Истёк {_format_dt(trial_state.trial_ends_at)}"


def _start_text() -> str:
    return (
        "<b>Revian — спокойный контроль бизнес-переписки</b>\n\n"
        "Я сохраняю важное до того, как оно исчезнет: удалённые сообщения, правки и поддержанные медиа.\n\n"
        f"<b>Бесплатно:</b> {settings.TRIAL_PERIOD_HOURS} часов полного доступа.\n\n"
        "<b>Как это работает</b>\n"
        "1. Ты сам подключаешь Revian к бизнес-аккаунту.\n"
        "2. Выбираешь чаты и разрешения в Telegram.\n"
        "3. Я работаю только в выбранных чатах и отправляю копии тебе в личный диалог с ботом.\n\n"
        "<b>Что ты контролируешь</b>\n"
        "• подключение можно отключить в любой момент\n"
        "• данные хранятся в зашифрованном виде\n"
        "• подписка и реферальные бонусы продлевают доступ без скрытых условий\n\n"
        "Начни с инструкции — подключение занимает около минуты."
    )


def _returning_user_text(user: types.User, stored_user) -> str:
    return (
        f"<b>С возвращением, {_display_name(user)}</b>\n\n"
        f"<b>Доступ:</b> {_trial_status_label(stored_user)}\n"
        f"<b>Статус подключения:</b> {_connection_status(stored_user)}\n"
        f"<b>Твой промокод:</b> <code>{html_escape(stored_user.ref_code)}</code>\n\n"
        "Пригласи друга и получи +7 дней доступа — кнопка есть в меню ниже."
    )


def _instruction_text() -> str:
    return (
        "<b>Подключение Revian</b>\n\n"
        "1. Открой настройки Telegram.\n"
        "2. Перейди в <code>Chat Automation</code> / «Подключённые боты».\n"
        "3. Выбери «Добавить бота» и найди <code>@RevianBot</code>.\n"
        "4. Разреши чтение сообщений и выбери нужные чаты.\n\n"
        "<b>После подключения я смогу:</b>\n"
        "• прислать тебе медиа от собеседника сразу;\n"
        "• сохранить текст до его удаления или редактирования;\n"
        "• сообщить, что именно изменилось.\n\n"
        "Я не подключаюсь к чатам сам, не пишу собеседникам и не работаю вне выбранных тобой чатов.\n\n"
        "В любой момент отключи Revian там же, в настройках Telegram."
    )


def _main_menu_text() -> str:
    return (
        "<b>Главное меню Revian</b>\n\n"
        "Здесь можно проверить статус подключения, купить подписку, "
        "пригласить друга, активировать промокод или открыть FAQ и поддержку."
    )


def _support_text() -> str:
    return (
        "<b>Поддержка</b>\n\n"
        "Если нужна помощь с подключением, оплатой или удалением данных, "
        "напиши владельцу проекта.\n\n"
        f"Контакт: {html_escape(settings.TRIAL_SUPPORT_HANDLE)}\n"
        "Обычно отвечаем в течение рабочего дня."
    )


def _about_text() -> str:
    return (
        "<b>О Revian</b>\n\n"
        "Revian — инструмент для владельцев Telegram Business, которым важно не терять контекст переписки.\n\n"
        "Я не заменяю Telegram и не вмешиваюсь в разговоры: только фиксирую выбранные события и отправляю результат владельцу.\n\n"
        "Принцип проекта простой: понятное подключение, прозрачная оплата и контроль данных у пользователя."
    )


def _faq_intro_text() -> str:
    return (
        "<b>FAQ</b>\n\n"
        "Собрал короткие ответы на самые частые вопросы о приватности, подключении и работе бота."
    )


def _subscription_intro_text() -> str:
    return (
        "<b>Подписка Revian</b>\n\n"
        "Продли доступ к контролю бизнес-переписки: удалённым сообщениям, правкам и исчезающим медиа.\n\n"
        "Выбери срок подписки ниже. Оплата проходит в Telegram Stars.\n\n"
        "Можно также пригласить друга и получить +7 дней бесплатно."
    )


def _subscription_plan_text(plan) -> str:
    benefit = "доступ без ограничения срока" if plan.code == "unlimited" else f"полный доступ на {plan.period}"
    return (
        f"<b>{plan.title}</b>\n\n"
        f"Стоимость: <b>{plan.stars} ⭐</b>\n"
        f"Что получишь: {benefit}.\n"
        f"Преимущество: {plan.value}.\n\n"
        "До подтверждения ты увидишь сумму в Telegram. Доступ активируется только после успешной оплаты."
    )


async def _referral_link(bot, ref_code: str) -> str:
    bot_user = await bot.get_me()
    return f"https://t.me/{bot_user.username}?start=ref_{ref_code}"


@router.message(F.text == "/userstats")
async def handle_user_stats(message: types.Message):
    if not _is_admin_user(message.from_user.id):
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


@router.message(F.text.startswith("/start"))
async def handle_start_in_business(message: types.Message):
    tg_id = str(message.from_user.id)
    tg_login = message.from_user.username or message.from_user.full_name
    start_arg = (message.text or "").split(maxsplit=1)[1].strip() if " " in (message.text or "") else ""

    user = await crud_user.get_user_by_tg_id(tg_id)

    if user:
        if start_arg.lower().startswith("ref_"):
            result = await crud_user.update_referral_user(
                tg_id=tg_id,
                ref_code=start_arg[4:].strip().upper(),
            )
            if result == 1:
                await message.answer(
                    "🎉 Реферальный код принят! Пригласивший тебя пользователь получил +7 дней доступа.\n\n"
                    "Спасибо, что присоединился по приглашению друга.",
                    reply_markup=main_menu_kb(),
                )
                return
        await message.answer(
            _returning_user_text(message.from_user, user),
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
        return

    await crud_user.add_user(tg_id, tg_login)

    if start_arg.lower().startswith("ref_"):
        result = await crud_user.update_referral_user(
            tg_id=tg_id,
            ref_code=start_arg[4:].strip().upper(),
        )
        if result == 1:
            await message.answer(
                f"🎉 Реферальный код принят! Пригласивший друг получил +{settings.REFERRAL_BONUS_HOURS} часов, а ты можешь продолжить настройку Revian.",
                reply_markup=start_continue_kb,
                parse_mode="HTML",
            )
            return

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

    if settings.LIFETIME_PROMO_CODE and code == settings.LIFETIME_PROMO_CODE.upper():
        result = await crud_user.activate_lifetime_access(tg_id=tg_id)

        if result == 1:
            await message.answer(
                "<b>Промокод принят</b>\n\n"
                "Для этого аккаунта активирован бессрочный доступ без ограничений.",
                reply_markup=next_to_menu_kb,
                parse_mode="HTML",
            )
        elif result == -1:
            await message.answer(
                "<b>Доступ уже активирован</b>\n\n"
                "Для этого аккаунта уже включён бессрочный режим.",
                reply_markup=menu_kb(),
                parse_mode="HTML",
            )
        else:
            await message.answer(
                "<b>Профиль не найден</b>\n\n"
                "Нажми /start и попробуй активировать промокод снова.",
                reply_markup=menu_kb(),
                parse_mode="HTML",
            )
        await state.clear()
        return

    result = await crud_user.update_referral_user(tg_id=tg_id, ref_code=code)

    if result == 1:
        await message.answer(
            f"<b>Промокод принят</b>\n\n"
            f"Код <code>{html_escape(code)}</code> успешно активирован.\n"
            "Пользователь, который тебя пригласил, получил ещё 7 дней доступа.",
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


@router.callback_query(F.data == "subscription")
async def show_subscription_plans(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer(
        _subscription_intro_text(),
        parse_mode="HTML",
        reply_markup=subscription_plans_kb(),
    )


@router.callback_query(F.data == "referral")
async def show_referral(callback: types.CallbackQuery):
    await callback.answer()
    user = await crud_user.get_user_by_tg_id(str(callback.from_user.id))
    if not user:
        await callback.message.answer("Нажми /start, чтобы создать профиль.")
        return

    link = await _referral_link(callback.bot, user.ref_code)
    await callback.message.delete()
    await callback.message.answer(
        "<b>Пригласи друга и получи 7 дней бесплатно</b>\n\n"
        "Отправь другу эту ссылку. Когда он впервые активирует её, ты получишь +7 дней доступа.\n\n"
        f"<b>Твой код:</b> <code>{html_escape(user.ref_code)}</code>\n"
        f"<b>Твоя ссылка:</b>\n<code>{html_escape(link)}</code>\n\n"
        "Один приглашённый пользователь может активировать только один реферальный код.",
        parse_mode="HTML",
        reply_markup=referral_kb(),
    )


@router.callback_query(F.data.startswith("subscription_plan:"))
async def show_subscription_plan(callback: types.CallbackQuery):
    plan_code = callback.data.split(":", 1)[1]
    plan = SUBSCRIPTION_PLANS.get(plan_code)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    await callback.answer()
    await callback.message.delete()
    await callback.message.answer(
        _subscription_plan_text(plan),
        parse_mode="HTML",
        reply_markup=subscription_plan_kb(plan.code),
    )


@router.callback_query(F.data.startswith("subscription_pay:"))
async def create_subscription_invoice(callback: types.CallbackQuery):
    plan_code = callback.data.split(":", 1)[1]
    plan = SUBSCRIPTION_PLANS.get(plan_code)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    payload = f"revian_sub:{plan.code}:{callback.from_user.id}"
    await callback.answer("Формирую счёт…")
    try:
        await callback.bot.send_invoice(
            chat_id=callback.from_user.id,
            title=plan.title,
            description=(
                f"Revian: {('безлимитный доступ' if plan.code == 'unlimited' else f'доступ на {plan.period}')}"
            ),
            payload=payload,
            currency="XTR",
            prices=[LabeledPrice(label=plan.title, amount=plan.stars)],
            provider_token="",
        )
        waiting_message = await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text="⏳ Ожидаем оплату. После подтверждения Stars доступ продлится автоматически.",
        )
        user_id = callback.from_user.id
        # Keep only the latest invoice for this user. A new invoice supersedes an
        # older one and prevents an old timeout from editing the new message.
        previous = _pending_subscription_payments.pop(user_id, None)
        if previous:
            previous[0].cancel()
        deadline = asyncio.get_running_loop().time() + SUBSCRIPTION_PAYMENT_TIMEOUT
        timeout_task = asyncio.create_task(
            _expire_subscription_payment(user_id, payload, deadline)
        )
        _pending_subscription_payments[user_id] = (
            timeout_task,
            callback.bot,
            waiting_message.message_id,
            payload,
            deadline,
        )
    except Exception:
        await callback.message.answer(
            "Не удалось создать счёт. Попробуй ещё раз через несколько секунд.",
            reply_markup=subscription_plan_kb(plan.code),
        )


@router.pre_checkout_query()
async def process_pre_checkout_query(query: types.PreCheckoutQuery, bot: Bot):
    pending = _pending_subscription_payments.get(query.from_user.id)
    if (
        not pending
        or pending[3] != query.invoice_payload
        or pending[4] <= asyncio.get_running_loop().time()
    ):
        await query.answer(ok=False, error_message="Счёт истёк. Создай новый счёт в разделе подписки.")
        await bot.send_message(query.from_user.id, "❌ Оплата не прошла: время ожидания истекло. Создай новый счёт.")
        return

    parts = (query.invoice_payload or "").split(":")
    if len(parts) != 3 or parts[0] != "revian_sub" or parts[2] != str(query.from_user.id):
        await query.answer(ok=False, error_message="Счёт устарел. Создай новый счёт в разделе подписки.")
        await bot.send_message(query.from_user.id, "❌ Оплата не прошла: счёт устарел. Создай новый счёт.")
        return

    plan = SUBSCRIPTION_PLANS.get(parts[1])
    if not plan or query.currency != "XTR" or query.total_amount != plan.stars:
        await query.answer(ok=False, error_message="Тариф изменился. Создай новый счёт.")
        await bot.send_message(query.from_user.id, "❌ Оплата не прошла: тариф изменился. Создай новый счёт.")
        return

    await query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    payment = message.successful_payment
    pending = _pending_subscription_payments.pop(message.from_user.id, None)
    if pending:
        pending[0].cancel()
        with suppress(asyncio.CancelledError):
            await pending[0]
        with suppress(Exception):
            await pending[1].edit_message_text(
                chat_id=message.from_user.id,
                message_id=pending[2],
                text="✅ Оплата подтверждена. Доступ продлевается автоматически…",
            )
    parts = (payment.invoice_payload or "").split(":")
    if len(parts) != 3 or parts[0] != "revian_sub" or parts[2] != str(message.from_user.id):
        await message.answer("Платёж получен, но его тариф не удалось определить. Обратись в поддержку.")
        return

    plan = SUBSCRIPTION_PLANS.get(parts[1])
    if not plan:
        await message.answer("Платёж получен, но тариф не найден. Обратись в поддержку.")
        return

    if plan.code == "unlimited":
        result = await crud_user.activate_lifetime_access(str(message.from_user.id))
        if result == -1:
            await message.answer("У тебя уже активирован безлимитный доступ ♾")
        elif result != 1:
            await message.answer("Платёж прошёл, но профиль не найден. Обратись в поддержку.")
        else:
            await message.answer("🎉 Оплата прошла! Поздравляю — безлимитный доступ активирован.")
        return

    ends_at = await crud_user.extend_paid_access(str(message.from_user.id), plan.hours)
    if ends_at is None:
        await message.answer("Платёж прошёл, но профиль не найден. Обратись в поддержку.")
        return

    await message.answer(
        f"🎉 Оплата прошла! Подписка активирована на {plan.period}.\n"
        f"Доступ продлён до <b>{_format_dt(ends_at)}</b>.",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
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
        f"<b>Доступ:</b> {'♾ Бессрочный' if trial_state.is_lifetime else ('🟢 Активен' if trial_state.is_active else '🔴 Истёк')}\n"
        f"<b>Доступ до:</b> {'без ограничений' if trial_state.is_lifetime else _format_dt(trial_state.trial_ends_at)}\n"
        f"<b>Осталось:</b> {'без ограничений' if trial_state.is_lifetime else _format_remaining(trial_state.remaining)}\n"
        f"<b>Статус подключения:</b> {_connection_status(user)}\n"
        f"<b>Твой промокод:</b> <code>{html_escape(user.ref_code)}</code>\n"
        f"<b>Входной промокод:</b> {_referral_status(user)}\n"
        f"<b>Приглашён:</b> {_format_dt(getattr(user, 'referred_at', None))}\n"
        f"<b>Бессрочный доступ активирован:</b> {_format_dt(getattr(user, 'lifetime_activated_at', None))}\n"
        f"<b>Активных приглашений:</b> {referral_summary.active_count}\n"
        f"<b>Последний приглашён:</b> {_format_dt(referral_summary.latest_referred_at)}",
        parse_mode="HTML",
        reply_markup=profile_kb(),
    )
