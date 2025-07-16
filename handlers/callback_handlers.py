import asyncio
import datetime
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from telebot import apihelper

from config.settings import (
    BOT_STYLES, TRANSLATE_LANGUAGES,
    CALLBACK_LANG_PREFIX, STATE_WAITING_FOR_TRANSLATE_TEXT,
    CALLBACK_CALENDAR_DATE_PREFIX, CALLBACK_CALENDAR_MONTH_PREFIX, STATE_WAITING_FOR_HISTORY_DATE,
    CALLBACK_SETTINGS_STYLE_PREFIX, CALLBACK_SETTINGS_LANG_PREFIX,
    CALLBACK_IGNORE
)
from database import db_manager
from services import gemini_service
# ИСПРАВЛЕНО: импортируем хелперы из правильного места
from utils import markup_helpers as mk
from utils import localization as loc
# ИСПРАВЛЕНО: user_states импортируется из command_handlers
from .command_handlers import user_states 
# ИСПРАВЛЕНО: импортируем send_long_message из message_handlers
from .message_handlers import send_long_message 
from logger_config import get_logger

logger = get_logger(__name__)

# --- Вспомогательные функции, которые раньше были в telegram_helpers ---

async def answer_callback_query(bot: AsyncTeleBot, call: types.CallbackQuery, text=None, show_alert=False, cache_time=0):
    """Отвечает на callback query."""
    try:
        await bot.answer_callback_query(call.id, text=text, show_alert=show_alert, cache_time=cache_time)
    except Exception as e:
        logger.debug(f"Ошибка при ответе на callback query {call.id}: {e}", extra={'user_id': str(call.from_user.id)})

async def edit_message_text_safe(bot: AsyncTeleBot, chat_id: int, message_id: int, text: str, reply_markup=None, parse_mode='Markdown'):
    """Редактирует текст сообщения с обработкой ошибок Markdown."""
    try:
        await bot.edit_message_text(text, chat_id, message_id, reply_markup=reply_markup, parse_mode=parse_mode)
    except apihelper.ApiException as e:
        if "message is not modified" in str(e).lower():
             logger.debug(f"Сообщение {message_id} не изменено.", extra={'user_id': str(chat_id)})
        elif parse_mode == 'Markdown' and "can't parse entities" in str(e).lower():
            logger.warning(f"Ошибка Markdown при редактировании {message_id}. Попытка как plain text.", extra={'user_id': str(chat_id)})
            try:
                await bot.edit_message_text(text, chat_id, message_id, reply_markup=reply_markup, parse_mode='None')
            except apihelper.ApiException as fallback_e:
                 logger.error(f"Ошибка при повторном редактировании (plain text) {message_id}: {fallback_e}", extra={'user_id': str(chat_id)})
        else:
            logger.error(f"Ошибка API при редактировании {message_id}: {e}", extra={'user_id': str(chat_id)})


# --- Основной обработчик ---

async def handle_callback_query(call: types.CallbackQuery, bot: AsyncTeleBot):
    """Обрабатывает все callback запросы."""
    user_id = call.from_user.id
    data = call.data
    message = call.message

    if not message:
        await answer_callback_query(bot, call)
        return

    db_manager.add_or_update_user(user_id)
    lang_code = db_manager.get_user_language(user_id)

    try:
        if data == CALLBACK_IGNORE:
            await answer_callback_query(bot, call)

        elif data.startswith(CALLBACK_LANG_PREFIX):
            await handle_language_selection_for_translation(bot, call, lang_code)

        elif data.startswith(CALLBACK_SETTINGS_STYLE_PREFIX):
            await handle_style_setting(bot, call)

        elif data.startswith(CALLBACK_SETTINGS_LANG_PREFIX):
            await handle_language_setting(bot, call)

        elif data.startswith(CALLBACK_CALENDAR_DATE_PREFIX):
            await handle_calendar_date_selection(bot, call, lang_code)

        elif data.startswith(CALLBACK_CALENDAR_MONTH_PREFIX):
            await handle_calendar_month_navigation(bot, call)

        else:
            await answer_callback_query(bot, call, text="Unknown action", show_alert=True)

    except Exception as e:
        logger.exception(f"Критическая ошибка обработки callback query: {e}", extra={'user_id': str(user_id)})
        await answer_callback_query(bot, call, text="An internal error occurred.", show_alert=True)

# --- Обработчики конкретных колбэков ---

