# File: handlers/telegram_helpers.py
"""
Модуль со вспомогательными функциями для взаимодействия с Telegram API.
Использует langchain.text_splitter для надежного разделения сообщений.
"""
import asyncio
import re
import html
from typing import Optional

from telebot.async_telebot import AsyncTeleBot
from telebot import types
from telebot import apihelper

# НОВЫЙ ИМПОРТ: Используем надежный сплиттер из langchain
from langchain.text_splitter import MarkdownTextSplitter
from chatgpt_md_converter import telegram_format

from config.settings import ADMIN_USER_ID
from logger_config import get_logger
from utils import text_helpers as th
from utils import markup_helpers as mk
from utils import localization as loc
from database import db_manager

logger = get_logger(__name__)

_bot_instance: Optional[AsyncTeleBot] = None

# Инициализируем сплиттер один раз при старте
# Устанавливаем безопасный лимит, чтобы оставить место для HTML-тегов
markdown_splitter = MarkdownTextSplitter(chunk_size=3800, chunk_overlap=0)


def register_bot_instance(bot: AsyncTeleBot):
    """Регистрирует глобальный экземпляр бота для использования в хелперах."""
    global _bot_instance
    _bot_instance = bot
    logger.info("Экземпляр бота зарегистрирован в telegram_helpers.")

# --- Функции для отправки сообщений ---

async def send_typing_action(bot: AsyncTeleBot, chat_id: int):
    """Отправляет действие 'печатает...' в чат."""
    try:
        await bot.send_chat_action(chat_id, 'typing')
    except apihelper.ApiException as e:
        logger.debug(f"Не удалось отправить typing action в чат {chat_id}: {e}", extra={'user_id': str(chat_id)})


async def send_long_message(bot: AsyncTeleBot, chat_id: int, text: str, **kwargs):
    """
    Отправляет длинное сообщение, используя langchain.MarkdownTextSplitter
    для корректного разделения на части.
    """
    if not text:
        return

    kwargs.pop('parse_mode', None)

    try:
        # 1. Используем langchain для разделения Markdown на семантически корректные части
        markdown_chunks = markdown_splitter.split_text(text)
        
        total_parts = len(markdown_chunks)
        if total_parts == 0:
            return

        for i, md_chunk in enumerate(markdown_chunks):
            # 2. Конвертируем каждый фрагмент в HTML, совместимый с Telegram
            html_chunk = telegram_format(md_chunk)

            if not html_chunk or html_chunk.isspace():
                continue

            current_kwargs = {}
            # Для последней части передаем все оригинальные kwargs (например, reply_markup)
            if i == total_parts - 1:
                current_kwargs = kwargs
            else:
                current_kwargs['disable_web_page_preview'] = True

            await bot.send_message(chat_id, html_chunk, parse_mode='HTML', **current_kwargs)

            if total_parts > 1:
                await asyncio.sleep(0.5)

    except Exception as e:
        logger.exception(f"Критическая ошибка при отправке длинного сообщения user_id {chat_id}. Текст: '{text[:100]}...'", extra={'user_id': str(chat_id)})
        # В случае сбоя пробуем отправить текст как есть, без форматирования
        try:
            plain_text = th.remove_markdown(text)
            max_len = 4096
            parts = [plain_text[i:i+max_len] for i in range(0, len(plain_text), max_len)]
            for part in parts:
                await bot.send_message(chat_id, part, **kwargs)
        except Exception as fallback_e:
            logger.error(f"Не удалось отправить сообщение даже в виде простого текста user_id {chat_id}: {fallback_e}", extra={'user_id': str(chat_id)})


