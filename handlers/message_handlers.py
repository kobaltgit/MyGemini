import asyncio
import PIL.Image
from io import BytesIO
from typing import Optional, List, Union
from telebot.async_telebot import AsyncTeleBot
from telebot import types

from .states import user_states
from config.settings import (
    STATE_WAITING_FOR_TRANSLATE_TEXT, STATE_WAITING_FOR_HISTORY_DATE,
    STATE_WAITING_FOR_API_KEY, BOT_STYLES, TRANSLATE_LANGUAGES
)
from database import db_manager
from services import gemini_service
from utils import markup_helpers as mk
from utils.telegram_helpers import (
    send_long_message, send_typing_action, send_error_reply
)
from logger_config import get_logger

logger = get_logger(__name__)
user_logger = get_logger('user_messages')

async def handle_any_message(message: types.Message, bot: AsyncTeleBot):
    """Обрабатывает любое входящее сообщение."""
    user_id = message.chat.id
    content_type = message.content_type

    user_logger.info(f"Получено сообщение ({content_type}) от user ID: {user_id}", extra={'user_id': str(user_id)})
    db_manager.add_or_update_user(user_id)
    current_state = user_states.get(user_id)

    try:
        if content_type == 'text':
            await handle_text_message(bot, message, current_state)
        elif content_type == 'photo':
            if current_state:
                await bot.reply_to(message, "Пожалуйста, завершите текущее действие или нажмите /reset.")
            else:
                await handle_photo_message(bot, message)
        else:
            await bot.reply_to(message, "Я пока не умею обрабатывать такой тип контента.")
    except Exception as e:
        await send_error_reply(bot, message, f"Критическая ошибка в handle_any_message для user_id {user_id}")
        if user_id in user_states: user_states.pop(user_id, None)

async def handle_text_message(bot: AsyncTeleBot, message: types.Message, current_state: Optional[str]):
    """Обрабатывает входящие текстовые сообщения."""
    state_handlers = {
        STATE_WAITING_FOR_API_KEY: handle_state_api_key,
        STATE_WAITING_FOR_TRANSLATE_TEXT: handle_state_translate,
    }
    if current_state in state_handlers:
        await state_handlers[current_state](bot, message)
        return

    await handle_general_text_query(bot, message)

# --- Обработчики состояний ---

async def handle_state_api_key(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает получение API-ключа от пользователя."""
    user_id = message.chat.id
    api_key = message.text.strip()
    lang_code = db_manager.get_user_language(user_id)

    await bot.delete_message(message.chat.id, message.message_id)

    status_msg = await bot.send_message(user_id, "Проверяю ключ... / Verifying key...")

    is_valid = await gemini_service.validate_api_key(api_key)

    if is_valid:
        db_manager.set_user_api_key(user_id, api_key)
        user_states.pop(user_id, None)
        text = "✅ Ключ успешно установлен и зашифрован! Теперь вы можете общаться со мной."
        if lang_code == 'en': text = "✅ Key successfully set and encrypted! You can now chat with me."
        await bot.edit_message_text(text, user_id, status_msg.message_id, reply_markup=mk.create_main_keyboard(lang_code))
    else:
        text = "❌ Этот ключ недействителен. Пожалуйста, проверьте его и попробуйте снова, вызвав /set_api_key."
        if lang_code == 'en': text = "❌ This key is invalid. Please check it and try again by calling /set_api_key."
        await bot.edit_message_text(text, user_id, status_msg.message_id)

async def handle_state_translate(bot: AsyncTeleBot, message: types.Message):
    # Эта функция остается почти без изменений, но теперь использует API ключ
    user_id = message.chat.id
    target_lang_code = user_states.get(f"{user_id}_target_lang")
    api_key = db_manager.get_user_api_key(user_id)

    if not api_key:
        await bot.reply_to(message, "Для перевода нужен API ключ. Пожалуйста, установите его через /set_api_key.")
        return

    # ... (логика перевода)

# --- Основные обработчики ---

async def handle_general_text_query(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает общий текстовый запрос к Gemini."""
    user_id = message.chat.id
    api_key = db_manager.get_user_api_key(user_id)
    lang_code = db_manager.get_user_language(user_id)

    if not api_key:
        text = "Для общения со мной нужен API ключ. Пожалуйста, установите его с помощью команды /set_api_key."
        if lang_code == 'en': text = "To chat with me, an API key is required. Please set it using the /set_api_key command."
        await bot.reply_to(message, text)
        return

    await send_typing_action(bot, user_id)
    response = await gemini_service.generate_response(user_id, api_key, message.text)

    if response:
        await send_long_message(bot, user_id, response, parse_mode='Markdown')
    else:
        await send_error_reply(bot, message, f"Ошибка Gemini для {user_id}", "Не удалось обработать запрос.")

async def handle_photo_message(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает запрос к Gemini с изображением."""
    user_id = message.chat.id
    api_key = db_manager.get_user_api_key(user_id)
    lang_code = db_manager.get_user_language(user_id)

    if not api_key:
        text = "Для анализа изображений нужен API ключ. Пожалуйста, установите его с помощью команды /set_api_key."
        if lang_code == 'en': text = "To analyze images, an API key is required. Please set it using the /set_api_key command."
        await bot.reply_to(message, text)
        return

    await send_typing_action(bot, user_id)

    try:
        file_info = await bot.get_file(message.photo[-1].file_id)
        downloaded_bytes = await bot.download_file(file_info.file_path)
        image = PIL.Image.open(BytesIO(downloaded_bytes))

        prompt_text = message.caption or ("Подробно опиши, что на картинке." if lang_code == 'ru' else "Describe in detail what is in the picture.")
        prompt = [prompt_text, image]

        response = await gemini_service.generate_response(user_id, api_key, prompt)

        if response:
            await send_long_message(bot, user_id, response, parse_mode='Markdown')
        else:
            await send_error_reply(bot, message, f"Ошибка Gemini (фото) для {user_id}", "Не удалось обработать изображение.")

    except Exception as e:
        await send_error_reply(bot, message, f"Ошибка обработки фото для {user_id}: {e}")

def register_message_handlers(bot: AsyncTeleBot):
    bot.register_message_handler(handle_any_message, content_types=['text', 'photo'], pass_bot=True)
    logger.info("Универсальный обработчик сообщений зарегистрирован.")
