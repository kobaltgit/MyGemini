# --- START OF FILE handlers/message_handlers.py ---
import datetime
import pytz
import time
import os
import PIL.Image # <--- Убедимся, что импорт есть
from io import BytesIO
from typing import Optional, List, Union, Dict, Any
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from telebot.util import smart_split
import asyncio
import re

# Импорты из проекта
from config.settings import (
    STATE_WAITING_FOR_TRANSLATE_TEXT, STATE_WAITING_FOR_SUMMARIZE_INPUT,
    STATE_WAITING_FOR_INCOME_SKILLS, STATE_WAITING_FOR_INCOME_TERM,
    STATE_WAITING_FOR_INCOME_RESOURCES, STATE_WAITING_FOR_INCOME_INTERESTS,
    STATE_WAITING_FOR_REMINDER_TEXT, STATE_WAITING_FOR_REMINDER_DATE, STATE_WAITING_FOR_REMINDER_TIME,
    STATE_WAITING_FOR_TIMEZONE,
    STATE_WAITING_FOR_HISTORY_DATE,
    MAX_SUMMARIZE_CHARS, BOT_STYLES, LANGUAGE_FLAGS
)
from database import db_manager
from services import gemini_service
from features import personal_account, reminders
from utils import markup_helpers as mk
from utils import text_helpers, file_helpers, web_helpers
from logger_config import get_logger
from .command_handlers import user_states, send_message, reply_to_message
from .callback_handlers import answer_callback_query, edit_message_text, edit_message_reply_markup

try:
    from timezonefinder import TimezoneFinder # type: ignore
    tf = TimezoneFinder()
    def find_timezone_at(lat: float, lng: float) -> Optional[str]:
        return tf.timezone_at(lng=lng, lat=lat)
except ImportError:
    logger = get_logger(__name__)
    logger.error("Библиотека 'timezonefinder' не установлена. Определение таймзоны по геолокации не будет работать. Установите: pip install timezonefinder[numba]")
    def find_timezone_at(lat: float, lng: float) -> Optional[str]:
        return None

logger = get_logger(__name__)
user_logger = get_logger('user_messages')

# --- Вспомогательные функции ---

async def send_typing_action(bot: AsyncTeleBot, chat_id: int):
    """Отправляет действие 'typing'."""
    try:
        await bot.send_chat_action(chat_id, 'typing')
    except Exception as e:
        logger.debug(f"Не удалось отправить typing action в чат {chat_id}: {e}", extra={'user_id': str(chat_id)})

async def send_error_reply(bot: AsyncTeleBot, message: types.Message, log_message: str, user_message: str = "Произошла ошибка. Попробуйте позже."):
    """Отправляет сообщение об ошибке пользователю и логирует исключение."""
    logger.error(log_message, exc_info=True, extra={'user_id': str(message.chat.id)})
    error_report_markup = mk.create_error_report_button()
    try:
        await reply_to_message(bot, message, user_message, reply_markup=error_report_markup, parse_mode='None')
    except Exception as send_err:
        logger.error(f"Не удалось отправить сообщение об ошибке пользователю {message.chat.id}: {send_err}", extra={'user_id': str(message.chat.id)})

def log_user_message_info(message: types.Message):
    """Логирует информацию о полученном сообщении пользователя."""
    user_id = message.chat.id
    user_info = f"User ID: {user_id}"
    if message.from_user:
        if message.from_user.first_name: user_info += f", Имя: {message.from_user.first_name}"
        if message.from_user.last_name: user_info += f", Фамилия: {message.from_user.last_name}"
        if message.from_user.username: user_info += f", Username: @{message.from_user.username}"

    content_type = message.content_type
    log_text = f"Получено сообщение ({content_type}) от {user_info}"

    if content_type == 'text':
        log_text += f". Текст: '{message.text[:100]}{'...' if len(message.text) > 100 else ''}'"
    elif content_type == 'photo':
        photo_info = f"Photo ID: {message.photo[-1].file_id}"
        if message.caption:
             photo_info += f", Caption: '{message.caption[:50]}{'...' if len(message.caption) > 50 else ''}'"
        else:
             photo_info += ", No caption"
        log_text += f". {photo_info}"
    elif content_type == 'document':
        doc = message.document
        doc_info = f"Doc: {doc.file_name}, Size: {doc.file_size} bytes, MIME: {doc.mime_type}, ID: {doc.file_id}"
        log_text += f". {doc_info}"
    elif content_type == 'location':
        loc = message.location
        loc_info = f"Location: lat={loc.latitude}, lon={loc.longitude}"
        log_text += f". {loc_info}"

    user_logger.info(log_text, extra={'user_id': str(user_id)})

# --- Основной обработчик сообщений ---

