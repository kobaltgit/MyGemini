# File: handlers/command_handlers.py
from telebot.async_telebot import AsyncTeleBot
from telebot import types

from .states import user_states  # Импортируем состояния
from . import telegram_helpers as tg_helpers # Импортируем хелперы
from utils import markup_helpers as mk
from utils import localization as loc

from config.settings import (
    STATE_WAITING_FOR_HISTORY_DATE,
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
    await tg_helpers.send_long_message(
        bot, user_id, welcome_text,
        reply_markup=mk.create_main_keyboard(lang_code)
    )


async def handle_help(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /help."""
    user_id = message.chat.id
    lang_code = db_manager.get_user_language(user_id)
    help_text = loc.get_text('cmd_help_text', lang_code)
    await tg_helpers.send_long_message(
        bot, user_id, help_text,
        reply_markup=mk.create_main_keyboard(lang_code)
    )


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

    text = loc.get_text('set_api_key_prompt', lang_code)
    user_states[user_id] = STATE_WAITING_FOR_API_KEY
    await bot.reply_to(message, text, reply_markup=types.ReplyKeyboardRemove())


async def handle_history(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /history."""
    user_id = message.chat.id
    lang_code = db_manager.get_user_language(user_id)

    calendar_markup = mk.create_calendar_keyboard()
    text = loc.get_text('history_prompt', lang_code)
    await bot.send_message(user_id, text, reply_markup=calendar_markup)
    user_states[user_id] = STATE_WAITING_FOR_HISTORY_DATE


async def handle_settings(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /settings."""
    user_id = message.chat.id
    lang_code = db_manager.get_user_language(user_id)
    settings_markup = mk.create_settings_keyboard(user_id)
    await bot.send_message(
        user_id, loc.get_text('settings_title', lang_code),
        reply_markup=settings_markup
    )


async def handle_translate(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /translate."""
    user_id = message.chat.id
    lang_code = db_manager.get_user_language(user_id)

    lang_markup = mk.create_language_selection_keyboard()
    text = loc.get_text('translate_prompt', lang_code)
    await bot.send_message(user_id, text, reply_markup=lang_markup)


async def handle_personal_account_button(message: types.Message, bot: AsyncTeleBot):
    """Обработчик нажатия на кнопку 'Личный кабинет'."""
    user_id = message.chat.id
    await tg_helpers.send_typing_action(bot, user_id)
    info_text = await personal_account.get_personal_account_info(user_id)
    lang_code = db_manager.get_user_language(user_id)
    await tg_helpers.send_long_message(
        bot, user_id, info_text,
        reply_markup=mk.create_main_keyboard(lang_code)
    )


def register_command_handlers(bot: AsyncTeleBot):
    """Регистрирует все обработчики команд и кнопок-синонимов."""
    # Регистрация команд
    bot.register_message_handler(handle_start, commands=['start'], pass_bot=True)
    bot.register_message_handler(handle_help, commands=['help'], pass_bot=True)
    bot.register_message_handler(handle_reset, commands=['reset'], pass_bot=True)
    # Добавляем alias /setapikey
    bot.register_message_handler(handle_set_api_key, commands=['set_api_key', 'setapikey'], pass_bot=True)
    bot.register_message_handler(handle_settings, commands=['settings'], pass_bot=True)
    bot.register_message_handler(handle_history, commands=['history'], pass_bot=True)
    bot.register_message_handler(handle_translate, commands=['translate'], pass_bot=True)

    # Регистрация кнопок-синонимов, которые должны работать как команды
    # `lambda msg: msg.text in [...]` - проверяет, что текст сообщения точно совпадает с одной из строк
    # Локализация кнопок берется из `localization.py`
    bot.register_message_handler(handle_translate,
                                 func=lambda msg: msg.text in [loc.get_text('btn_translate', 'ru'),
                                                               loc.get_text('btn_translate', 'en')], pass_bot=True)
    bot.register_message_handler(handle_history,
                                 func=lambda msg: msg.text in [loc.get_text('btn_history', 'ru'),
                                                               loc.get_text('btn_history', 'en')], pass_bot=True)
    bot.register_message_handler(handle_personal_account_button,
                                 func=lambda msg: msg.text in [loc.get_text('btn_account', 'ru'),
                                                               loc.get_text('btn_account', 'en')], pass_bot=True)
    bot.register_message_handler(handle_settings,
                                 func=lambda msg: msg.text in [loc.get_text('btn_settings', 'ru'),
                                                               loc.get_text('btn_settings', 'en')], pass_bot=True)
    bot.register_message_handler(handle_help,
                                 func=lambda msg: msg.text in [loc.get_text('btn_help', 'ru'),
                                                               loc.get_text('btn_help', 'en')], pass_bot=True)
    bot.register_message_handler(handle_reset,
                                 func=lambda msg: msg.text in [loc.get_text('btn_reset', 'ru'),
                                                               loc.get_text('btn_reset', 'en')], pass_bot=True)

    logger.info("Обработчики команд и кнопок-синонимов зарегистрированы.")
