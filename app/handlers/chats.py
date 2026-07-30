import asyncio
from dataclasses import dataclass
from html import escape as html_escape
from io import BytesIO
from pathlib import Path
from time import monotonic

from aiogram import Bot, Router, types
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import BufferedInputFile, BusinessConnection
from loguru import logger

from app.core.config import settings
from app.repository.chat import crud_chat
from app.repository.message import crud_message
from app.repository.user import crud_user
from app.utils.encription import encrypt, decrypt
from app.utils.trial import build_trial_state

router = Router()
MEDIA_DOWNLOAD_SEMAPHORE = asyncio.Semaphore(settings.MEDIA_DOWNLOAD_CONCURRENCY)
MAX_MEDIA_SIZE_BYTES = settings.MAX_MEDIA_SIZE_MB * 1024 * 1024
OWNER_CACHE_TTL_SEC = 300.0
KNOWN_CHAT_CACHE_TTL_SEC = 3600.0
CLIENT_CHAT_CACHE_TTL_SEC = 600.0
TRIAL_NOTICE_COOLDOWN_SEC = settings.TRIAL_NOTICE_COOLDOWN_MINUTES * 60.0


@dataclass(slots=True, frozen=True)
class OwnerRef:
    tg_id: str
    connection_id: str | None = None


_owner_cache_by_connection: dict[str, tuple[float, OwnerRef]] = {}
_owner_cache_by_chat: dict[str, tuple[float, OwnerRef]] = {}
_owner_cache_by_sender: dict[str, tuple[float, OwnerRef]] = {}
_known_chat_cache: dict[tuple[str, str], float] = {}
_client_chat_cache: dict[str, tuple[float, tuple[str, str]]] = {}
_trial_notice_cache: dict[str, float] = {}


async def set_message(message: types.Message) -> None:
    try:
        logger.info(f"Сообщение сохранено: {message.chat.id}:{message.message_id}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении сообщения: {e}")


def _build_trial_expired_text(user) -> str:
    return (
        "⛔ <b>Испытательный срок закончился</b>\n\n"
        "Новые сообщения больше не записываются, а уведомления по этому чату остановлены.\n\n"
        f"Чтобы получить ещё {settings.REFERRAL_BONUS_HOURS} часов бесплатно, "
        "пригласи друга по своему коду:\n"
        f"<code>{html_escape(user.ref_code)}</code>\n\n"
        f"Или обратись к владельцу {html_escape(settings.TRIAL_SUPPORT_HANDLE)}."
    )