async def handle_any_message(message: types.Message, bot: AsyncTeleBot):
    """Обрабатывает любое входящее сообщение (текст, фото, документ и т.д.)."""
    user_id = message.chat.id
    content_type = message.content_type

    log_user_message_info(message)
    db_manager.add_or_update_user(user_id)
    current_state = user_states.get(user_id)
    logger.debug(f"Обработка сообщения от user_id {user_id}. Состояние: {current_state}. Тип контента: {content_type}", extra={'user_id': str(user_id)})

    try:
        if content_type == 'text':
            await handle_text_message(bot, message, current_state)
        elif content_type == 'photo':
            if current_state in [STATE_WAITING_FOR_TRANSLATE_TEXT, STATE_WAITING_FOR_INCOME_SKILLS,
                                STATE_WAITING_FOR_INCOME_TERM, STATE_WAITING_FOR_INCOME_RESOURCES,
                                STATE_WAITING_FOR_INCOME_INTERESTS, STATE_WAITING_FOR_REMINDER_TEXT,
                                STATE_WAITING_FOR_REMINDER_TIME, STATE_WAITING_FOR_TIMEZONE,
                                STATE_WAITING_FOR_HISTORY_DATE]:
                  await reply_to_message(bot, message, "Сейчас я ожидаю другой ввод (текст, дату или геолокацию). Пожалуйста, завершите текущее действие или нажмите /reset.", reply_markup=mk.create_main_keyboard())
            else:
                  await handle_photo_message(bot, message)
        elif content_type == 'document':
            if current_state == STATE_WAITING_FOR_SUMMARIZE_INPUT:
                await handle_document_message(bot, message)
            else:
                await reply_to_message(bot, message, "Чтобы отправить документ для изложения, сначала нажмите кнопку '📝 Изложить' или команду /summarize.", reply_markup=mk.create_main_keyboard())
        elif content_type == 'location':
             if current_state == STATE_WAITING_FOR_TIMEZONE:
                 await handle_state_timezone_location(bot, message)
             else:
                  logger.debug(f"Получена локация от {user_id} вне состояния ожидания таймзоны.", extra={'user_id': str(user_id)})
        else:
             logger.warning(f"Получен неподдерживаемый тип контента '{content_type}' от user_id {user_id}. Игнорируется.", extra={'user_id': str(user_id)})

    except Exception as e:
        await send_error_reply(bot, message, f"Критическая ошибка в handle_any_message для user_id {user_id} (state: {current_state}, type: {content_type})")
        if user_id in user_states:
            # Удаляем основное состояние и все связанные временные данные
            keys_to_remove = [key for key in list(user_states.keys()) if key.startswith(f"{user_id}")]
            for key in keys_to_remove:
                 user_states.pop(key, None)
            logger.info(f"Состояние и временные данные user_id {user_id} сброшены из-за ошибки в handle_any_message.", extra={'user_id': str(user_id)})

# --- Обработчик текстовых сообщений ---

async def handle_text_message(bot: AsyncTeleBot, message: types.Message, current_state: Optional[str]):
    """Обрабатывает входящие текстовые сообщения."""
    user_id = message.chat.id
    text = message.text.strip()

    if not text:
        logger.debug(f"Получено пустое текстовое сообщение от {user_id}. Игнорируется.", extra={'user_id': str(user_id)})
        return

    # --- Обработка состояний ---
    state_handlers = {
        STATE_WAITING_FOR_TRANSLATE_TEXT: handle_state_translate,
        STATE_WAITING_FOR_SUMMARIZE_INPUT: handle_state_summarize,
        STATE_WAITING_FOR_INCOME_SKILLS: handle_state_income_skills,
        STATE_WAITING_FOR_INCOME_TERM: handle_state_income_term,
        STATE_WAITING_FOR_INCOME_RESOURCES: handle_state_income_resources,
        STATE_WAITING_FOR_INCOME_INTERESTS: handle_state_income_interests,
        STATE_WAITING_FOR_REMINDER_TEXT: handle_state_reminder_text,
        STATE_WAITING_FOR_REMINDER_TIME: handle_state_reminder_time,
        STATE_WAITING_FOR_TIMEZONE: handle_state_timezone_text,
        STATE_WAITING_FOR_HISTORY_DATE: lambda b, m: reply_to_message(b, m, "Пожалуйста, выберите дату на календаре выше или нажмите /reset для отмены.")
    }

    if current_state in state_handlers:
        logger.debug(f"Сообщение от {user_id} обрабатывается хендлером состояния: {current_state}", extra={'user_id': str(user_id)})
        await state_handlers[current_state](bot, message)
        return

    # --- Обработка кнопок ReplyKeyboard ---
    button_handlers = {
        '👤 Личный кабинет': handle_personal_account_button,
        '⏰ Напоминания': handle_reminders_button,
    }

    if text in button_handlers:
        logger.debug(f"Сообщение от {user_id} соответствует кнопке: {text}", extra={'user_id': str(user_id)})
        await button_handlers[text](bot, message)
        return

    # --- Обработка запросов помощи по ключевым словам ---
    text_lower = text.lower()
    if is_help_request(text_lower):
         logger.debug(f"Сообщение от {user_id} распознано как запрос помощи.", extra={'user_id': str(user_id)})
         await handle_help_request_message(bot, message)
         return
    if is_model_request(text_lower):
         logger.debug(f"Сообщение от {user_id} распознано как запрос о модели.", extra={'user_id': str(user_id)})
         await handle_model_request_message(bot, message)
         return

    # --- Если не состояние и не кнопка - отправляем в Gemini ---
    logger.debug(f"Сообщение от {user_id} не соответствует кнопкам или состояниям. Отправка в Gemini.", extra={'user_id': str(user_id)})
    await handle_general_text_query(bot, message)

# --- Обработчики состояний ---
# ... (handle_state_translate, handle_state_summarize - без изменений) ...
async def handle_state_translate(bot: AsyncTeleBot, message: types.Message):
    """Состояние: ожидание текста для перевода."""
    user_id = message.chat.id
    text_to_translate = message.text.strip()
    target_lang_code = user_states.get(f"{user_id}_target_lang")

    if not target_lang_code:
        logger.warning(f"Нет целевого языка для перевода у user_id {user_id} в состоянии {STATE_WAITING_FOR_TRANSLATE_TEXT}", extra={'user_id': str(user_id)})
        await reply_to_message(bot, message, "Не выбран язык для перевода. Начните сначала, нажав '🇷🇺 Перевести' или /translate.", reply_markup=mk.create_main_keyboard())
        user_states.pop(user_id, None)
        return

    if not text_to_translate:
        await reply_to_message(bot, message, "Пожалуйста, введите текст для перевода.")
        return

    lang_name = LANGUAGE_FLAGS.get(target_lang_code, target_lang_code)
    logger.info(f"Перевод текста для user_id {user_id} на язык {lang_name} ({target_lang_code})", extra={'user_id': str(user_id)})
    await send_typing_action(bot, user_id)

    prompt = f"Переведи следующий текст на язык '{lang_name}' (код: {target_lang_code}). Выведи только сам перевод, без дополнительных фраз:\n\n{text_to_translate}"
    response = await asyncio.to_thread(gemini_service.generate_response, user_id, prompt, store_in_db=True)

    user_states.pop(user_id, None)
    user_states.pop(f"{user_id}_target_lang", None)

    if response:
        await reply_to_message(bot, message, response, reply_markup=mk.create_main_keyboard())
    else:
        await send_error_reply(bot, message, f"Ошибка перевода (Gemini не вернул ответ) для user_id {user_id}", "Не удалось выполнить перевод. Возможно, запрос был заблокирован.")

