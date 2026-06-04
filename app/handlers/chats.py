import asyncio
from html import escape as html_escape
from aiogram.exceptions import TelegramForbiddenError
from aiogram import Bot, Router, types
from aiogram.types import BufferedInputFile, BusinessConnection
from io import BytesIO
from loguru import logger
from pathlib import Path

from app.core.config import settings
from app.repository.chat import crud_chat
from app.repository.message import crud_message
from app.repository.user import crud_user
from app.utils.encription import encrypt, decrypt

router = Router()
MEDIA_DOWNLOAD_SEMAPHORE = asyncio.Semaphore(settings.MEDIA_DOWNLOAD_CONCURRENCY)
MAX_MEDIA_SIZE_BYTES = settings.MAX_MEDIA_SIZE_MB * 1024 * 1024


async def set_message(message: types.Message) -> None:
    try:
        logger.info(f"Сообщение сохранено: {message.chat.id}:{message.message_id}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении сообщения: {e}")


def _format_bytes(size_bytes: int) -> str:
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _media_size_is_too_large(size_bytes: int | None) -> bool:
    return size_bytes is not None and size_bytes > MAX_MEDIA_SIZE_BYTES


async def _download_media(
    bot: Bot,
    *,
    file_id: str,
    file_path_hint: str | None,
) -> BufferedInputFile:
    async with MEDIA_DOWNLOAD_SEMAPHORE:
        tg_file = await bot.get_file(file_id)
        buf = BytesIO()
        await bot.download_file(tg_file.file_path, destination=buf)
        buf.seek(0)

        suffix = Path(file_path_hint or tg_file.file_path).suffix or ".bin"
        return BufferedInputFile(buf.getvalue(), filename=f"{file_id}{suffix}")


@router.business_connection()
async def on_business_connection_change(conn: BusinessConnection, bot: Bot):
    user = conn.user
    user_id = str(user.id)
    connection_id = conn.id

    if conn.is_enabled:
        logger.success(f"🤖 Бот подключён к бизнес-аккаунту пользователя {user_id}")

        # Активируем чаты и обновляем connection_id
        await crud_chat.activate_all_by_user_id(user_id)
        await crud_user.update_connection_id(
            user_id=user_id,
            connection_id=connection_id
        )

        # Приветственное сообщение
        welcome_text = (
            "👋 Привет!\n\n"
            "Я рад, что ты со мной 🤖\n"
            "Теперь я готов к работе, и больше ни одно твоё сообщение "
            "не пропадёт незаметно в переписках.\n\n"
            "📌 Моя задача — отслеживать, сохранять и сообщать тебе "
            "о любых удалённых или отредактированных сообщениях."
        )
        try:
            await bot.send_message(chat_id=user_id, text=welcome_text)
        except Exception as e:
            logger.warning(f"Не удалось отправить приветственное сообщение {user_id}: {e}")

    else:
        logger.warning(f"🚫 Бот отключён от бизнес-аккаунта пользователя {user_id}")

        # Деактивируем чаты
        await crud_chat.deactivate_all_by_user_id(user_id)

        # Прощальное сообщение
        farewell_text = (
            "😔 Похоже, мы расстаёмся...\n\n"
            "Я больше не смогу отслеживать твои бизнес-диалоги и "
            "предупреждать о пропавших сообщениях.\n\n"
            "Если захочешь вернуться — просто подключи меня снова!"
        )
        try:
            await bot.send_message(chat_id=user_id, text=farewell_text)
        except Exception as e:
            logger.warning(f"Не удалось отправить прощальное сообщение {user_id}: {e}")

