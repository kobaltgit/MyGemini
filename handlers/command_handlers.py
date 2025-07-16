import asyncio
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from telebot import apihelper

from .states import user_states
from utils.telegram_helpers import send_long_message, send_typing_action, send_error_reply
from utils import markup_helpers as mk
from utils import localization as loc

from config.settings import (
    ADMIN_USER_ID, TRANSLATE_LANGUAGES, CALLBACK_LANG_PREFIX,
    STATE_WAITING_FOR_TRANSLATE_TEXT, STATE_WAITING_FOR_HISTORY_DATE,
    STATE_WAITING_FOR_API_KEY
)
from database import db_manager
from services import gemini_service
from features import personal_account
from logger_config import get_logger

logger = get_logger(__name__)

async def handle_start(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /start."""
    user_id = message.chat.id
    first_name = message.from_user.first_name or "User"
    logger.info(f"Команда /start от user_id: {user_id}", extra={'user_id': str(user_id)})

    db_manager.add_or_update_user(user_id)
    lang_code = db_manager.get_user_language(user_id)

    if user_id in user_states:
        user_states.pop(user_id, None)
    gemini_service.reset_user_chat(user_id)

    welcome_text = loc.get_text('welcome', lang_code).format(name=first_name)
    await send_long_message(bot, user_id, welcome_text, reply_markup=mk.create_main_keyboard(lang_code), parse_mode='Markdown')

async def handle_help(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /help."""
    user_id = message.chat.id
    lang_code = db_manager.get_user_language(user_id)
    help_text = loc.get_text('cmd_help_title', lang_code) # Будет дополнено

    # Примерная справка (нужно будет добавить в localization.py)
    help_text += "\n\n/start - Start the bot\n/set_api_key - Set your Google AI API key\n/help - Show this message"
    await send_long_message(bot, user_id, help_text, reply_markup=mk.create_main_keyboard(lang_code), parse_mode='Markdown')

async def handle_reset(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /reset."""
    user_id = message.chat.id
    lang_code = db_manager.get_user_language(user_id)

    if user_id in user_states:
        user_states.pop(user_id, None)
    gemini_service.reset_user_chat(user_id)

    reset_text = loc.get_text('cmd_reset_success', lang_code)
    await bot.reply_to(message, reset_text, reply_markup=mk.create_main_keyboard(lang_code))

async def handle_set_api_key(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /set_api_key."""
    user_id = message.chat.id
    lang_code = db_manager.get_user_language(user_id)

    text = "Пожалуйста, отправьте ваш Google AI API ключ." if lang_code == 'ru' else "Please send your Google AI API key."
    user_states[user_id] = STATE_WAITING_FOR_API_KEY
    await bot.reply_to(message, text, reply_markup=types.ReplyKeyboardRemove())

async def handle_history(message: types.Message, bot: AsyncTeleBot):
    user_id = message.chat.id
    lang_code = db_manager.get_user_language(user_id)

    calendar_markup = mk.create_calendar_keyboard()
    text = "🗓️ Выберите дату для просмотра истории:" if lang_code == 'ru' else "🗓️ Please select a date to view the history:"
    await bot.send_message(user_id, text, reply_markup=calendar_markup)
    user_states[user_id] = STATE_WAITING_FOR_HISTORY_DATE

async def handle_settings(message: types.Message, bot: AsyncTeleBot):
    user_id = message.chat.id
    lang_code = db_manager.get_user_language(user_id)
    settings_markup = mk.create_settings_keyboard(user_id)
    await bot.send_message(user_id, loc.get_text('settings_title', lang_code), reply_markup=settings_markup, parse_mode='Markdown')

async def handle_translate(message: types.Message, bot: AsyncTeleBot):
    user_id = message.chat.id
    lang_code = db_manager.get_user_language(user_id)

    lang_markup = mk.create_language_selection_keyboard()
    text = "Выберите язык, на который нужно перевести текст:" if lang_code == 'ru' else "Select the language to translate the text into:"
    await bot.send_message(user_id, text, reply_markup=lang_markup)

async def handle_personal_account_button(message: types.Message, bot: AsyncTeleBot):
    user_id = message.chat.id
    await send_typing_action(bot, user_id)
    # personal_account.get_personal_account_info теперь async
    info_text = await personal_account.get_personal_account_info(user_id)
    lang_code = db_manager.get_user_language(user_id)
    await send_long_message(bot, user_id, info_text, reply_markup=mk.create_main_keyboard(lang_code), parse_mode='Markdown')

def register_command_handlers(bot: AsyncTeleBot):
    """Регистрирует все обработчики команд и кнопок-синонимов."""
    bot.register_message_handler(handle_start, commands=['start'], pass_bot=True)
    bot.register_message_handler(handle_help, commands=['help'], pass_bot=True)
    bot.register_message_handler(handle_reset, commands=['reset'], pass_bot=True)
    bot.register_message_handler(handle_set_api_key, commands=['set_api_key'], pass_bot=True)
    bot.register_message_handler(handle_settings, commands=['settings'], pass_bot=True)
    bot.register_message_handler(handle_history, commands=['history'], pass_bot=True)
    bot.register_message_handler(handle_translate, commands=['translate'], pass_bot=True)

    # Регистрация кнопок-синонимов
    bot.register_message_handler(handle_translate, func=lambda msg: msg.text in ["🇷🇺 Перевести", "🇬🇧 Translate"], pass_bot=True)
    bot.register_message_handler(handle_history, func=lambda msg: msg.text in ["📜 История", "📜 History"], pass_bot=True)
    bot.register_message_handler(handle_personal_account_button, func=lambda msg: msg.text in ["👤 Личный кабинет", "👤 My Account"], pass_bot=True)
    bot.register_message_handler(handle_settings, func=lambda msg: msg.text in ["⚙️ Настройки", "⚙️ Settings"], pass_bot=True)
    bot.register_message_handler(handle_help, func=lambda msg: msg.text in ["❓ Помощь", "❓ Help"], pass_bot=True)
    bot.register_message_handler(handle_reset, func=lambda msg: msg.text in ["🔄 Сброс", "🔄 Reset"], pass_bot=True)

    logger.info("Обработчики команд и кнопок-синонимов зарегистрированы.")