async def handle_state_summarize(bot: AsyncTeleBot, message: types.Message):
    """Состояние: ожидание текста/ссылки для изложения."""
    user_id = message.chat.id
    text_or_url = message.text.strip()
    combined_text = ""
    source_type = "текст"

    if not text_or_url:
         await reply_to_message(bot, message, "Пожалуйста, отправьте текст или ссылку для изложения.")
         return

    if text_helpers.is_url(text_or_url):
        source_type = "URL"
        logger.info(f"Получен URL для изложения от {user_id}: {text_or_url}", extra={'user_id': str(user_id)})
        await reply_to_message(bot, message, f"🔗 Загружаю текст со страницы '{text_or_url}'...", parse_mode='None')
        await send_typing_action(bot, user_id)
        webpage_text = await asyncio.to_thread(web_helpers.get_text_from_url, text_or_url)

        if webpage_text:
            combined_text = webpage_text[:MAX_SUMMARIZE_CHARS]
            if len(webpage_text) > MAX_SUMMARIZE_CHARS:
                 await send_message(bot, user_id, f"⚠️ Текст со страницы слишком длинный. Будет обработано только первые ~{MAX_SUMMARIZE_CHARS // 1000} тыс. символов.")
        else:
            await reply_to_message(bot, message, "Не удалось загрузить или обработать текст со страницы. Попробуйте другую ссылку или отправьте текст.", reply_markup=mk.create_main_keyboard())
            return
    else:
        source_type = "текст"
        logger.info(f"Получен текст для изложения от {user_id}", extra={'user_id': str(user_id)})
        combined_text = text_or_url[:MAX_SUMMARIZE_CHARS]
        if len(text_or_url) > MAX_SUMMARIZE_CHARS:
             await send_message(bot, user_id, f"⚠️ Текст слишком длинный. Будет обработано только первые ~{MAX_SUMMARIZE_CHARS // 1000} тыс. символов.")

    user_states.pop(user_id, None)

    if not combined_text:
        await reply_to_message(bot, message, f"Не удалось получить {source_type} для изложения.", reply_markup=mk.create_main_keyboard())
        return

    await reply_to_message(bot, message, "⏳ Готовлю краткое изложение...", parse_mode='None')
    await send_typing_action(bot, user_id)

    prompt = f"""Сделай краткое и структурированное изложение следующего текста (источник: {source_type}). Выдели основные мысли, ключевые моменты и, если применимо, главные выводы.
Текст для изложения:
---
{combined_text}
---
Предоставь только само изложение. Ответ должен быть на русском языке.
"""
    response = await asyncio.to_thread(gemini_service.generate_response, user_id, prompt, store_in_db=True)

    if response:
        parts = smart_split(response, chars_per_string=4000)
        for part in parts:
             await send_message(bot, user_id, part, reply_markup=mk.create_main_keyboard())
             await asyncio.sleep(0.1)
    else:
        await send_error_reply(bot, message, f"Ошибка изложения ({source_type}) для user_id {user_id}", "Не удалось подготовить изложение. Возможно, запрос был заблокирован.")

# ... (handle_state_income_... - без изменений) ...
async def handle_state_income_skills(bot: AsyncTeleBot, message: types.Message):
    """Состояние: ожидание ввода навыков для плана дохода."""
    user_id = message.chat.id
    skills = message.text.strip()
    if not skills:
        await reply_to_message(bot, message, "Кажется, вы не указали навыки. Пожалуйста, опишите их:")
        return
    user_states[f"{user_id}_income_skills"] = skills
    user_states[user_id] = STATE_WAITING_FOR_INCOME_TERM
    logger.debug(f"План дохода: Получены навыки от {user_id}. Переход к {STATE_WAITING_FOR_INCOME_TERM}", extra={'user_id': str(user_id)})
    await reply_to_message(bot, message, "⏳ Отлично! Теперь укажите желаемый срок для достижения цели (например, '6 месяцев', '1 год'):")

async def handle_state_income_term(bot: AsyncTeleBot, message: types.Message):
    """Состояние: ожидание ввода срока для плана дохода."""
    user_id = message.chat.id
    term = message.text.strip()
    if not term:
        await reply_to_message(bot, message, "Пожалуйста, укажите желаемый срок:")
        return
    user_states[f"{user_id}_income_term"] = term
    user_states[user_id] = STATE_WAITING_FOR_INCOME_RESOURCES
    logger.debug(f"План дохода: Получен срок от {user_id}. Переход к {STATE_WAITING_FOR_INCOME_RESOURCES}", extra={'user_id': str(user_id)})
    await reply_to_message(bot, message, "📝 Понял. Перечислите ресурсы, которые у вас есть (стартовый капитал, оборудование, связи, время и т.д.):")

