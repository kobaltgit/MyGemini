import asyncio
from telebot.async_telebot import AsyncTeleBot
from telebot import types

from config.settings import (
    ADMIN_USER_ID, BOT_STYLES, TRANSLATE_LANGUAGES,
    CALLBACK_LANG_PREFIX, STATE_WAITING_FOR_TRANSLATE_TEXT,
    CALLBACK_CALENDAR_DATE_PREFIX, CALLBACK_CALENDAR_MONTH_PREFIX, STATE_WAITING_FOR_HISTORY_DATE,
    CALLBACK_SETTINGS_STYLE_PREFIX, CALLBACK_SETTINGS_LANG_PREFIX,
    CALLBACK_REPORT_ERROR, CALLBACK_IGNORE
)
from database import db_manager
from services import gemini_service
from utils import markup_helpers as mk
from utils.telegram_helpers import edit_message_text_safe, send_long_message
from .states import user_states
from logger_config import get_logger
from utils import localization as loc

logger = get_logger(__name__)

async def answer_callback_query(bot: AsyncTeleBot, call: types.CallbackQuery, text=None, show_alert=False):
    try:
        await bot.answer_callback_query(call.id, text=text, show_alert=show_alert)
    except Exception:
        pass

async def handle_callback_query(call: types.CallbackQuery, bot: AsyncTeleBot):
    """Обрабатывает все callback запросы."""
    user_id = call.from_user.id
    data = call.data
    message = call.message

    if not message:
        await answer_callback_query(bot, call)
        return

    logger.debug(f"Получен callback query от user_id: {user_id}. Data: '{data}'.", extra={'user_id': str(user_id)})
    db_manager.add_or_update_user(user_id)

    try:
        if data == CALLBACK_IGNORE:
            await answer_callback_query(bot, call)

        elif data.startswith(CALLBACK_LANG_PREFIX):
            await handle_language_selection_for_translation(bot, call)

        elif data.startswith(CALLBACK_SETTINGS_STYLE_PREFIX):
            await handle_style_setting(bot, call)

        elif data.startswith(CALLBACK_SETTINGS_LANG_PREFIX):
            await handle_language_setting(bot, call)

        elif data.startswith(CALLBACK_CALENDAR_DATE_PREFIX):
            await handle_calendar_date_selection(bot, call)

        elif data.startswith(CALLBACK_CALENDAR_MONTH_PREFIX):
            await handle_calendar_month_navigation(bot, call)

        else:
            await answer_callback_query(bot, call, text="Unknown action", show_alert=True)

    except Exception as e:
        logger.exception(f"Критическая ошибка обработки callback query: {e}", extra={'user_id': str(user_id)})
        await answer_callback_query(bot, call, text="An internal error occurred.", show_alert=True)

async def handle_language_setting(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает смену языка интерфейса."""
    user_id = call.from_user.id
    lang_code = call.data[len(CALLBACK_SETTINGS_LANG_PREFIX):]

    db_manager.set_user_language(user_id, lang_code)

    new_markup = mk.create_settings_keyboard(user_id)
    await edit_message_text_safe(bot, call.message.chat.id, call.message.message_id, 
                                 loc.get_text('settings_title', lang_code), 
                                 reply_markup=new_markup, parse_mode='Markdown')
    await answer_callback_query(bot, call, text=f"Language set to {'English' if lang_code == 'en' else 'Русский'}")

async def handle_style_setting(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает выбор стиля общения бота."""
    user_id = call.from_user.id
    style_code = call.data[len(CALLBACK_SETTINGS_STYLE_PREFIX):]

    if style_code in BOT_STYLES:
        db_manager.set_user_bot_style(user_id, style_code)
        gemini_service.reset_user_chat(user_id)

        new_markup = mk.create_settings_keyboard(user_id)
        lang_code = db_manager.get_user_language(user_id)

        await edit_message_text_safe(bot, call.message.chat.id, call.message.message_id,
                                loc.get_text('settings_title', lang_code),
                                reply_markup=new_markup, parse_mode='Markdown')
        await answer_callback_query(bot, call, text="Стиль изменен / Style changed")

async def handle_language_selection_for_translation(bot: AsyncTeleBot, call: types.CallbackQuery):
    # Эта функция остается почти без изменений
    user_id = call.from_user.id
    lang_code = call.data[len(CALLBACK_LANG_PREFIX):]
    lang_name = TRANSLATE_LANGUAGES.get(lang_code, lang_code)

    user_states[user_id] = STATE_WAITING_FOR_TRANSLATE_TEXT
    user_states[f"{user_id}_target_lang"] = lang_code

    await answer_callback_query(bot, call, text=f"Выбран язык: {lang_name}")
    await edit_message_text_safe(bot, call.message.chat.id, call.message.message_id,
                                 f"Выбран язык: **{lang_name}**.\n\nТеперь отправьте текст для перевода.",
                                 reply_markup=None, parse_mode='Markdown')

async def handle_calendar_date_selection(bot: AsyncTeleBot, call: types.CallbackQuery):
    # Эта функция остается почти без изменений
    user_id = call.from_user.id
    selected_date_str = call.data[len(CALLBACK_CALENDAR_DATE_PREFIX):]

    if user_states.get(user_id) == STATE_WAITING_FOR_HISTORY_DATE:
        selected_date = datetime.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        history = db_manager.get_conversation_history_by_date(user_id, selected_date)
        # ... (логика отображения истории, нужно будет добавить локализацию)
        await bot.send_message(user_id, f"History for {selected_date_str}: {len(history)} messages.")
        user_states.pop(user_id, None)

async def handle_calendar_month_navigation(bot: AsyncTeleBot, call: types.CallbackQuery):
    # Эта функция остается без изменений
    year, month = map(int, call.data[len(CALLBACK_CALENDAR_MONTH_PREFIX):].split('-'))
    new_markup = mk.create_calendar_keyboard(year, month)
    await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=new_markup)

def register_callback_handlers(bot: AsyncTeleBot):
    bot.register_callback_query_handler(handle_callback_query, func=lambda call: True, pass_bot=True)
    logger.info("Обработчик callback query зарегистрирован.")