async def _ensure_trial_access(bot: Bot, owner_id: str, *, force_notice: bool = False) -> bool:
    user = await crud_user.get_user_by_tg_id(owner_id)
    if not user:
        return False

    trial_state = build_trial_state(user)
    if trial_state.is_active:
        _trial_notice_cache.pop(owner_id, None)
        return True

    now = monotonic()
    send_notice = force_notice
    expires_at = _trial_notice_cache.get(owner_id)
    if expires_at is None or expires_at <= now:
        send_notice = True
        _trial_notice_cache[owner_id] = now + TRIAL_NOTICE_COOLDOWN_SEC

    if not send_notice:
        return False

    try:
        await bot.send_message(
            chat_id=owner_id,
            text=_build_trial_expired_text(user),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(
            f"trial: не удалось отправить уведомление об окончании доступа user_id={owner_id}: {e}"
        )

    return False


def _format_bytes(size_bytes: int) -> str:
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _media_size_is_too_large(size_bytes: int | None) -> bool:
    return size_bytes is not None and size_bytes > MAX_MEDIA_SIZE_BYTES


def _get_cached_entry(cache: dict, key):
    if not key:
        return None

    cached = cache.get(key)
    if not cached:
        return None

    expires_at, value = cached
    if expires_at <= monotonic():
        cache.pop(key, None)
        return None

    return value


def _set_cached_entry(cache: dict, key, value, ttl_sec: float) -> None:
    if key:
        cache[key] = (monotonic() + ttl_sec, value)


def _owner_from_user(user) -> OwnerRef:
    return OwnerRef(
        tg_id=str(user.tgID),
        connection_id=getattr(user, "connection_id", None),
    )


def _cache_owner(
    owner: OwnerRef,
    *,
    connection_id: str | None,
    chat_id: str | None,
    sender_id: str | None = None,
) -> None:
    _set_cached_entry(_owner_cache_by_chat, chat_id, owner, OWNER_CACHE_TTL_SEC)
    _set_cached_entry(
        _owner_cache_by_sender,
        sender_id,
        owner,
        OWNER_CACHE_TTL_SEC,
    )
    _set_cached_entry(
        _owner_cache_by_connection,
        connection_id or owner.connection_id,
        owner,
        OWNER_CACHE_TTL_SEC,
    )


def _drop_owner_cache(
    *,
    connection_id: str | None,
    chat_id: str | None,
    sender_id: str | None = None,
) -> None:
    if connection_id:
        _owner_cache_by_connection.pop(connection_id, None)
    if chat_id:
        _owner_cache_by_chat.pop(chat_id, None)
    if sender_id:
        _owner_cache_by_sender.pop(sender_id, None)


async def _ensure_chat_registered(chat_id: str, user_id: str) -> None:
    key = (chat_id, user_id)
    expires_at = _known_chat_cache.get(key)
    now = monotonic()

    if expires_at and expires_at > now:
        return

    await crud_chat.ensure_chat_exists(chat_id=chat_id, user_id=user_id)
    _known_chat_cache[key] = now + KNOWN_CHAT_CACHE_TTL_SEC


async def _resolve_client_identity(bot: Bot, chat_id: str) -> tuple[str, str]:
    cached = _get_cached_entry(_client_chat_cache, chat_id)
    if cached:
        return cached

    try:
        client_chat = await bot.get_chat(chat_id)
        client_name = (
            f"{client_chat.first_name or ''} {client_chat.last_name or ''}".strip()
            or "Клиент"
        )
        client_username = client_chat.username or "—"
    except Exception:
        client_name = "Клиент"
        client_username = "—"

    result = (client_name, client_username)
    _set_cached_entry(_client_chat_cache, chat_id, result, CLIENT_CHAT_CACHE_TTL_SEC)
    return result


def _build_deleted_notifications(
    client_name: str,
    client_username: str,
    deleted_payloads: list[str],
) -> list[str]:
    if not deleted_payloads:
        return []

    header = (
        "🗑 <b>Клиент удалил сообщение</b>\n\n"
        f"<b>Пользователь:</b> {html_escape(client_name)} (@{html_escape(client_username)})"
    )
    notifications: list[str] = []
    current = header

    for index, payload in enumerate(deleted_payloads, start=1):
        block = f"\n\n<b>Сообщение {index}:</b>\n<code>{payload}</code>"
        if len(current) + len(block) > 3500 and current != header:
            notifications.append(current)
            current = header + block
        else:
            current += block

    if current != header:
        notifications.append(current)

    return notifications


def _client_attachment_label(message: types.Message) -> str | None:
    if message.document:
        return "документ"
    if message.voice:
        return "голосовое сообщение"
    if message.audio:
        return "аудио"
    if message.photo:
        return "фото"
    if message.video:
        return "видео"
    if message.video_note:
        return "видеосообщение"
    if message.animation:
        return "анимацию"
    return None


async def _send_attachment_by_file_id(
    message: types.Message,
    bot: Bot,
    owner_id: str,
) -> bool:
    caption = message.caption or None

    if message.document:
        await bot.send_document(
            owner_id,
            document=message.document.file_id,
            caption=caption,
        )
        return True

    if message.voice:
        await bot.send_voice(
            owner_id,
            voice=message.voice.file_id,
            caption=caption,
        )
        return True

    if message.audio:
        await bot.send_audio(
            owner_id,
            audio=message.audio.file_id,
            caption=caption,
        )
        return True

    if message.photo:
        await bot.send_photo(
            owner_id,
            photo=message.photo[-1].file_id,
            caption=caption,
        )
        return True

    if message.video:
        await bot.send_video(
            owner_id,
            video=message.video.file_id,
            caption=caption,
            width=message.video.width,
            height=message.video.height,
            supports_streaming=True,
        )
        return True

    if message.video_note:
        await bot.send_video_note(
            owner_id,
            video_note=message.video_note.file_id,
        )
        return True

    if message.animation:
        await bot.send_animation(
            owner_id,
            animation=message.animation.file_id,
            caption=caption,
        )
        return True

    return False


async def _mirror_client_attachment(
    message: types.Message,
    bot: Bot,
    owner_id: str,
) -> bool:
    attachment_label = _client_attachment_label(message)
    if not attachment_label:
        return False

    sender_name = (
        html_escape(message.from_user.full_name)
        if message.from_user and message.from_user.full_name
        else "Клиент"
    )
    sender_username = (
        f"@{html_escape(message.from_user.username)}"
        if message.from_user and message.from_user.username
        else "—"
    )

    notice_text = (
        f"📎 <b>Клиент отправил {attachment_label}</b>\n\n"
        f"<b>Пользователь:</b> {sender_name} ({sender_username})"
    )

    try:
        await bot.copy_message(
            chat_id=owner_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await bot.send_message(
            chat_id=owner_id,
            text=notice_text,
            parse_mode="HTML",
        )
        return True
    except Exception as copy_error:
        logger.warning(
            "mirror: copy_message failed for owner_id={}, message_id={}, error={}",
            owner_id,
            message.message_id,
            copy_error,
        )

    try:
        sent = await _send_attachment_by_file_id(message, bot, owner_id)
        if not sent:
            return False
        await bot.send_message(
            chat_id=owner_id,
            text=notice_text,
            parse_mode="HTML",
        )
        return True
    except Exception as send_error:
        logger.warning(
            "mirror: send by file_id failed for owner_id={}, message_id={}, error={}",
            owner_id,
            message.message_id,
            send_error,
        )
        return False


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


async def _resolve_owner(
    *,
    connection_id: str | None,
    chat_id: str,
    sender_id: str | None = None,
):
    cached_owner = _get_cached_entry(_owner_cache_by_connection, connection_id)
    if cached_owner:
        return cached_owner

    cached_owner = _get_cached_entry(_owner_cache_by_chat, chat_id)
    if cached_owner:
        return cached_owner

    cached_owner = _get_cached_entry(_owner_cache_by_sender, sender_id)
    if cached_owner:
        return cached_owner

    owner = None

    if connection_id:
        owner = await crud_user.get_user_by_connection_id(connection_id)
        if owner:
            resolved_owner = _owner_from_user(owner)
            _cache_owner(
                resolved_owner,
                connection_id=connection_id,
                chat_id=chat_id,
                sender_id=sender_id,
            )
            return resolved_owner
        logger.warning(
            f"business: connection_id={connection_id} not found, trying fallback resolution for chat_id={chat_id}"
        )

    owner = await crud_user.get_user_by_tg_id(chat_id)
    if owner:
        if connection_id and owner.connection_id != connection_id:
            await crud_user.update_connection_id(str(owner.tgID), connection_id)
            owner.connection_id = connection_id
            logger.debug(
                f"business: refreshed connection_id for owner_id={owner.tgID} via direct user match"
            )
        resolved_owner = _owner_from_user(owner)
        _cache_owner(
            resolved_owner,
            connection_id=connection_id,
            chat_id=chat_id,
            sender_id=sender_id,
        )
        return resolved_owner

    if sender_id:
        owner = await crud_user.get_user_by_tg_id(sender_id)
        if owner:
            if connection_id and owner.connection_id != connection_id:
                await crud_user.update_connection_id(str(owner.tgID), connection_id)
                owner.connection_id = connection_id
                logger.debug(
                    f"business: refreshed connection_id for owner_id={owner.tgID} via sender_id={sender_id}"
                )
            resolved_owner = _owner_from_user(owner)
            _cache_owner(
                resolved_owner,
                connection_id=connection_id,
                chat_id=chat_id,
                sender_id=sender_id,
            )
            return resolved_owner

    chat = await crud_chat.get_chat_by_chat_id(chat_id)
    if not chat:
        return None

    owner = await crud_user.get_user_by_tg_id(str(chat.user_id))
    if not owner:
        return None

    if connection_id and owner.connection_id != connection_id:
        await crud_user.update_connection_id(str(owner.tgID), connection_id)
        owner.connection_id = connection_id
        logger.debug(
            f"business: refreshed connection_id for owner_id={owner.tgID} via chat_id={chat_id}"
        )

    resolved_owner = _owner_from_user(owner)
    _cache_owner(
        resolved_owner,
        connection_id=connection_id,
        chat_id=chat_id,
        sender_id=sender_id,
    )
    return resolved_owner


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
        _cache_owner(
            OwnerRef(tg_id=user_id, connection_id=connection_id),
            connection_id=connection_id,
            chat_id=user_id,
            sender_id=user_id,
        )

        if not await _ensure_trial_access(bot, user_id, force_notice=True):
            return

        welcome_text = (
            "✅ <b>Revian подключён</b>\n\n"
            "Теперь я отслеживаю выбранные чаты и сразу сообщу, если собеседник:\n"
            "• удалит сообщение\n"
            "• изменит уже отправленный текст\n"
            "• пришлёт исчезающее медиа\n\n"
            "Открыть меню и настройки можно в любой момент через команду /start."
        )
        try:
            await bot.send_message(chat_id=user_id, text=welcome_text)
        except Exception as e:
            logger.warning(f"Не удалось отправить приветственное сообщение {user_id}: {e}")

    else:
        logger.warning(f"🚫 Бот отключён от бизнес-аккаунта пользователя {user_id}")
        _drop_owner_cache(
            connection_id=connection_id,
            chat_id=user_id,
            sender_id=user_id,
        )

        # Деактивируем чаты
        await crud_chat.deactivate_all_by_user_id(user_id)

        # Прощальное сообщение
        farewell_text = (
            "⏸ <b>Revian отключён</b>\n\n"
            "Я больше не получаю события из подключённых чатов, "
            "поэтому новые удаления и правки отслеживаться не будут.\n\n"
            "Если захочешь вернуться, просто подключи меня заново."
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
        logger.debug("Ответ на сообщение владельца — не пересылаем обратно владельцу.")
        return

    if reply.from_user and (str(reply.from_user.id) == str(message.from_user.id)):
        logger.debug("Ответ на собственное сообщение — пропускаем медиа-обработку.")
        return

    # Только защищённые/скрытые медиа
    is_protected = bool(getattr(reply, "has_protected_content", False))
    if not is_protected:
        logger.debug("Медиа без защиты (has_protected_content != True) — пропускаем обработку.")
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
            await bot.send_photo(
                owner_id,
                photo=photo_file,
                caption=(
                    "🫥 <b>Сохранено исчезающее фото</b>\n"
                    "Медиа было перехвачено до того, как оно исчезло из чата."
                ),
            )
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
                caption=(
                    "🫥 <b>Сохранено исчезающее видео</b>\n"
                    "Медиа было перехвачено до того, как оно исчезло из чата."
                ),
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
            await bot.send_message(
                owner_id,
                "🫥 <b>Сохранено исчезающее видеосообщение</b>",
            )
            await bot.send_video_note(owner_id, video_note=note_file)
        except Exception as e:
            logger.error(f"Ошибка при отправке видео-заметки пользователю {owner_id}: {e}")

    else:
        logger.debug("Защищённое сообщение без фото/видео/video_note — пропущено.")
        return

@router.business_message()
async def handle_business_message(message: types.Message, bot: Bot) -> None:
    connection_id: str | None = message.business_connection_id
    chat_id: str = str(message.chat.id)
    if not message.from_user:
        logger.warning(f"business: message.from_user отсутствует для chat_id={chat_id}")
        return
    from_id: str = str(message.from_user.id)

    if not connection_id:
        logger.warning(f"business: business_connection_id отсутствует для chat_id={chat_id}")

    owner = await _resolve_owner(
        connection_id=connection_id,
        chat_id=chat_id,
        sender_id=from_id,
    )
    if not owner:
        logger.error(f"business: не найден пользователь с connection_id={connection_id}")
        return
    owner_id: str = owner.tg_id
    if not await _ensure_trial_access(bot, owner_id):
        return

    # Если пишет клиент — обрабатываем медиа-ответы и выходим
    if chat_id != from_id:
        await _mirror_client_attachment(message, bot, owner_id)
        await media_with_timer(message, bot, owner_id)
        return

    await _ensure_chat_registered(chat_id=chat_id, user_id=owner_id)
    encrypted_content = encrypt(message.text or message.caption or "")
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
    editor_id: str | None = str(message.from_user.id) if message.from_user else None

    if not connection_id:
        logger.warning(f"edited: business_connection_id отсутствует для chat_id={chat_id}")

    owner = await _resolve_owner(
        connection_id=connection_id,
        chat_id=chat_id,
        sender_id=editor_id,
    )
    if not owner:
        logger.error(
            f"edited: нет user с connection_id={connection_id} и chat_id={chat_id}"
        )
        return
    owner_id: str = owner.tg_id
    if not await _ensure_trial_access(bot, owner_id):
        return

    new_content_raw: str = message.text or message.caption or ""

    # В текущей схеме сохраняются только сообщения клиента, поэтому
    # редактирование сообщений владельца не требует работы с БД.
    if editor_id == owner_id:
        logger.debug(
            f"edited(owner): msg_id={msg_id} пропущен без обновления — уведомления не отправлены."
        )
        return

    # ===== 2) Редактирует клиент — ищем исходное сообщение клиента =====
    stored_msg = await crud_message.get_message_by_ids(
        msg_id=msg_id,
        from_user=chat_id,   # у клиентских сообщений from_user == chat_id
        to_user=owner_id,
    )
    if not stored_msg:
        logger.debug(f"edited: не нашли msg_id={msg_id} (client->{owner_id}) в БД")
        return

    old_content_raw = decrypt(stored_msg.content) if stored_msg.content else ""

    # если изменений нет — не спамим владельца
    if (old_content_raw or "") == new_content_raw:
        logger.debug(f"edited: содержимое не изменилось (msg_id={msg_id}) — уведомление не шлём.")
        return

    # ===== 3) Обновляем БД =====
    try:
        new_content_enc = encrypt(new_content_raw)
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
                "✏️ <b>Клиент изменил сообщение</b>\n\n"
                f"<b>Пользователь:</b> {html_escape(client_name)} (@{html_escape(client_username)})\n\n"
                "<b>Было:</b>\n"
                f"<code>{html_escape(old_content_raw)}</code>\n\n"
                "<b>Стало:</b>\n"
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
        logger.warning(f"deleted: business_connection_id отсутствует для chat_id={chat_id}")

    owner = await _resolve_owner(connection_id=connection_id, chat_id=chat_id)
    if not owner:
        logger.error(
            f"deleted: нет user c connection_id={connection_id} и chat_id={chat_id}"
        )
        return
    owner_id: str = owner.tg_id
    if not await _ensure_trial_access(bot, owner_id):
        return
    client_name, client_username = await _resolve_client_identity(bot, chat_id)
    stored_messages = await crud_message.get_messages_by_ids(
        msg_ids=msg_ids,
        from_user=chat_id,
        to_user=owner_id,
    )
    deleted_payloads: list[str] = []

    for msg_id in msg_ids:
        stored_msg = stored_messages.get(msg_id)
        if not stored_msg:
            logger.debug(f"deleted: msg_id={msg_id} не найден в БД")
            continue

        # ⛔ не уведомляем, если удалено сообщение владельца
        try:
            if str(getattr(stored_msg, "from_user", "")) == owner_id:
                logger.debug(
                    f"deleted: msg_id={msg_id} — удалено сообщение владельца, пропускаем уведомление."
                )
                continue
        except Exception:
            # если в записи нет поля from_user — просто продолжаем обычный флоу
            pass

        decrypted = decrypt(stored_msg.content) if getattr(stored_msg, "content", None) else ""
        decrypted_safe = html_escape(decrypted)

        # не шлём пустые «удалённые» уведомления
        if decrypted_safe.strip() == "":
            logger.debug(f"deleted: msg_id={msg_id} — пустое содержимое, уведомление не отправляем.")
            continue
        deleted_payloads.append(decrypted_safe)

    for notification in _build_deleted_notifications(
        client_name,
        client_username,
        deleted_payloads,
    ):
        try:
            await bot.send_message(
                chat_id=owner_id,
                text=notification,
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
