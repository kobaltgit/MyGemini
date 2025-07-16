# File: handlers/message_handlers.py
import PIL.Image
from io import BytesIO
from typing import Optional, List, Union
from telebot.async_telebot import AsyncTeleBot
from telebot import types

from . import telegram_helpers as tg_helpers
from utils import markup_helpers as mk
from utils import localization as loc

from config.settings import (
    STATE_WAITING_FOR_TRANSLATE_TEXT,
    STATE_WAITING_FOR_API_KEY,
    STATE_WAITING_FOR_NEW_DIALOG_NAME, # Импорт состояний
    STATE_WAITING_FOR_RENAME_DIALOG,
    GEMINI_MODEL_NAME,
    BOT_PERSONAS
)
from database import db_manager
from services import gemini_service
from services.gemini_service import GeminiAPIError

from logger_config import get_logger

logger = get_logger(__name__)
user_logger = get_logger('user_messages')

# НОВАЯ ФУНКЦИЯ для создания заголовка
async def _create_context_header(user_id: int, lang_code: str) -> str:
    """Создает текстовый заголовок с информацией о текущем контексте."""
    context_info = await db_manager.get_user_context_info(user_id)
    if not context_info:
        return ""

    dialog_name = context_info.get('dialog_name', '..._')
    persona_id = context_info.get('active_persona', 'default')
    model_name = context_info.get('gemini_model') or GEMINI_MODEL_NAME

    persona_info = BOT_PERSONAS.get(persona_id, BOT_PERSONAS['default'])
    persona_name = persona_info.get(f"name_{lang_code}", persona_info.get('name_ru', '...'))

    header = (
        f"•  **Диалог:** `{dialog_name}`\n"
        f"•  **Персона:** `{persona_name}`\n"
        f"•  **Модель:** `{model_name}`\n"
        f"---"
    )
    return header

async def handle_any_message(message: types.Message, bot: AsyncTeleBot):
    """
    Обрабатывает любое входящее сообщение (текст или фото).
    """
    user_id = message.chat.id
    content_type = message.content_type

    user_logger.info(f"Получено сообщение ({content_type}) от user ID: {user_id}", extra={'user_id': str(user_id)})
    await db_manager.add_or_update_user(user_id)
    current_state = await bot.get_state(message.from_user.id, message.chat.id)

    try:
        if current_state:
            await handle_stateful_message(bot, message, current_state)
        elif content_type == 'text':
            await handle_general_text_query(bot, message)
        elif content_type == 'photo':
            await handle_photo_message(bot, message)
        else:
            lang_code = await db_manager.get_user_language(user_id)
            await bot.reply_to(message, loc.get_text('unsupported_content', lang_code))
    except GeminiAPIError as e:
        lang_code = await db_manager.get_user_language(user_id)
        user_friendly_error = loc.get_text(e.error_key, lang_code)
        await tg_helpers.send_long_message(bot, user_id, user_friendly_error)
    except Exception as e:
        await tg_helpers.send_error_reply(bot, message, f"Критическая ошибка в handle_any_message: {e}")
        await bot.delete_state(message.from_user.id, message.chat.id)


async def handle_stateful_message(bot: AsyncTeleBot, message: types.Message, current_state: str):
    """Маршрутизирует сообщения от пользователей, находящихся в определенном состоянии."""
    lang_code = await db_manager.get_user_language(user_id=message.chat.id)

    if message.content_type != 'text':
        await bot.reply_to(message, loc.get_text('state_wrong_content_type', lang_code))
        return

    state_handlers = {
        STATE_WAITING_FOR_API_KEY: handle_state_api_key,
        STATE_WAITING_FOR_TRANSLATE_TEXT: handle_state_translate,
        STATE_WAITING_FOR_NEW_DIALOG_NAME: handle_state_new_dialog_name,
        STATE_WAITING_FOR_RENAME_DIALOG: handle_state_rename_dialog,
    }
    handler = state_handlers.get(current_state)
    if handler:
        await handler(bot, message)
    else:
        logger.warning(f"Нет обработчика для состояния '{current_state}' у {message.chat.id}", extra={'user_id': str(message.chat.id)})
        await bot.delete_state(message.from_user.id, message.chat.id)


# --- Обработчики состояний ---

async def handle_state_api_key(bot: AsyncTeleBot, message: types.Message):
    user_id = message.chat.id
    api_key = message.text.strip()
    lang_code = await db_manager.get_user_language(user_id)
    try:
        await bot.delete_message(message.chat.id, message.message_id)
    except Exception: pass
    status_msg = await bot.send_message(user_id, loc.get_text('api_key_verifying', lang_code))
    is_valid = await gemini_service.validate_api_key(api_key)
    try:
        await bot.delete_message(user_id, status_msg.message_id)
    except Exception: pass
    if is_valid:
        await db_manager.set_user_api_key(user_id, api_key)
        await bot.delete_state(message.from_user.id, message.chat.id)
        text = loc.get_text('api_key_success', lang_code)
        await bot.send_message(user_id, text, reply_markup=mk.create_main_keyboard(lang_code))
    else:
        text = loc.get_text('api_key_invalid', lang_code)
        await bot.send_message(user_id, text)

