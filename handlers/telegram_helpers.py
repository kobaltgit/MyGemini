# File: handlers/telegram_helpers.py
"""
Модуль со вспомогательными функциями для взаимодействия с Telegram API.
"""
import asyncio
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from telebot import apihelper
from telegram_text_splitter import split_markdown_into_chunks
from chatgpt_md_converter import telegram_format

from config.settings import ADMIN_USER_ID
from logger_config import get_logger
from utils import text_helpers as th
from utils import markup_helpers as mk
from utils import localization as loc # <-- НОВЫЙ ИМПОРТ
from database import db_manager   # <-- НОВЫЙ ИМПОРТ

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
    Отправляет длинное сообщение, используя telegram_text_splitter для разделения
    Markdown на корректные фрагменты и chatgpt-md-converter для преобразования в HTML.
    """
    if not text:
        return

    # Убираем parse_mode из kwargs, так как мы будем управлять им сами (всегда HTML)
    kwargs.pop('parse_mode', None)

    try:
        # 1. Разделяем Markdown на безопасные для Telegram фрагменты
        markdown_chunks = split_markdown_into_chunks(text)
        total_parts = len(markdown_chunks)

        for i, md_chunk in enumerate(markdown_chunks):
            # 2. Конвертируем каждый фрагмент в HTML, совместимый с Telegram
            html_chunk = telegram_format(md_chunk)

            # Для последней части передаем все оригинальные kwargs (например, reply_markup)
            if i == total_parts - 1:
                await bot.send_message(chat_id, html_chunk, parse_mode='HTML', **kwargs)
            else:
                # Для промежуточных частей отключаем превью ссылок, чтобы избежать лишнего шума
                await bot.send_message(chat_id, html_chunk, parse_mode='HTML', disable_web_page_preview=True)
                await asyncio.sleep(0.5)  # Небольшая задержка между сообщениями

    except Exception as e:
        logger.exception(f"Ошибка при отправке длинного сообщения для user_id {chat_id}. Текст: '{text[:100]}...'", extra={'user_id': str(chat_id)})
        # В случае сбоя при конвертации/отправке, пробуем отправить текст как есть, без форматирования
        try:
            # Используем старый метод простого разделения для plain text
            plain_text = th.remove_markdown(text)
            # Заменяем несуществующий th.split_message на простой сплит по длине
            max_len = 4096
            parts = [plain_text[i:i+max_len] for i in range(0, len(plain_text), max_len)]
            for part in parts:
                await bot.send_message(chat_id, part, **kwargs)
        except Exception as fallback_e:
            logger.error(f"Не удалось отправить сообщение даже в виде простого текста для user_id {chat_id}: {fallback_e}", extra={'user_id': str(chat_id)})


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


# --- НОВАЯ ОБЩАЯ ФУНКЦИЯ ДЛЯ АДМИНКИ ---

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