async def handle_state_income_resources(bot: AsyncTeleBot, message: types.Message):
    """Состояние: ожидание ввода ресурсов для плана дохода."""
    user_id = message.chat.id
    resources = message.text.strip()
    if not resources:
        await reply_to_message(bot, message, "Укажите, пожалуйста, имеющиеся ресурсы (можно написать 'нет', если их нет):")
        return
    user_states[f"{user_id}_income_resources"] = resources
    user_states[user_id] = STATE_WAITING_FOR_INCOME_INTERESTS
    logger.debug(f"План дохода: Получены ресурсы от {user_id}. Переход к {STATE_WAITING_FOR_INCOME_INTERESTS}", extra={'user_id': str(user_id)})
    await reply_to_message(bot, message, "💡 Хорошо. И последнее: какие у вас личные интересы или хобби, которые могут быть полезны или которые вы хотели бы монетизировать?")

async def handle_state_income_interests(bot: AsyncTeleBot, message: types.Message):
    """Состояние: ожидание ввода интересов (последний шаг) и генерация плана дохода."""
    user_id = message.chat.id
    interests = message.text.strip() or "не указаны"
    user_states[f"{user_id}_income_interests"] = interests
    logger.debug(f"План дохода: Получены интересы от {user_id}. Запуск генерации.", extra={'user_id': str(user_id)})

    skills = user_states.get(f"{user_id}_income_skills", "не указаны")
    term = user_states.get(f"{user_id}_income_term", "не указан")
    resources = user_states.get(f"{user_id}_income_resources", "не указаны")

    user_states.pop(user_id, None)
    for key_suffix in ['skills', 'term', 'resources', 'interests']:
        user_states.pop(f"{user_id}_income_{key_suffix}", None)
    logger.debug(f"План дохода: Состояние и временные данные для {user_id} сброшены.", extra={'user_id': str(user_id)})

    await reply_to_message(bot, message, "⏳ Спасибо! Вся информация собрана. Составляю ваш индивидуальный план дохода...", parse_mode='None')
    await send_typing_action(bot, user_id)

    prompt = f"""
Разработай, пожалуйста, подробный и реалистичный пошаговый план достижения дохода (например, 100 тысяч рублей в месяц или эквивалент) для пользователя, основываясь на следующих данных:

- Ключевые навыки и компетенции: {skills}
- Желаемый срок достижения цели: {term}
- Доступные ресурсы (финансы, оборудование, связи, время и т.д.): {resources}
- Личные интересы и хобби: {interests}

План должен быть структурирован и включать:
1.  **Анализ:** Оценка 2-3 наиболее перспективных и релевантных направлений для монетизации указанных навыков и интересов с учетом ресурсов и срока. Краткое обоснование выбора.
2.  **Стратегия:** Для каждого выбранного направления - общая стратегия действий. Как выделиться, где искать клиентов/возможности.
3.  **Пошаговый план:** Конкретные, измеримые шаги для реализации стратегии. Что делать на каждом этапе (например, неделя 1-2, месяц 1, квартал 1). Укажи примерные сроки для каждого этапа.
4.  **Ресурсы и Интересы:** Как эффективно использовать имеющиеся ресурсы? Как можно задействовать хобби и интересы?
5.  **Риски и Решения:** Краткое описание 2-3 возможных трудностей и как их можно преодолеть или минимизировать.
6.  **Мотивация:** Небольшой мотивирующий абзац в конце.

Представь план в четком, структурированном виде (используй заголовки, списки). Ответ должен быть на русском языке.
"""
    response = await asyncio.to_thread(gemini_service.generate_response, user_id, prompt, store_in_db=True)

    if response:
        parts = smart_split(response, chars_per_string=4000)
        for part in parts:
            await send_message(bot, user_id, part, reply_markup=mk.create_main_keyboard())
            await asyncio.sleep(0.1)
    else:
        await send_error_reply(bot, message, f"Ошибка генерации плана дохода для user_id {user_id}", "Не удалось составить план дохода. Возможно, запрос был заблокирован.")

# ... (handle_state_reminder_... - без изменений) ...
async def handle_state_reminder_text(bot: AsyncTeleBot, message: types.Message):
     """Состояние: Ожидание текста напоминания. Переход к выбору ДАТЫ."""
     user_id = message.chat.id
     reminder_text = message.text.strip()
     if not reminder_text:
         await reply_to_message(bot, message, "Текст напоминания не может быть пустым. Введите текст:")
         return

     user_states[f"{user_id}_reminder_text"] = reminder_text
     user_states[user_id] = STATE_WAITING_FOR_REMINDER_DATE
     logger.debug(f"Напоминание: Получен текст от {user_id}. Переход к {STATE_WAITING_FOR_REMINDER_DATE}", extra={'user_id': str(user_id)})

     calendar_markup = mk.create_calendar_keyboard(disable_past=True)
     await send_message(bot, user_id, "🗓️ Отлично! Теперь выберите **дату** для напоминания на календаре ниже:", reply_markup=calendar_markup)