async def media_with_timer(message: types.Message, bot: Bot, owner_id: str):
    reply = message.reply_to_message
    if not reply:
        return

    if reply.from_user and (str(reply.from_user.id) == str(owner_id)):
        logger.info("Ответ на сообщение владельца — не пересылаем обратно владельцу.")
        return

    if reply.from_user and (str(reply.from_user.id) == str(message.from_user.id)):
        logger.info("Ответ на собственное сообщение — пропускаем медиа-обработку.")
        return

    # Только защищённые/скрытые медиа
    is_protected = bool(getattr(reply, "has_protected_content", False))
    if not is_protected:
        logger.info("Медиа без защиты (has_protected_content != True) — пропускаем обработку.")
        return

    # Фото (максимальный размер)
    if reply.photo:
        file_id = reply.photo[-1].file_id
        file_size = getattr(reply.photo[-1], "file_size", None)
        if _media_size_is_too_large(file_size):
            logger.warning(
                "media: skip protected photo for owner_id={}, size={} exceeds limit={}",
                owner_id,
                _format_bytes(file_size),
                _format_bytes(MAX_MEDIA_SIZE_BYTES),
            )
            return

        photo_file = await _download_media(
            bot,
            file_id=file_id,
            file_path_hint=getattr(reply.photo[-1], "file_path", None),
        )

        try:
            await bot.send_photo(owner_id, photo=photo_file)
        except Exception as e:
            logger.error(f"Ошибка при отправке фото пользователю {owner_id}: {e}")

    # Видео
    elif reply.video:
        file_id = reply.video.file_id
        width = reply.video.width
        height = reply.video.height
        file_size = getattr(reply.video, "file_size", None)
        if _media_size_is_too_large(file_size):
            logger.warning(
                "media: skip protected video for owner_id={}, size={} exceeds limit={}",
                owner_id,
                _format_bytes(file_size),
                _format_bytes(MAX_MEDIA_SIZE_BYTES),
            )
            return

        video_file = await _download_media(
            bot,
            file_id=file_id,
            file_path_hint=getattr(reply.video, "file_name", None),
        )

        try:
            await bot.send_video(
                owner_id,
                video=video_file,
                width=width,
                height=height,
                supports_streaming=True,
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке видео пользователю {owner_id}: {e}")

    # Кружок (video_note)
    elif reply.video_note:
        file_id = reply.video_note.file_id
        file_size = getattr(reply.video_note, "file_size", None)
        if _media_size_is_too_large(file_size):
            logger.warning(
                "media: skip protected video note for owner_id={}, size={} exceeds limit={}",
                owner_id,
                _format_bytes(file_size),
                _format_bytes(MAX_MEDIA_SIZE_BYTES),
            )
            return

        note_file = await _download_media(
            bot,
            file_id=file_id,
            file_path_hint=None,
        )

        try:
            await bot.send_video_note(owner_id, video_note=note_file)
        except Exception as e:
            logger.error(f"Ошибка при отправке видео-заметки пользователю {owner_id}: {e}")

    else:
        logger.info("Защищённое сообщение без фото/видео/video_note — пропущено.")
        return

@router.business_message()
async def handle_business_message(message: types.Message, bot: Bot) -> None:
    connection_id: str | None = message.business_connection_id
    if not connection_id:
        logger.warning("business: business_connection_id отсутствует")
        return

    owner = await crud_user.get_user_by_connection_id(connection_id)
    if not owner:
        logger.error(f"business: не найден пользователь с connection_id={connection_id}")
        return
    owner_id: str = str(owner.tgID)

    chat_id: str = str(message.chat.id)
    if not message.from_user:
        logger.warning(f"business: message.from_user отсутствует для chat_id={chat_id}")
        return
    from_id: str = str(message.from_user.id)

    # Если пишет клиент — обрабатываем медиа-ответы и выходим
    if chat_id != from_id:
        await media_with_timer(message, bot, owner_id)
        return

    await crud_chat.ensure_chat_exists(chat_id=chat_id, user_id=owner_id)
    encrypted_content = encrypt(message.text or "")
    await crud_message.add_message(
        msg_id=message.message_id,
        from_user=from_id,
        to_user=owner_id,
        content=encrypted_content,
        m_type="text",
    )


@router.edited_business_message()
async def edited_business_message(message: types.Message, bot: Bot) -> None:
    chat_id: str = str(message.chat.id)
    msg_id: str = str(message.message_id)
    connection_id: str | None = message.business_connection_id

    if not connection_id:
        logger.warning("edited: business_connection_id отсутствует")
        return

    owner = await crud_user.get_user_by_connection_id(connection_id)
    if not owner:
        logger.error(f"edited: нет user с connection_id={connection_id}")
        return
    owner_id: str = str(owner.tgID)

    editor_id: str | None = str(message.from_user.id) if message.from_user else None
    new_content_raw: str = message.text or message.caption or ""
    new_content_enc = encrypt(new_content_raw)

    # ===== 1) Если редактирует владелец — обновляем и выходим без уведомлений =====
    if editor_id == owner_id:
        try:
            # Предпочтительно — апдейт по msg_id (если у тебя есть такой метод)
            if hasattr(crud_message, "update_message_content_by_msg_id"):
                await crud_message.update_message_content_by_msg_id(
                    msg_id=msg_id,
                    new_content=new_content_enc,
                )
            else:
                # Фолбэк: если в БД сообщения владельца хранятся как from_user=owner_id,to_user=owner_id
                # и/или у тебя нет апдейта по одному msg_id — адаптируй под свою схему.
                await crud_message.update_message_content(
                    msg_id=msg_id,
                    from_user=owner_id,
                    to_user=owner_id,
                    new_content=new_content_enc,
                )
        except Exception as e:
            logger.error(f"edited(owner): ошибка апдейта msg_id={msg_id}: {e}")
        logger.info(f"edited(owner): msg_id={msg_id} обновлён, уведомления не отправлены.")
        return

    # ===== 2) Редактирует клиент — ищем исходное сообщение клиента =====
    stored_msg = await crud_message.get_message_by_ids(
        msg_id=msg_id,
        from_user=chat_id,   # у клиентских сообщений from_user == chat_id
        to_user=owner_id,
    )
    if not stored_msg:
        logger.warning(f"edited: не нашли msg_id={msg_id} (client->{owner_id}) в БД")
        return

    old_content_raw = decrypt(stored_msg.content) if stored_msg.content else ""

    # если изменений нет — не спамим владельца
    if (old_content_raw or "") == new_content_raw:
        logger.info(f"edited: содержимое не изменилось (msg_id={msg_id}) — уведомление не шлём.")
        return

    # ===== 3) Обновляем БД =====
    try:
        await crud_message.update_message_content(
            msg_id=msg_id,
            from_user=chat_id,
            to_user=owner_id,
            new_content=new_content_enc,
        )
    except Exception as e:
        logger.error(f"edited: ошибка обновления БД для msg_id={msg_id}: {e}")

    # ===== 4) Уведомляем владельца о правке клиента =====
    client_name: str = (message.from_user.full_name if message.from_user else "Клиент")
    client_username: str = (message.from_user.username if message.from_user and message.from_user.username else "—")

    try:
        await bot.send_message(
            chat_id=owner_id,
            text=(
                "⚠️ <b>Отредактировано сообщение</b>\n\n"
                f"👤 <b>Пользователь:</b> {html_escape(client_name)} (@{html_escape(client_username)})\n\n"
                "<b>💬 До редактирования:</b>\n"
                f"<code>{html_escape(old_content_raw)}</code>\n\n"
                "<b>✏️ После редактирования:</b>\n"
                f"<code>{html_escape(new_content_raw)}</code>"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"edited: не смог отправить владельцу {owner_id}: {e}")


@router.deleted_business_messages()
async def deleted_business_message(
    event: types.BusinessMessagesDeleted, bot: Bot
) -> None:
    chat_id: str = str(event.chat.id)
    connection_id: str | None = event.business_connection_id
    msg_ids: list[str] = [str(mid) for mid in event.message_ids]

    if not connection_id:
        logger.warning("deleted: business_connection_id отсутствует")
        return

    owner = await crud_user.get_user_by_connection_id(connection_id)
    if not owner:
        logger.error(f"deleted: нет user c connection_id={connection_id}")
        return
    owner_id: str = str(owner.tgID)  # ← всегда строка

    try:
        client_chat = await bot.get_chat(chat_id)
        client_name = (
            f"{client_chat.first_name or ''} {client_chat.last_name or ''}".strip() or "Клиент"
        )
        client_username = client_chat.username or "—"
    except Exception:
        client_name = "Клиент"
        client_username = "—"

    for msg_id in msg_ids:
        stored_msg = await crud_message.get_message_by_ids(
            msg_id=msg_id,
            from_user=chat_id,
            to_user=owner_id,
        )
        if not stored_msg:
            logger.warning(f"deleted: msg_id={msg_id} не найден в БД")
            continue

        # ⛔ не уведомляем, если удалено сообщение владельца
        try:
            if str(getattr(stored_msg, "from_user", "")) == owner_id:
                logger.info(f"deleted: msg_id={msg_id} — удалено сообщение владельца, пропускаем уведомление.")
                continue
        except Exception:
            # если в записи нет поля from_user — просто продолжаем обычный флоу
            pass

        decrypted = decrypt(stored_msg.content) if getattr(stored_msg, "content", None) else ""
        decrypted_safe = html_escape(decrypted)

        # не шлём пустые «удалённые» уведомления
        if decrypted_safe.strip() == "":
            logger.info(f"deleted: msg_id={msg_id} — пустое содержимое, уведомление не отправляем.")
            continue

        try:
            await bot.send_message(
                chat_id=owner_id,
                text=(
                    "🚨 <b>Зафиксировано удаление сообщения</b>\n\n"
                    f"<b>👤 Пользователь:</b> {html_escape(client_name)} (@{html_escape(client_username)})\n\n"
                    "<b>🗑 Удалённое сообщение:</b>\n"
                    f"<code>{decrypted_safe}</code>"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"deleted: не смог отправить владельцу {owner_id}: {e}")


async def send_private_message(bot: Bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except TelegramForbiddenError:
        print(f"⛔ Пользователь {user_id} запретил писать ему в личку.")
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения пользователю {user_id}: {e}")
