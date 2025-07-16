# File: handlers/message_handlers.py
import PIL.Image
from io import BytesIO
from typing import Optional, List, Union
from telebot.async_telebot import AsyncTeleBot
from telebot import types

from .states import user_states
from . import telegram_helpers as tg_helpers
from utils import markup_helpers as mk
from utils import localization as loc

from config.settings import (
    STATE_WAITING_FOR_TRANSLATE_TEXT,
    STATE_WAITING_FOR_API_KEY
)
from database import db_manager
from services import gemini_service
from services.gemini_service import GeminiAPIError # Импортируем кастомное исключение

from logger_config import get_logger

logger = get_logger(__name__)
user_logger = get_logger('user_messages')


async def handle_any_message(message: types.Message, bot: AsyncTeleBot):
    """
    Обрабатывает любое входящее сообщение (текст или фото).
    Является точкой входа для сообщений, не являющихся командами.
    """
    user_id = message.chat.id
    content_type = message.content_type

    user_logger.info(f"Получено сообщение ({content_type}) от user ID: {user_id}", extra={'user_id': str(user_id)})
    db_manager.add_or_update_user(user_id)
    current_state = user_states.get(user_id)

    try:
        if current_state:
            await handle_stateful_message(bot, message, current_state)
        elif content_type == 'text':
            await handle_general_text_query(bot, message)
        elif content_type == 'photo':
            await handle_photo_message(bot, message)
        else:
            lang_code = db_manager.get_user_language(user_id)
            await bot.reply_to(message, loc.get_text('unsupported_content', lang_code))
    except GeminiAPIError as e:
        lang_code = db_manager.get_user_language(user_id)
        user_friendly_error = loc.get_text(e.error_key, lang_code)
        await tg_helpers.send_long_message(bot, user_id, user_friendly_error)
    except Exception as e:
        await tg_helpers.send_error_reply(bot, message, f"Критическая ошибка в handle_any_message для user_id {user_id}: {e}")
        if user_id in user_states:
            user_states.pop(user_id, None)


async def handle_stateful_message(bot: AsyncTeleBot, message: types.Message, current_state: str):
    """Маршрутизирует сообщения от пользователей, находящихся в определенном состоянии."""
    lang_code = db_manager.get_user_language(user_id=message.chat.id)

    if message.content_type != 'text':
        await bot.reply_to(message, loc.get_text('state_wrong_content_type', lang_code))
        return

    state_handlers = {
        STATE_WAITING_FOR_API_KEY: handle_state_api_key,
        STATE_WAITING_FOR_TRANSLATE_TEXT: handle_state_translate,
    }
    handler = state_handlers.get(current_state)
    if handler:
        await handler(bot, message)
    else:
        logger.warning(f"Нет обработчика для состояния '{current_state}' у пользователя {message.chat.id}", extra={'user_id': str(message.chat.id)})
        user_states.pop(message.chat.id, None)


# --- Обработчики состояний ---

async def handle_state_api_key(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает получение API-ключа от пользователя."""
    user_id = message.chat.id
    api_key = message.text.strip()
    lang_code = db_manager.get_user_language(user_id)

    try:
        await bot.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение с API ключом для user {user_id}: {e}", extra={'user_id': str(user_id)})

    status_msg = await bot.send_message(user_id, loc.get_text('api_key_verifying', lang_code))
    is_valid = await gemini_service.validate_api_key(api_key)

    try:
        await bot.delete_message(user_id, status_msg.message_id)
    except Exception as e:
        logger.warning(f"Не удалось удалить статусное сообщение для user {user_id}: {e}", extra={'user_id': str(user_id)})

    if is_valid:
        db_manager.set_user_api_key(user_id, api_key)
        user_states.pop(user_id, None)
        text = loc.get_text('api_key_success', lang_code)
        await bot.send_message(user_id, text, reply_markup=mk.create_main_keyboard(lang_code))
    else:
        text = loc.get_text('api_key_invalid', lang_code)
        await bot.send_message(user_id, text)


async def handle_state_translate(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает текст для перевода."""
    user_id = message.chat.id
    text_to_translate = message.text
    target_lang_code = user_states.get(f"{user_id}_target_lang")
    lang_code = db_manager.get_user_language(user_id)
    api_key = db_manager.get_user_api_key(user_id)

    if not api_key:
        await bot.reply_to(message, loc.get_text('api_key_needed_for_feature', lang_code))
        user_states.pop(user_id, None)
        return
    if not target_lang_code:
        logger.error(f"Отсутствует target_lang_code для перевода у user {user_id}", extra={'user_id': str(user_id)})
        await bot.reply_to(message, loc.get_text('translation_error_generic', lang_code))
        user_states.pop(user_id, None)
        return

    await tg_helpers.send_typing_action(bot, user_id)
    translated_text = await gemini_service.generate_content_simple(api_key, f"Translate the following text to {target_lang_code}: '{text_to_translate}'")

    if translated_text:
        await bot.reply_to(message, translated_text)

    user_states.pop(user_id, None)
    user_states.pop(f"{user_id}_target_lang", None)


# --- Основные обработчики ---

async def handle_general_text_query(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает общий текстовый запрос к Gemini."""
    user_id = message.chat.id
    api_key = db_manager.get_user_api_key(user_id)
    lang_code = db_manager.get_user_language(user_id)

    if not api_key:
        await bot.reply_to(message, loc.get_text('api_key_needed_for_chat', lang_code))
        return

    await tg_helpers.send_typing_action(bot, user_id)
    response = await gemini_service.generate_response(user_id, api_key, message.text)
    await tg_helpers.send_long_message(bot, user_id, response)


async def handle_photo_message(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает запрос к Gemini с изображением."""
    user_id = message.chat.id
    api_key = db_manager.get_user_api_key(user_id)
    lang_code = db_manager.get_user_language(user_id)

    if not api_key:
        await bot.reply_to(message, loc.get_text('api_key_needed_for_vision', lang_code))
        return

    await tg_helpers.send_typing_action(bot, user_id)
    file_info = await bot.get_file(message.photo[-1].file_id)
    downloaded_bytes = await bot.download_file(file_info.file_path)
    image = PIL.Image.open(BytesIO(downloaded_bytes))

    prompt_text = message.caption or loc.get_text('vision_default_prompt', lang_code)
    prompt: List[Union[str, PIL.Image.Image]] = [prompt_text, image]

    response = await gemini_service.generate_response(user_id, api_key, prompt)
    await tg_helpers.send_long_message(bot, user_id, response)


def register_message_handlers(bot: AsyncTeleBot):
    """Регистрирует универсальный обработчик для текстовых сообщений и фото."""
    bot.register_message_handler(handle_any_message, content_types=['text', 'photo'], pass_bot=True)
    logger.info("Универсальный обработчик сообщений (текст и фото) зарегистрирован.")