async def handle_state_reminder_time(bot: AsyncTeleBot, message: types.Message):
    """Состояние: Ожидание времени напоминания (ЧЧ:ММ)."""
    user_id = message.chat.id
    time_str = message.text.strip()

    reminder_text = user_states.get(f"{user_id}_reminder_text")
    reminder_date_str = user_states.get(f"{user_id}_reminder_date")

    if not reminder_text or not reminder_date_str:
        error_msg = "Произошла ошибка: "
        missing_data = []
        if not reminder_text: missing_data.append("текст напоминания")
        if not reminder_date_str: missing_data.append("дата напоминания")
        error_msg += f"не найдены {', '.join(missing_data)}. Пожалуйста, начните сначала, нажав '⏰ Напоминания'."
        logger.warning(f"Не все данные для создания напоминания у {user_id} в состоянии {STATE_WAITING_FOR_REMINDER_TIME}. Отсутствует: {', '.join(missing_data)}", extra={'user_id': str(user_id)})
        await reply_to_message(bot, message, error_msg, reply_markup=mk.create_main_keyboard())
        user_states.pop(user_id, None)
        user_states.pop(f"{user_id}_reminder_text", None)
        user_states.pop(f"{user_id}_reminder_date", None)
        return

    try:
        reminder_time_obj = datetime.datetime.strptime(time_str, "%H:%M").time()
        reminder_date_obj = datetime.datetime.strptime(reminder_date_str, "%Y-%m-%d").date()
        reminder_dt_naive = datetime.datetime.combine(reminder_date_obj, reminder_time_obj)

        user_timezone_str = db_manager.get_user_timezone(user_id)
        reminder_dt_utc: datetime.datetime

        if user_timezone_str:
            try:
                user_tz = pytz.timezone(user_timezone_str)
                reminder_dt_local = user_tz.localize(reminder_dt_naive, is_dst=None)
                reminder_dt_utc = reminder_dt_local.astimezone(pytz.utc)
                logger.debug(f"Время напоминания для {user_id} ({time_str} в {user_timezone_str}) конвертировано в UTC: {reminder_dt_utc}", extra={'user_id': str(user_id)})
            except pytz.UnknownTimeZoneError:
                 logger.error(f"Неизвестный часовой пояс '{user_timezone_str}' у пользователя {user_id}. Используем UTC.", extra={'user_id': str(user_id)})
                 reminder_dt_utc = pytz.utc.localize(reminder_dt_naive)
            except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError) as tz_err:
                 logger.warning(f"Проблема с временем {time_str} для {user_id} в {user_timezone_str}: {tz_err}. Используем UTC.", extra={'user_id': str(user_id)})
                 reminder_dt_utc = pytz.utc.localize(reminder_dt_naive)
        else:
             logger.warning(f"Часовой пояс не установлен для user_id {user_id}. Время {time_str} будет интерпретировано как UTC.", extra={'user_id': str(user_id)})
             reminder_dt_utc = pytz.utc.localize(reminder_dt_naive)
             await send_message(bot, user_id, "💡 Совет: Вы можете установить свой часовой пояс в /settings для более точной установки напоминаний.", parse_mode='None')

        now_utc = datetime.datetime.now(pytz.utc)
        if reminder_dt_utc <= (now_utc - datetime.timedelta(minutes=1)):
             await reply_to_message(bot, message, "Нельзя установить напоминание на прошедшее время. Пожалуйста, введите время в будущем (формат ЧЧ:ММ).")
             return

        logger.info(f"Планирование напоминания для {user_id}. Текст: '{reminder_text[:50]}...'. Время UTC: {reminder_dt_utc}", extra={'user_id': str(user_id)})
        success = await reminders.schedule_reminder(bot, user_id, reminder_text, reminder_dt_utc)

        user_states.pop(user_id, None)
        user_states.pop(f"{user_id}_reminder_text", None)
        user_states.pop(f"{user_id}_reminder_date", None)

        if success:
            time_confirm_utc_str = reminder_dt_utc.strftime("%d.%m.%Y %H:%M %Z")
            confirm_msg = f"✅ Напоминание установлено на **{time_confirm_utc_str}**!"
            if user_timezone_str:
                 try:
                      user_tz = pytz.timezone(user_timezone_str)
                      local_dt = reminder_dt_utc.astimezone(user_tz)
                      time_confirm_local_str = local_dt.strftime("%d.%m.%Y %H:%M")
                      confirm_msg += f"\n(Ваше время: {time_confirm_local_str} {user_timezone_str})"
                 except Exception: pass
            await reply_to_message(bot, message, confirm_msg, reply_markup=mk.create_main_keyboard())
        else:
            await reply_to_message(bot, message, "❌ Не удалось установить напоминание. Попробуйте позже.", reply_markup=mk.create_main_keyboard())

    except ValueError as e:
        if "time data" in str(e) and ("match format '%H:%M'" in str(e)):
            await reply_to_message(bot, message, "❌ Неверный формат времени. Введите время в формате **ЧЧ:ММ** (например, 14:05).")
        elif "time data" in str(e) and ("match format '%Y-%m-%d'" in str(e)):
             logger.error(f"Ошибка парсинга сохраненной даты '{reminder_date_str}' для user_id {user_id}: {e}", extra={'user_id': str(user_id)})
             await reply_to_message(bot, message, "❌ Произошла внутренняя ошибка (дата). Попробуйте начать сначала.", reply_markup=mk.create_main_keyboard())
             user_states.pop(user_id, None)
             user_states.pop(f"{user_id}_reminder_text", None)
             user_states.pop(f"{user_id}_reminder_date", None)
        else:
             logger.exception(f"Неожиданная ошибка ValueError при установке напоминания для {user_id}: {e}", extra={'user_id': str(user_id)})
             await send_error_reply(bot, message, f"Ошибка значения при установке напоминания для {user_id}", "Произошла ошибка при установке напоминания.")
             user_states.pop(user_id, None)
             user_states.pop(f"{user_id}_reminder_text", None)
             user_states.pop(f"{user_id}_reminder_date", None)

    except Exception as e:
         await send_error_reply(bot, message, f"Критическая ошибка установки напоминания для {user_id}", "Произошла ошибка при установке напоминания.")
         user_states.pop(user_id, None)
         user_states.pop(f"{user_id}_reminder_text", None)
         user_states.pop(f"{user_id}_reminder_date", None)

