# File: handlers/telegram_helpers.py
"""
Модуль со вспомогательными функциями для взаимодействия с Telegram API.
Содержит логику для безопасной отправки сообщений, их редактирования и
корректного разделения длинного контента с сохранением Markdown-форматирования.
"""
import asyncio
import re
from typing import Optional

from telebot.async_telebot import AsyncTeleBot
from telebot import types
from telebot import apihelper

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


def register_bot_instance(bot: AsyncTeleBot):
    """
    Регистрирует глобальный экземпляр бота для использования в хелперах.

    Это позволяет вызывать функции, отправляющие сообщения (например, уведомления
    администратору), из модулей, где экземпляр бота напрямую недоступен.

    Args:
        bot: Экземпляр AsyncTeleBot для регистрации.
    """
    global _bot_instance
    _bot_instance = bot
    logger.info("Экземпляр бота зарегистрирован в telegram_helpers.")


# --- Функции для отправки сообщений ---

async def send_typing_action(bot: AsyncTeleBot, chat_id: int):
    """
    Отправляет действие 'печатает...' в чат.

    Используется для информирования пользователя о том, что бот обрабатывает
    его запрос и готовит ответ.

    Args:
        bot: Экземпляр AsyncTeleBot.
        chat_id: ID чата, куда будет отправлено действие.
    """
    try:
        await bot.send_chat_action(chat_id, 'typing')
    except apihelper.ApiException as e:
        logger.debug(f"Не удалось отправить typing action в чат {chat_id}: {e}", extra={'user_id': str(chat_id)})


async def send_long_message(bot: AsyncTeleBot, chat_id: int, text: str, **kwargs):
    """
    Отправляет длинное сообщение, корректно разделяя его на части.

    Эта функция решает проблему разрыва длинных блоков кода. Она сначала разделяет
    текст на обычные текстовые фрагменты и блоки кода, а затем применяет
    логику разделения к каждому типу контента индивидуально.

    Args:
        bot: Экземпляр AsyncTeleBot.
        chat_id: ID чата для отправки.
        text: Текст сообщения, который может содержать Markdown.
        **kwargs: Дополнительные аргументы для `bot.send_message` (например, reply_markup),
                  которые будут применены только к последнему сообщению.
    """
    if not text:
        return

    kwargs.pop('parse_mode', None)

    # Максимальная длина чанка, оставляем запас для HTML-тегов и других символов.
    CHUNK_SIZE = 3800

    # 1. Разделяем текст на обычные куски и блоки кода.
    # Паттерн (```[\s\S]*?```) находит блоки кода и `re.split` с захватывающей
    # скобкой сохраняет эти блоки в результирующем списке.
    parts = re.split(r'(```[\s\S]*?```)', text)

    final_chunks = []

    # 2. Обрабатываем каждый кусок отдельно.
    for part in parts:
        if not part or part.isspace():
            continue

        # 2.1. Если это блок кода
        if part.startswith('```'):
            # Извлекаем язык и сам код
            match = re.match(r'```(\w*)\n?([\s\S]*?)```', part)
            if match:
                lang, code_content = match.groups()
                lang_tag = lang if lang else ""

                # Если блок кода слишком длинный, делим его содержимое
                if len(code_content) > CHUNK_SIZE:
                    # Делим сам код на части
                    sub_chunks = [code_content[i:i + CHUNK_SIZE] for i in range(0, len(code_content), CHUNK_SIZE)]
                    for sub_chunk in sub_chunks:
                        # Каждую часть заново оборачиваем в ```
                        final_chunks.append(f"```{lang_tag}\n{sub_chunk.strip()}\n```")
                else:
                    # Блок кода помещается целиком
                    final_chunks.append(part)
            else:
                # Если это `code` без переноса строки или без указания языка
                final_chunks.append(part)

        # 2.2. Если это обычный текст
        else:
            # Используем сплиттер langchain для обычного текста
            markdown_splitter = MarkdownTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=100)
            text_chunks = markdown_splitter.split_text(part)
            final_chunks.extend(text_chunks)

    # 3. Отправляем все сформированные части
    try:
        total_parts = len(final_chunks)
        if total_parts == 0:
            return

        for i, md_chunk in enumerate(final_chunks):
            html_chunk = telegram_format(md_chunk)

            if not html_chunk or html_chunk.isspace():
                continue

            current_kwargs = {}
            if i == total_parts - 1:
                current_kwargs = kwargs
            else:
                # Отключаем предпросмотр ссылок для всех частей, кроме последней
                current_kwargs['disable_web_page_preview'] = kwargs.get('disable_web_page_preview', True)

            await bot.send_message(chat_id, html_chunk, parse_mode='HTML', **current_kwargs)

            if total_parts > 1:
                await asyncio.sleep(0.5)

    except Exception as e:
        logger.exception(
            f"Критическая ошибка при отправке длинного сообщения user_id {chat_id}. Текст: '{text[:100]}...'",
            extra={'user_id': str(chat_id)}
        )
        # Отправка как простого текста в случае фатального сбоя
        try:
            plain_text = th.remove_markdown(text)
            max_len = 4096
            parts = [plain_text[i:i+max_len] for i in range(0, len(plain_text), max_len)]
            for i, part_chunk in enumerate(parts):
                current_kwargs = kwargs if i == len(parts) - 1 else {}
                await bot.send_message(chat_id, part_chunk, **current_kwargs)
        except Exception as fallback_e:
            logger.error(
                f"Не удалось отправить сообщение даже в виде простого текста user_id {chat_id}: {fallback_e}",
                extra={'user_id': str(chat_id)}
            )