async def handle_state_translate(bot: AsyncTeleBot, message: types.Message):
    user_id = message.chat.id
    text_to_translate = message.text
    lang_code = await db_manager.get_user_language(user_id)
    api_key = await db_manager.get_user_api_key(user_id)
    async with bot.retrieve_data(user_id, message.chat.id) as data:
        target_lang_code = data.get('target_lang')
    if not api_key:
        await bot.reply_to(message, loc.get_text('api_key_needed_for_feature', lang_code))
        await bot.delete_state(user_id, message.chat.id)
        return
    if not target_lang_code:
        await bot.reply_to(message, loc.get_text('translation_error_generic', lang_code))
        await bot.delete_state(user_id, message.chat.id)
        return
    await tg_helpers.send_typing_action(bot, user_id)
    translated_text = await gemini_service.generate_content_simple(api_key, f"Translate to {target_lang_code}: '{text_to_translate}'")
    if translated_text:
        await bot.reply_to(message, translated_text)
    await bot.delete_state(user_id, message.chat.id)

async def handle_state_new_dialog_name(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает ввод названия нового диалога."""
    user_id = message.chat.id
    lang_code = await db_manager.get_user_language(user_id)
    dialog_name = message.text.strip()

    if not dialog_name:
        await bot.reply_to(message, loc.get_text('dialog_name_invalid', lang_code))
        return
    if len(dialog_name) > 50:
        await bot.reply_to(message, loc.get_text('dialog_name_too_long', lang_code))
        return

    await db_manager.create_dialog(user_id, dialog_name, set_active=True)
    await bot.delete_state(user_id, message.chat.id)
    await bot.send_message(user_id, loc.get_text('dialog_created_success', lang_code).format(name=dialog_name))

    # Отправляем обновленное меню
    dialog_keyboard = await mk.create_dialogs_menu_keyboard(user_id)
    await bot.send_message(
        user_id,
        loc.get_text('dialogs_menu_title', lang_code),
        reply_markup=dialog_keyboard
    )

async def handle_state_rename_dialog(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает ввод нового названия для диалога."""
    user_id = message.chat.id
    lang_code = await db_manager.get_user_language(user_id)
    new_name = message.text.strip()

    if not new_name:
        await bot.reply_to(message, loc.get_text('dialog_name_invalid', lang_code))
        return
    if len(new_name) > 50:
        await bot.reply_to(message, loc.get_text('dialog_name_too_long', lang_code))
        return

    async with bot.retrieve_data(user_id, message.chat.id) as data:
        dialog_id_to_rename = data.get('dialog_id_to_rename')

    if dialog_id_to_rename:
        await db_manager.rename_dialog(dialog_id_to_rename, new_name)
        await bot.delete_state(user_id, message.chat.id)
        await bot.send_message(user_id, loc.get_text('renamed_success', lang_code).format(new_name=new_name))
        
        dialog_keyboard = await mk.create_dialogs_menu_keyboard(user_id)
        await bot.send_message(
            user_id, loc.get_text('dialogs_menu_title', lang_code),
            reply_markup=dialog_keyboard
        )
    else:
        logger.error(f"Не найден dialog_id_to_rename в состоянии у {user_id}", extra={'user_id': str(user_id)})
        await bot.delete_state(user_id, message.chat.id)

# --- Основные обработчики ---

async def handle_general_text_query(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает общий текстовый запрос к Gemini."""
    user_id = message.chat.id
    lang_code = await db_manager.get_user_language(user_id)
    api_key_exists = await db_manager.get_user_api_key(user_id)
    if not api_key_exists:
        await bot.reply_to(message, loc.get_text('api_key_needed_for_chat', lang_code))
        return
    await tg_helpers.send_typing_action(bot, user_id)
    response = await gemini_service.generate_response(user_id, message.text)
    header = await _create_context_header(user_id, lang_code)
    await tg_helpers.send_long_message(bot, user_id, f"{header}\n\n{response}")

async def handle_photo_message(bot: AsyncTeleBot, message: types.Message):
    """Обрабатывает запрос к Gemini с изображением."""
    user_id = message.chat.id
    lang_code = await db_manager.get_user_language(user_id)
    api_key_exists = await db_manager.get_user_api_key(user_id)
    if not api_key_exists:
        await bot.reply_to(message, loc.get_text('api_key_needed_for_vision', lang_code))
        return
    await tg_helpers.send_typing_action(bot, user_id)
    file_info = await bot.get_file(message.photo[-1].file_id)
    downloaded_bytes = await bot.download_file(file_info.file_path)
    image = PIL.Image.open(BytesIO(downloaded_bytes))
    prompt_text = message.caption or loc.get_text('vision_default_prompt', lang_code)
    prompt: List[Union[str, PIL.Image.Image]] = [prompt_text, image]
    response = await gemini_service.generate_response(user_id, prompt)
    header = await _create_context_header(user_id, lang_code)
    await tg_helpers.send_long_message(bot, user_id, f"{header}\n\n{response}")

def register_message_handlers(bot: AsyncTeleBot):
    """Регистрирует универсальный обработчик для текстовых сообщений и фото."""
    bot.register_message_handler(handle_any_message, content_types=['text', 'photo'], pass_bot=True)
    logger.info("Универсальный обработчик сообщений (текст и фото) зарегистрирован.")