# ... (handle_state_timezone_... - без изменений) ...
async def handle_state_timezone_text(bot: AsyncTeleBot, message: types.Message):
    """Состояние: ожидание текстового ввода часового пояса."""
    user_id = message.chat.id
    tz_name = message.text.strip()

    if tz_name.lower() in ["отмена", "cancel", "/cancel", "стоп", "stop", "/stop"]:
        user_states.pop(user_id, None)
        await reply_to_message(bot, message, "Установка часового пояса отменена.", reply_markup=mk.create_main_keyboard())
        logger.debug(f"Установка часового пояса отменена пользователем {user_id}.", extra={'user_id': str(user_id)})
        return

    if tz_name in pytz.all_timezones_set:
        db_manager.set_user_timezone(user_id, tz_name)
        logger.info(f"Часовой пояс для {user_id} установлен на '{tz_name}' через текстовый ввод.", extra={'user_id': str(user_id)})
        await reply_to_message(bot, message, f"✅ Часовой пояс успешно установлен на **{tz_name}**.", reply_markup=mk.create_main_keyboard())
        user_states.pop(user_id, None)
    else:
        possible_tzs = [tz for tz in pytz.all_timezones if tz_name.lower() in tz.lower()]
        if possible_tzs:
             response_text = f"🤔 Не удалось найти часовой пояс '{tz_name}'. Возможно, вы имели в виду один из этих:\n"
             response_text += "\n".join([f"- `{tz}`" for tz in possible_tzs[:10]])
             if len(possible_tzs) > 10: response_text += "\n..."
             response_text += "\n\nПожалуйста, попробуйте ввести один из них, отправьте свою геолокацию или напишите 'Отмена'."
             await reply_to_message(bot, message, response_text)
        else:
             await reply_to_message(bot, message, f"❌ Часовой пояс '{tz_name}' не найден. Попробуйте ввести снова (например, `Europe/Moscow`, `Asia/Yekaterinburg`), отправьте свою геолокацию или напишите 'Отмена'.")

async def handle_state_timezone_location(bot: AsyncTeleBot, message: types.Message):
    """Состояние: обработка полученной геолокации для установки таймзоны."""
    user_id = message.chat.id
    if not message.location:
         logger.warning(f"Сообщение в состоянии {STATE_WAITING_FOR_TIMEZONE} не содержит локации от user_id {user_id}.", extra={'user_id': str(user_id)})
         return

    latitude = message.location.latitude
    longitude = message.location.longitude
    logger.info(f"Получена геолокация от {user_id} для установки таймзоны: lat={latitude}, lon={longitude}", extra={'user_id': str(user_id)})

    timezone_name = await asyncio.to_thread(find_timezone_at, lat=latitude, lng=longitude)

    if timezone_name and timezone_name in pytz.all_timezones_set:
        db_manager.set_user_timezone(user_id, timezone_name)
        logger.info(f"Часовой пояс для {user_id} установлен на '{timezone_name}' по геолокации.", extra={'user_id': str(user_id)})
        await reply_to_message(bot, message, f"✅ Ваш часовой пояс определен как **{timezone_name}** и успешно установлен.", reply_markup=mk.create_main_keyboard())
        user_states.pop(user_id, None)
    elif find_timezone_at is None: # Если функция-заглушка
        await reply_to_message(bot, message, "❌ Не удалось определить часовой пояс: необходимая библиотека (`timezonefinder`) не установлена на сервере.", reply_markup=mk.create_main_keyboard())
        user_states.pop(user_id, None)
    else:
        logger.warning(f"Не удалось определить часовой пояс по координатам ({latitude}, {longitude}) для user_id {user_id}. Результат: {timezone_name}", extra={'user_id': str(user_id)})
        await reply_to_message(bot, message, "❌ Не удалось определить ваш часовой пояс по геолокации. Попробуйте ввести его текстом (например, `Europe/Moscow`) или напишите 'Отмена'.")

# --- Обработчики контента (Фото, Документы) ---

