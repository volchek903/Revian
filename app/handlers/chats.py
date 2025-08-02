import asyncio
from aiogram import F, Bot, Dispatcher, types, exceptions, Router
from loguru import logger
from aiogram.types import Update, BusinessConnection
import json
from aiogram.enums import UpdateType
from aiogram.exceptions import TelegramForbiddenError
from app.repository.chat import crud_chat
from app.repository.user import crud_user
from app.repository.message import crud_message
from app.utils.encription import encrypt, decrypt

router = Router()


async def set_message(message: types.Message) -> None:
    try:
        logger.info(f"Сообщение сохранено: {message.chat.id}:{message.message_id}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении сообщения: {e}")


@router.business_connection()
async def on_business_connection_change(conn: BusinessConnection):
    user = conn.user
    user_id = str(user.id)
    connection_id = conn.id
    if conn.is_enabled:
        logger.success(f"🤖 Бот подключён к бизнес-аккаунту пользователя {user_id}")
        await crud_chat.activate_all_by_user_id(user_id)
        await crud_user.update_connection_id(
            user_id=user_id, connection_id=connection_id
        )
    else:
        logger.warning(f"🚫 Бот отключён от бизнес-аккаунта пользователя {user_id}")
        await crud_chat.deactivate_all_by_user_id(user_id)


@router.business_message()
async def handle_business_message(message: types.Message) -> None:
    chat_id: str = str(message.chat.id)
    from_id: str = str(message.from_user.id)

    if chat_id != from_id:
        return

    connection_id: str | None = message.business_connection_id
    if not connection_id:
        logger.warning("business_connection_id отсутствует в сообщении")
        return

    owner = await crud_user.get_user_by_connection_id(connection_id)
    if not owner:
        logger.error(f"Не найден пользователь с connection_id={connection_id}")
        return
    owner_id: str = owner.tgID

    await crud_chat.ensure_chat_exists(chat_id=chat_id, user_id=owner_id)

    encrypted_content = encrypt(message.text or "")

    await crud_message.add_message(
        msg_id=message.message_id,
        from_user=chat_id,
        to_user=owner_id,
        content=encrypted_content,
        m_type="text",
    )

    # logger.info(
    #     f"💾 Сохранено сообщение {message.message_id} "
    #     f"от клиента {chat_id} владельцу {owner_id}"
    # )


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
    owner_id: str = owner.tgID

    stored_msg = await crud_message.get_message_by_ids(
        msg_id=msg_id,
        from_user=chat_id,
        to_user=owner_id,
    )
    if not stored_msg:
        logger.warning(f"edited: не нашли msg_id={msg_id} в БД")
        return

    client_name: str = message.from_user.full_name
    client_username: str = message.from_user.username or "—"
    new_content: str = message.text or message.caption or ""
    decrypted_old = decrypt(stored_msg.content)

    try:
        await bot.send_message(
            chat_id=owner_id,
            text=(
                "⚠️ <b>Отредактировано сообщение</b> ⚠️\n\n"
                f"👤 <b>Пользователь:</b> {client_name} (@{client_username})\n\n"
                "<b>💬 До редактирования:</b>\n"
                f"<code>{decrypted_old}</code>\n\n"
                "<b>✏️ После редактирования:</b>\n"
                f"<code>{new_content}</code>"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"edited: не смог отправить владельцу {owner_id}: {e}")

    try:
        await crud_message.update_message_content(
            msg_id=msg_id,
            from_user=chat_id,
            to_user=owner_id,
            new_content=encrypt(new_content),
        )
        # logger.info(
        #     f"✏️ msg_id={msg_id} обновлён | "
        #     f"{client_name} → owner {owner_id} | "
        #     f"«{decrypted_old[:30]}…» → «{new_content[:30]}…»"
        # )
    except Exception as e:
        logger.error(f"edited: ошибка при обновлении БД для msg_id={msg_id}: {e}")


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
    owner_id: str = owner.tgID

    try:
        client_chat = await bot.get_chat(chat_id)
        client_name = (
            f"{client_chat.first_name or ''} {client_chat.last_name or ''}".strip()
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

        decrypted = decrypt(stored_msg.content)

        try:
            await bot.send_message(
                chat_id=owner_id,
                text=(
                    "🚨 <b>Зафиксировано удаление сообщения</b> 🚨\n\n"
                    f"<b>👤 Пользователь:</b> {client_name} (@{client_username})\n\n"
                    "<b>🗑 Удалённое сообщение:</b>\n"
                    f"<code>{decrypted}</code>"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"deleted: не смог отправить владельцу {owner_id}: {e}")

        # logger.info(f"🗑 Уведомили owner={owner_id} об удалении msg_id={msg_id}")


async def send_private_message(bot: Bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except TelegramForbiddenError:
        print(f"⛔ Пользователь {user_id} запретил писать ему в личку.")
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения пользователю {user_id}: {e}")