async def send_error_reply(
    bot: AsyncTeleBot,
    message: types.Message,
    error_log_message: str,
    user_reply_text: str = "Произошла внутренняя ошибка. Попробуйте позже."
):
    """
    Логирует ошибку, отправляет пользователю стандартизированный ответ и уведомляет админа.

    Args:
        bot: Экземпляр AsyncTeleBot.
        message: Объект сообщения, вызвавшего ошибку.
        error_log_message: Детальное сообщение об ошибке для лога и админа.
        user_reply_text: Краткое сообщение, которое увидит пользователь.
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

async def answer_callback_query(
    bot: AsyncTeleBot,
    call: types.CallbackQuery,
    text: Optional[str] = None,
    show_alert: bool = False,
    cache_time: int = 0
):
    """
    Безопасно отвечает на callback query, игнорируя ошибки.

    Args:
        bot: Экземпляр AsyncTeleBot.
        call: Объект CallbackQuery, на который нужно ответить.
        text: Текст уведомления (всплывающего или вверху экрана).
        show_alert: Если True, уведомление будет модальным окном.
        cache_time: Время кеширования результата запроса на стороне клиента.
    """
    try:
        await bot.answer_callback_query(call.id, text=text, show_alert=show_alert, cache_time=cache_time)
    except apihelper.ApiException as e:
        logger.debug(f"Ошибка при ответе на callback query {call.id} (возможно, устарел): {e}", extra={'user_id': str(call.from_user.id)})


async def edit_message_text_safe(bot: AsyncTeleBot, chat_id: int, message_id: int, text: str, **kwargs):
    """
    Редактирует текст сообщения с обработкой распространенных ошибок.

    Сначала пытается отредактировать сообщение с HTML-форматированием.
    Если Telegram возвращает ошибку парсинга, пытается отправить
    то же сообщение, но уже как простой текст без форматирования.

    Args:
        bot: Экземпляр AsyncTeleBot.
        chat_id: ID чата, где находится сообщение.
        message_id: ID сообщения для редактирования.
        text: Новый текст сообщения (может содержать Markdown).
        **kwargs: Дополнительные аргументы для `bot.edit_message_text`.
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
                kwargs.pop('parse_mode', None)
                plain_text = th.remove_markdown(text)
                await bot.edit_message_text(plain_text, chat_id, message_id, **kwargs)
            except apihelper.ApiException as fallback_e:
                logger.error(f"Не удалось отредактировать сообщение {message_id} даже без форматирования: {fallback_e}", extra={'user_id': str(chat_id)})


async def edit_message_reply_markup_safe(bot: AsyncTeleBot, chat_id: int, message_id: int, reply_markup=None):
    """
    Безопасно редактирует (или удаляет) клавиатуру под сообщением.

    Args:
        bot: Экземпляр AsyncTeleBot.
        chat_id: ID чата, где находится сообщение.
        message_id: ID сообщения для редактирования.
        reply_markup: Новая inline-клавиатура или None для удаления.
    """
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)
    except apihelper.ApiException as e:
        logger.debug(f"Не удалось отредактировать клавиатуру у сообщения {message_id}: {e}", extra={'user_id': str(chat_id)})


# --- ОБЩАЯ ФУНКЦИЯ ДЛЯ АДМИНКИ ---

async def get_user_info_text(user_id_to_check: int, lang_code: str) -> str:
    """
    Формирует текст с информацией о пользователе для админ-панели.

    Args:
        user_id_to_check: ID пользователя для поиска в базе данных.
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
    """
    Отправляет уведомление администратору о регистрации нового пользователя.

    Args:
        user_id: ID нового пользователя.
        username: Username нового пользователя.
        first_name: Имя нового пользователя.
        last_name: Фамилия нового пользователя.
    """
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