async def handle_photo_message(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает входящие фото."""
    user_id = message.chat.id
    photo_id = message.photo[-1].file_id
    caption = message.caption or ""

    await reply_to_message(bot, message, "🖼️ Анализирую изображение...", parse_mode='None')
    await send_typing_action(bot, user_id)

    try:
        # --- Получение файла ---
        file_info = await bot.get_file(photo_id)
        if not file_info or not file_info.file_path:
            await send_error_reply(bot, message, f"Не удалось получить информацию о файле фото {photo_id} для {user_id}", "Не удалось обработать фото (ошибка информации о файле).")
            return

        # --- Скачивание файла ---
        # --- ИЗМЕНЕНИЕ: Скачиваем байты ---
        logger.debug(f"Скачивание фото {file_info.file_path} для user_id {user_id}")
        downloaded_bytes = await bot.download_file(file_info.file_path)
        if not downloaded_bytes:
             await send_error_reply(bot, message, f"Не удалось скачать фото {photo_id} (bytes) для {user_id}", "Не удалось обработать фото (ошибка скачивания).")
             return
        logger.debug(f"Фото {file_info.file_path} скачано ({len(downloaded_bytes)} bytes) для user_id {user_id}")

        # --- Обработка изображения ---
        try:
            # --- ИЗМЕНЕНИЕ: Открываем из байтов ---
            image = PIL.Image.open(BytesIO(downloaded_bytes))
        except PIL.UnidentifiedImageError:
             await send_error_reply(bot, message, f"Не удалось распознать формат изображения {photo_id} для {user_id}", "Не удалось обработать фото (неверный формат).")
             return
        except Exception as img_err:
             await send_error_reply(bot, message, f"Ошибка обработки изображения {photo_id} для {user_id}: {img_err}", "Не удалось обработать фото (ошибка PIL).")
             return
        # BytesIO закроется автоматически

        # --- Формирование промпта для Gemini ---
        prompt_parts: List[Union[str, PIL.Image.Image]] = [image]
        text_prompt = caption.strip() or "Подробно опиши, что изображено на этой картинке."
        text_prompt += " Если на картинке есть объект, который можно идентифицировать (растение, животное, блюдо, лекарство, достопримечательность и т.п.), предоставь краткую энциклопедическую справку о нем."
        prompt_parts.append(text_prompt)
        logger.debug(f"Промпт для анализа фото user_id {user_id}: '{text_prompt[:100]}...'", extra={'user_id': str(user_id)})

        # --- Отправка в Gemini ---
        response = await asyncio.to_thread(gemini_service.generate_response, user_id, prompt_parts, store_in_db=True)

        if response:
            parts = smart_split(response, chars_per_string=4000)
            for part in parts:
                await send_message(bot, user_id, part, reply_markup=mk.create_main_keyboard())
                await asyncio.sleep(0.1)
        else:
            await send_error_reply(bot, message, f"Ошибка анализа фото {photo_id} (Gemini не вернул ответ) для {user_id}", "Не удалось проанализировать изображение. Возможно, запрос был заблокирован.")

    except Exception as e:
        # Ловим ошибки get_file и другие непредвиденные
        await send_error_reply(bot, message, f"Критическая ошибка обработки фото {photo_id} для {user_id}: {e}")


async def handle_document_message(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает входящие документы (только в состоянии ожидания изложения)."""
    user_id = message.chat.id
    doc = message.document
    file_id = doc.file_id
    file_name = doc.file_name or "document"
    mime_type = doc.mime_type or "unknown"
    file_size = doc.file_size or 0

    logger.info(f"Получен документ '{file_name}' ({mime_type}, {file_size} bytes) от {user_id} для изложения.", extra={'user_id': str(user_id)})

    MAX_DOC_SIZE = 20 * 1024 * 1024
    if file_size > MAX_DOC_SIZE:
        logger.warning(f"Документ '{file_name}' от {user_id} слишком большой ({file_size} bytes).", extra={'user_id': str(user_id)})
        await reply_to_message(bot, message, f"❌ Файл слишком большой (больше {MAX_DOC_SIZE // 1024 // 1024} МБ). Пожалуйста, отправьте файл меньшего размера.", reply_markup=mk.create_main_keyboard())
        return

    await reply_to_message(bot, message, f"📄 Обрабатываю документ '{file_name}'...", parse_mode='None')
    await send_typing_action(bot, user_id)

    downloaded_file_path: Optional[str] = None
    extracted_text: Optional[str] = None

    try:
        downloaded_file_path = await file_helpers.save_downloaded_file(bot, file_id, file_name)
        if not downloaded_file_path:
            await reply_to_message(bot, message, "❌ Не удалось скачать документ. Попробуйте еще раз.", reply_markup=mk.create_main_keyboard())
            return

        file_ext = os.path.splitext(file_name)[1].lower()
        text_extractor = None
        if 'wordprocessingml.document' in mime_type or file_ext == '.docx':
            text_extractor = file_helpers.get_text_from_docx
            logger.debug(f"Документ '{file_name}' определен как DOCX.", extra={'user_id': str(user_id)})
        elif 'pdf' in mime_type or file_ext == '.pdf':
            text_extractor = file_helpers.get_text_from_pdf
            logger.debug(f"Документ '{file_name}' определен как PDF.", extra={'user_id': str(user_id)})
        elif 'text/plain' in mime_type or file_ext == '.txt':
            text_extractor = file_helpers.get_text_from_txt
            logger.debug(f"Документ '{file_name}' определен как TXT.", extra={'user_id': str(user_id)})
        else:
            logger.warning(f"Неподдерживаемый формат документа '{file_name}' (MIME: {mime_type}, Ext: {file_ext}) от {user_id}.", extra={'user_id': str(user_id)})
            await reply_to_message(bot, message, "❌ Формат документа не поддерживается. Пожалуйста, отправьте DOCX, PDF или TXT.", reply_markup=mk.create_main_keyboard())
            user_states.pop(user_id, None)
            return

        extracted_text = await asyncio.to_thread(text_extractor, downloaded_file_path)

        if not extracted_text:
             await reply_to_message(bot, message, "❌ Не удалось извлечь текст из документа. Возможно, он пустой, защищен паролем или поврежден.", reply_markup=mk.create_main_keyboard())
             user_states.pop(user_id, None)
             return

        logger.info(f"Извлечено ~{len(extracted_text)} символов из документа '{file_name}' от {user_id}", extra={'user_id': str(user_id)})

        combined_text = extracted_text[:MAX_SUMMARIZE_CHARS]
        if len(extracted_text) > MAX_SUMMARIZE_CHARS:
            await send_message(bot, user_id, f"⚠️ Текст документа слишком длинный. Будет обработано только первые ~{MAX_SUMMARIZE_CHARS // 1000} тыс. символов.")

        user_states.pop(user_id, None)
        logger.debug(f"Состояние user_id {user_id} сброшено после обработки документа.", extra={'user_id': str(user_id)})

        await reply_to_message(bot, message, "⏳ Готовлю краткое изложение документа...", parse_mode='None')
        await send_typing_action(bot, user_id)

        prompt = f"""Сделай краткое и структурированное изложение следующего текста из документа '{file_name}'. Выдели основные мысли, ключевые моменты и, если применимо, главные выводы.
Текст для изложения:
---
{combined_text}
---
Предоставь только само изложение. Ответ должен быть на русском языке.
"""
        response = await asyncio.to_thread(gemini_service.generate_response, user_id, prompt, store_in_db=True)

        if response:
            parts = smart_split(response, chars_per_string=4000)
            for part in parts:
                await send_message(bot, user_id, part, reply_markup=mk.create_main_keyboard())
                await asyncio.sleep(0.1)
        else:
            await send_error_reply(bot, message, f"Ошибка изложения документа '{file_name}' для {user_id}", "Не удалось подготовить изложение документа. Возможно, запрос был заблокирован.")

    except Exception as e:
         await send_error_reply(bot, message, f"Критическая ошибка обработки документа '{file_name}' для {user_id}")
         user_states.pop(user_id, None)
    finally:
        if downloaded_file_path:
             await asyncio.to_thread(file_helpers.cleanup_file, downloaded_file_path)

# --- Обработчики кнопок клавиатуры (не-команд) ---

async def handle_personal_account_button(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает нажатие кнопки 'Личный кабинет'."""
    user_id = message.chat.id
    logger.info(f"Запрос личного кабинета от user_id {user_id}", extra={'user_id': str(user_id)})
    await send_typing_action(bot, user_id)
    info_text = await asyncio.to_thread(personal_account.get_personal_account_info, user_id)
    await reply_to_message(bot, message, info_text, reply_markup=mk.create_main_keyboard(), parse_mode='Markdown')

async def handle_reminders_button(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает нажатие кнопки 'Напоминания'."""
    user_id = message.chat.id
    logger.info(f"Запрос меню напоминаний от user_id {user_id}", extra={'user_id': str(user_id)})
    await send_typing_action(bot, user_id)
    try:
        user_reminders = db_manager.get_user_reminders(user_id)
        reminders_markup = mk.create_reminders_keyboard(user_reminders)
        await reply_to_message(bot, message, "⏰ **Управление напоминаниями**\nНажмите '➕', чтобы добавить новое, или на существующее напоминание, чтобы удалить его.", reply_markup=reminders_markup, parse_mode='Markdown')
    except Exception as e:
        await send_error_reply(bot, message, f"Ошибка при отображении меню напоминаний для user_id {user_id}: {e}")

# --- Обработчики специальных текстовых запросов ---

def is_help_request(message_lower: str) -> bool:
    """Проверяет, является ли сообщение запросом помощи."""
    help_keywords = ["что ты умеешь", "что можешь", "твои возможности", "функции",
                     "умеет этот бот", "кнопки", "что делают кнопки", "помощь", "справка", "хелп", "help", "/help"]
    return any(re.search(r'\b' + re.escape(keyword) + r'\b', message_lower) for keyword in help_keywords)

def is_model_request(message_lower: str) -> bool:
    """Проверяет, является ли сообщение запросом о модели."""
    model_keywords = ["модель", "какая модель", "на какой модели", "gemini", "гугл", "google"]
    return any(re.search(r'\b' + re.escape(keyword) + r'\b', message_lower) for keyword in model_keywords)

async def handle_help_request_message(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает запрос помощи по ключевым словам."""
    user_id = message.chat.id
    logger.info(f"Запрос помощи по ключевым словам от {user_id}: '{message.text[:50]}...'", extra={'user_id': str(user_id)})
    await send_typing_action(bot, user_id)
    logger.debug(f"Перенаправление запроса помощи от {user_id} на handle_help.", extra={'user_id': str(user_id)})
    from .command_handlers import handle_help
    await handle_help(message, bot)

async def handle_model_request_message(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает запрос о модели Gemini."""
    user_id = message.chat.id
    logger.info(f"Запрос о модели от {user_id}: '{message.text[:50]}...'", extra={'user_id': str(user_id)})
    await send_typing_action(bot, user_id)
    try:
        model_name = gemini_service.model.model_name
        response_text = f"Я работаю на базе нейросети **Google Gemini** (модель `{model_name}`). Это одна из современных и мощных языковых моделей от Google AI."
        await reply_to_message(bot, message, response_text, reply_markup=mk.create_main_keyboard())
    except Exception as e:
         await send_error_reply(bot, message, f"Ошибка при получении информации о модели для {user_id}: {e}", "Не удалось получить информацию о модели.")

# --- Общий обработчик текстовых запросов к Gemini ---

async def handle_general_text_query(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает обычный текстовый запрос к Gemini, применяя стиль общения."""
    user_id = message.chat.id
    text = message.text.strip()
    await send_typing_action(bot, user_id)

    user_style = db_manager.get_user_bot_style(user_id)
    style_prompt_suffix = ""
    if user_style != 'default':
        style_desc = BOT_STYLES.get(user_style, "").lower().replace('ё','е')
        style_instruction = f" (Стиль ответа: {style_desc})."
        full_prompt = text + style_instruction
        logger.debug(f"Применяется стиль '{user_style}' для user_id {user_id}. Промпт: '{full_prompt[:100]}...'", extra={'user_id': str(user_id)})
    else:
        full_prompt = text

    response = await asyncio.to_thread(gemini_service.generate_response, user_id, full_prompt, store_in_db=True)

    if response:
        parts = smart_split(response, chars_per_string=4000)
        for part in parts:
             await send_message(bot, user_id, part, reply_markup=mk.create_main_keyboard())
             await asyncio.sleep(0.05)
    else:
        await send_error_reply(bot, message, f"Ошибка Gemini при обработке текста для {user_id}", "Не удалось обработать ваш запрос. Возможно, он был заблокирован.")

# --- Регистрация обработчиков ---

def register_message_handlers(bot: AsyncTeleBot):
    """Регистрирует все обработчики сообщений."""
    bot.register_message_handler(handle_any_message,
                                 content_types=['text', 'photo', 'document', 'location'],
                                 pass_bot=True)
    logger.info("Обработчики сообщений зарегистрированы.")

# --- END OF FILE handlers/message_handlers.py ---