async def send_error_reply(bot: AsyncTeleBot, message: types.Message, error_log_message: str,
                           user_reply_text: str = "Произошла внутренняя ошибка. Попробуйте позже."):
    """
    Логирует ошибку, отправляет пользователю стандартизированный ответ и кнопку для репорта.
    """
    user_id = message.chat.id
    logger.exception(error_log_message, extra={'user_id': str(user_id)})

    try:
        error_report_markup = mk.create_error_report_button()
        await bot.send_message(user_id, user_reply_text, parse_mode=None, reply_markup=error_report_markup)
    except apihelper.ApiException as e:
        logger.error(f"Не удалось отправить сообщение об ошибке пользователю {user_id}: {e}", extra={'user_id': str(user_id)})

    if ADMIN_USER_ID and ADMIN_USER_ID != user_id:
        try:
            admin_notification = (f"⚠️ *Критическая ошибка у пользователя {user_id}* ⚠️\n\n"
                                  f"```\n{error_log_message}\n```\n\n"
                                  f"Сообщение пользователя: `{message.text or 'Не текстовое сообщение'}`")
            # Используем рекурсию для отправки длинного сообщения об ошибке
            await send_long_message(bot, ADMIN_USER_ID, admin_notification)
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
    Редактирует текст сообщения с обработкой распространенных ошибок.
    По умолчанию пытается использовать HTML, при ошибке - без форматирования.
    """
    try:
        html_text = telegram_format(text)
        kwargs['parse_mode'] = 'HTML'
        await bot.edit_message_text(html_text, chat_id, message_id, **kwargs)
    except apihelper.ApiException as e:
        if "message is not modified" in str(e).lower():
            logger.debug(f"Сообщение {message_id} не было изменено (текст совпадает).", extra={'user_id': str(chat_id)})
        else:
            logger.warning(f"Ошибка парсинга при редактировании сообщения {message_id}. Попытка без форматирования. Ошибка: {e}", extra={'user_id': str(chat_id)})
            try:
                kwargs['parse_mode'] = None
                plain_text = th.remove_markdown(text)
                await bot.edit_message_text(plain_text, chat_id, message_id, **kwargs)
            except apihelper.ApiException as fallback_e:
                logger.error(f"Не удалось отредактировать сообщение {message_id} даже без форматирования: {fallback_e}", extra={'user_id': str(chat_id)})


async def edit_message_reply_markup_safe(bot: AsyncTeleBot, chat_id: int, message_id: int, reply_markup=None):
    """Безопасно редактирует клавиатуру сообщения, удаляя ее."""
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)
    except apihelper.ApiException as e:
        logger.debug(f"Не удалось отредактировать клавиатуру у сообщения {message_id}: {e}", extra={'user_id': str(chat_id)})


# --- ОБЩАЯ ФУНКЦИЯ ДЛЯ АДМИНКИ ---

async def get_user_info_text(user_id_to_check: int, lang_code: str) -> str:
    """
    Формирует текст с информацией о пользователе для админ-панели.

    Args:
        user_id_to_check: ID пользователя для поиска.
        lang_code: Языковой код администратора для локализации текста.

    Returns:
        Отформатированная строка с информацией о пользователе или сообщение об ошибке.
    """
    user_info = await db_manager.get_user_info_for_admin(user_id_to_check)
    if not user_info:
        return loc.get_text('admin.user_not_found', lang_code).format(user_id=user_id_to_check)

    status = loc.get_text('admin.user_status_blocked', lang_code) if user_info['is_blocked'] else loc.get_text('admin.user_status_active', lang_code)

    info_text = (f"{loc.get_text('admin.user_info_title', lang_code)}\n\n"
                 f"*{loc.get_text('admin.user_info_id', lang_code)}* `{user_info['user_id']}`\n"
                 f"*{loc.get_text('admin.user_info_lang', lang_code)}* `{user_info['language_code']}`\n"
                 f"*{loc.get_text('admin.user_info_reg_date', lang_code)}* `{user_info['first_interaction_date']}`\n"
                 f"*{loc.get_text('admin.user_info_messages', lang_code)}* `{user_info['message_count']}`\n"
                 f"*{loc.get_text('admin.user_info_status', lang_code)}* {status}")
    return info_text

async def notify_admin_of_new_user(user_id: int, username: Optional[str], first_name: Optional[str], last_name: Optional[str]):
    """Отправляет уведомление администратору о регистрации нового пользователя."""
    if not ADMIN_USER_ID or not _bot_instance:
        return

    try:
        user_info_parts = [
            f"👤 *Новый пользователь зарегистрирован\\!*",
            f"*ID:* `{user_id}`"
        ]
        if username:
            user_info_parts.append(f"*Username:* @{th.escape_markdown(username)}")
        if first_name:
            safe_first_name = th.escape_markdown(first_name)
            user_info_parts.append(f"*Имя:* `{safe_first_name}`")
        if last_name:
            safe_last_name = th.escape_markdown(last_name)
            user_info_parts.append(f"*Фамилия:* `{safe_last_name}`")

        text = "\n".join(user_info_parts)

        await _bot_instance.send_message(ADMIN_USER_ID, text, parse_mode='MarkdownV2')
        logger.info(f"Администратор уведомлен о новом пользователе {user_id}", extra={'user_id': 'System'})

    except Exception as e:
        logger.error(f"Не удалось отправить уведомление администратору о новом пользователе {user_id}: {e}", extra={'user_id': 'System'})