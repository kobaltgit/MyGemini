# File: handlers/telegram_helpers.py
"""
Модуль со вспомогательными функциями для взаимодействия с Telegram API.
"""
import asyncio
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from telebot import apihelper

from config.settings import ADMIN_USER_ID
from logger_config import get_logger
from utils import text_helpers as th

# Получаем логгер для этого модуля
logger = get_logger(__name__)


# --- Функции для отправки сообщений ---

async def send_typing_action(bot: AsyncTeleBot, chat_id: int):
    """Отправляет действие 'печатает...' в чат."""
    try:
        await bot.send_chat_action(chat_id, 'typing')
    except apihelper.ApiException as e:
        logger.debug(f"Не удалось отправить typing action в чат {chat_id}: {e}", extra={'user_id': str(chat_id)})


async def send_long_message(bot: AsyncTeleBot, chat_id: int, text: str, **kwargs):
    """
    Отправляет длинное сообщение, разбивая его на части, если необходимо.
    Использует утилиту `text_helpers.split_message`.
    """
    if not text:
        return

    parts = th.split_message(text)
    total_parts = len(parts)

    for i, part in enumerate(parts):
        # Для последней части передаем все оригинальные kwargs (например, reply_markup)
        if i == total_parts - 1:
            await bot.send_message(chat_id, part, **kwargs)
        else:
            # Для промежуточных частей отключаем превью ссылок, чтобы избежать лишнего шума
            parse_mode = kwargs.get('parse_mode')
            await bot.send_message(chat_id, part, parse_mode=parse_mode, disable_web_page_preview=True)
            await asyncio.sleep(0.5)  # Небольшая задержка между сообщениями


async def send_error_reply(bot: AsyncTeleBot, message: types.Message, error_log_message: str,
                           user_reply_text: str = "Произошла внутренняя ошибка. Попробуйте позже."):
    """Логирует ошибку и отправляет пользователю стандартизированный ответ."""
    user_id = message.chat.id
    logger.exception(error_log_message, extra={'user_id': str(user_id)})

    try:
        await bot.reply_to(message, user_reply_text, parse_mode=None)
    except apihelper.ApiException as e:
        logger.error(f"Не удалось отправить сообщение об ошибке пользователю {user_id}: {e}", extra={'user_id': str(user_id)})

    if ADMIN_USER_ID and ADMIN_USER_ID != user_id:
        try:
            admin_notification = (f"⚠️ *Критическая ошибка у пользователя {user_id}* ⚠️\n\n"
                                  f"```\n{error_log_message}\n```\n\n"
                                  f"Сообщение пользователя: `{message.text or 'Не текстовое сообщение'}`")
            await bot.send_message(ADMIN_USER_ID, admin_notification, parse_mode='Markdown')
        except apihelper.ApiException as e:
            logger.error(f"Не удалось отправить уведомление об ошибке администратору: {e}", extra={'user_id': 'System'})


# --- Функции для работы с колбэками и редактированием ---

async def answer_callback_query(bot: AsyncTeleBot, call: types.CallbackQuery, text=None, show_alert=False, cache_time=0):
    """Безопасно отвечает на callback query."""
    try:
        await bot.answer_callback_query(call.id, text=text, show_alert=show_alert, cache_time=cache_time)
    except apihelper.ApiException as e:
        logger.debug(f"Ошибка при ответе на callback query {call.id} (возможно, устарел): {e}", extra={'user_id': str(call.from_user.id)})


async def edit_message_text_safe(bot: AsyncTeleBot, chat_id: int, message_id: int, text: str, **kwargs):
    """
    Редактирует текст сообщения с обработкой распространенных ошибок,
    таких как 'message is not modified' или ошибки парсинга Markdown.
    """
    try:
        await bot.edit_message_text(text, chat_id, message_id, **kwargs)
    except apihelper.ApiException as e:
        if "message is not modified" in str(e).lower():
            logger.debug(f"Сообщение {message_id} не было изменено (текст совпадает).", extra={'user_id': str(chat_id)})
        elif kwargs.get('parse_mode') == 'Markdown' and "can't parse entities" in str(e).lower():
            logger.warning(f"Ошибка парсинга Markdown при редактировании сообщения {message_id}. Повторная попытка без форматирования.", extra={'user_id': str(chat_id)})
            try:
                kwargs['parse_mode'] = None
                await bot.edit_message_text(text, chat_id, message_id, **kwargs)
            except apihelper.ApiException as fallback_e:
                logger.error(f"Не удалось отредактировать сообщение {message_id} даже без форматирования: {fallback_e}", extra={'user_id': str(chat_id)})
        else:
            logger.error(f"API-ошибка при редактировании сообщения {message_id}: {e}", extra={'user_id': str(chat_id)})