async def handle_language_setting(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает смену языка интерфейса."""
    user_id = call.from_user.id
    new_lang_code = call.data[len(CALLBACK_SETTINGS_LANG_PREFIX):]

    db_manager.set_user_language(user_id, new_lang_code)

    new_markup = mk.create_settings_keyboard(user_id)
    await edit_message_text_safe(bot, call.message.chat.id, call.message.message_id, 
                                 loc.get_text('settings_title', new_lang_code), 
                                 reply_markup=new_markup, parse_mode='Markdown')
    await answer_callback_query(bot, call, text=f"Language set to {'English' if new_lang_code == 'en' else 'Русский'}")

async def handle_style_setting(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает выбор стиля общения бота."""
    user_id = call.from_user.id
    style_code = call.data[len(CALLBACK_SETTINGS_STYLE_PREFIX):]
    lang_code = db_manager.get_user_language(user_id)

    if style_code in BOT_STYLES:
        db_manager.set_user_bot_style(user_id, style_code)
        gemini_service.reset_user_chat(user_id)

        new_markup = mk.create_settings_keyboard(user_id)

        await edit_message_text_safe(bot, call.message.chat.id, call.message.message_id,
                                loc.get_text('settings_title', lang_code),
                                reply_markup=new_markup, parse_mode='Markdown')
        await answer_callback_query(bot, call, text=loc.get_text('style_changed_notice', lang_code))

async def handle_language_selection_for_translation(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Обрабатывает выбор языка для перевода."""
    user_id = call.from_user.id
    target_lang_code = call.data[len(CALLBACK_LANG_PREFIX):]
    lang_name = TRANSLATE_LANGUAGES.get(target_lang_code, target_lang_code)

    user_states[user_id] = STATE_WAITING_FOR_TRANSLATE_TEXT
    user_states[f"{user_id}_target_lang"] = target_lang_code

    await answer_callback_query(bot, call, text=loc.get_text('language_selected_notice', lang_code).format(lang_name=lang_name))

    text = loc.get_text('send_text_to_translate_prompt', lang_code).format(lang_name=lang_name)
    await edit_message_text_safe(bot, call.message.chat.id, call.message.message_id,
                                 text, reply_markup=None, parse_mode='Markdown')

async def handle_calendar_date_selection(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Обрабатывает выбор даты в календаре для истории."""
    user_id = call.from_user.id
    selected_date_str = call.data[len(CALLBACK_CALENDAR_DATE_PREFIX):]

    if user_states.get(user_id) == STATE_WAITING_FOR_HISTORY_DATE:
        await answer_callback_query(bot, call)
        await edit_message_text_safe(bot, call.message.chat.id, call.message.message_id, 
                                     loc.get_text('history_loading', lang_code),
                                     reply_markup=None, parse_mode=None)

        selected_date = datetime.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        history = db_manager.get_conversation_history_by_date(user_id, selected_date)

        if history:
            history_text = f"📜 {loc.get_text('history_for_date', lang_code)} {selected_date.strftime('%d.%m.%Y')}:\n\n"
            for item in history:
                role = item.get('role', 'unknown')
                prefix = f"👤 *{loc.get_text('history_role_user', lang_code)}:*" if role == 'user' else f"🤖 *{loc.get_text('history_role_bot', lang_code)}:*"
                history_text += f"{prefix}\n{item.get('message_text', '')}\n\n"
            await send_long_message(bot, user_id, history_text, parse_mode='Markdown')
        else:
            await bot.send_message(user_id, loc.get_text('history_no_messages', lang_code))

        user_states.pop(user_id, None)

async def handle_calendar_month_navigation(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает навигацию по месяцам в календаре."""
    try:
        year, month = map(int, call.data[len(CALLBACK_CALENDAR_MONTH_PREFIX):].split('-'))
        new_markup = mk.create_calendar_keyboard(year, month)
        await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=new_markup)
    except Exception as e:
        logger.error(f"Ошибка навигации по календарю: {e}", extra={'user_id': str(call.from_user.id)})
    finally:
        await answer_callback_query(bot, call)

def register_callback_handlers(bot: AsyncTeleBot):
    """Регистрирует основной обработчик callback запросов."""
    bot.register_callback_query_handler(handle_callback_query, func=lambda call: True, pass_bot=True)
    logger.info("Обработчик callback query зарегистрирован.")
