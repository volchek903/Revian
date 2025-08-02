from aiogram import Router, F, types, Bot
from app.core.config import settings
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from app.repository.user import crud_user
from aiogram.utils.markdown import hbold
from app.keyboards.bot_keyboard import *
import asyncio

bot = Bot(token=settings.BOT_TOKEN)
router = Router()


class ReferralInput(StatesGroup):
    waiting_for_code = State()


async def type_text(chat_id: int, text: str, bot, delay: float = 0.02):
    sent = await bot.send_message(chat_id, ".")
    current_text = ""
    for char in text:
        current_text += char
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=sent.message_id,
                text=current_text,
                parse_mode="HTML",
            )
        except Exception:
            pass
        await asyncio.sleep(delay)


@router.message(F.text == "/start")
async def handle_start_in_business(message: types.Message):
    tg_id = str(message.from_user.id)
    tg_login = message.from_user.username or message.from_user.full_name

    user = await crud_user.is_user_exists(tg_id)

    if user:
        await message.answer(
            f"<b>👋 О, это снова ты, {hbold(tg_login)}!</b>\n\n"
            "Я уже с тобой работаю и продолжаю следить за перепиской.\n"
            "Ты снова в меню, хочешь что-то выбрать?",
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
        return

    await crud_user.add_user(tg_id, tg_login)  # ❌ Без шифрования

    await message.answer(
        "<b>Привет! Я Revian 👋</b>\n"
        "Я твой личный ассистент, который не даст исчезнуть ни одному сообщению в чате!\n\n"
        "🔍 Даже если собеседник что-то удалил — я покажу тебе это.\n"
        "✏️ Уведомляю, если сообщение было <b>отредактировано</b>, и сохраняю его <i>оригинал</i>.\n"
        "🧠 Я всё запоминаю и сохраняю историю переписки.\n"
        "🛡️ Контролирую удаление сообщений и <b>уведомляю об этом мгновенно</b>.\n"
        "📸 Сохраняю <b>сгорающие фото и видео</b>, пока они не исчезли.\n"
        "🗂️ Храню <b>все фото, видео, голосовые и документы</b>, которые тебе отправляют.\n"
        "🔗 Работаю автоматически и незаметно, но всегда на страже твоей переписки.\n\n"
        "🔒 <b>Все данные надёжно зашифрованы.</b>\n"
        "Никто — включая разработчиков — не имеет доступа к сообщениям, фото или голосовым.\n"
        "Ты — единственный, кто может просматривать свои данные.\n\n"
        "<b>Готов работать?</b> Просто <u>добавь меня в чат</u> — остальное я возьму на себя 💼",
        reply_markup=start_continue_kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "start_continue")
async def handle_continue_callback(callback: types.CallbackQuery):
    await callback.answer("✅ Продолжаем", show_alert=False)
    await callback.message.delete()

    text = (
        "<b>🔧 Как подключить Revian к бизнес-аккаунту Telegram:</b>\n\n"
        "1️⃣ Перейди в настройки своего бизнес-аккаунта Telegram.\n"
        "2️⃣ Нажми <b>«Инструменты» → «Боты»</b>.\n"
        "3️⃣ Нажми <b>«Добавить бота»</b>.\n"
        "4️⃣ Введи юзернейм бота (например: <code>@RevianBot</code>).\n"
        "5️⃣ Подтверди добавление и <b>дай доступ к сообщениям</b>.\n\n"
        "📥 После этого бот начнёт отслеживать переписку и выполнять свои функции:\n"
        "— сохранять удалённые сообщения\n"
        "— уведомлять об изменениях\n"
        "— хранить фото, голосовые и документы\n"
        "— работать в фоне автоматически\n\n"
        "⚠️ <i>Бот работает только в бизнес-чатах, где он официально добавлен!</i>"
    )

    await type_text(callback.message.chat.id, text, bot)

    await bot.send_message(
        chat_id=callback.message.chat.id,
        text="⬇️ Продолжим?",
        reply_markup=welcome_revian_kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "welcome_revian")
async def handle_welcome_revian(callback: types.CallbackQuery):
    await callback.message.answer(
        "У тебя есть пригласительный <b>промокод</b>? 🎁",
        reply_markup=has_referral_kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "has_referral")
async def ask_referral_code(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ReferralInput.waiting_for_code)
    await callback.message.answer(
        "✍️ Введите ваш <b>промокод</b> ниже:",
        reply_markup=no_referral_from_has_kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "no_referral_from_has")
async def fallback_from_referral(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Без промокода — не проблема 😉")
    await state.clear()
    await callback.message.answer(
        "Ты можешь продолжить пользоваться ботом без промокода.\n\n"
        "🔓 Открываю доступ к возможностям Revian!",
        reply_markup=main_menu_kb(),
    )


@router.message(ReferralInput.waiting_for_code)
async def handle_referral_code_input(message: types.Message, state: FSMContext):
    code = message.text.strip()
    tg_id = str(message.from_user.id)

    result = await crud_user.update_referral_user(
        tg_id=tg_id, ref_code=code  # ❌ Без шифрования
    )

    if result == 1:
        await message.answer(
            f"✅ Промокод <b>{code}</b> принят!\n"
            f"Вы успешно присоединились по приглашению 🌟",
            reply_markup=next_to_menu_kb,
            parse_mode="HTML",
        )
    elif result == -1:
        await message.answer(
            "⚠️ Вы не можете ввести собственный промокод.\n"
            "Поделитесь им с друзьями, чтобы получать бонусы!",
            reply_markup=retry_kb(),
            parse_mode="HTML",
        )
    elif result == -2:
        await message.answer(
            "🛑 Вы уже использовали промокод или были приглашены ранее.",
            reply_markup=menu_kb(),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"❌ Промокод <b>{code}</b> не найден.\n"
            "Проверьте правильность и попробуйте ещё раз.",
            reply_markup=retry_kb(),
            parse_mode="HTML",
        )

    await state.clear()


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🏠 <b>Ты в главном меню.</b>\n"
        "Нажми «Профиль», чтобы посмотреть данные о себе:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        f"👤 <b>Твой профиль</b>\n\n"
        f"• Имя: {callback.from_user.full_name}\n"
        f"• ID: <code>{callback.from_user.id}</code>",
        parse_mode="HTML",
    )
