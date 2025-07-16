# File: handlers/callback_handlers.py
import datetime
from telebot.async_telebot import AsyncTeleBot
from telebot import types

from config.settings import (
    BOT_STYLES, TRANSLATE_LANGUAGES, CALLBACK_SETTINGS_BACK_TO_MAIN,
    CALLBACK_LANG_PREFIX, STATE_WAITING_FOR_TRANSLATE_TEXT,
    CALLBACK_CALENDAR_DATE_PREFIX, CALLBACK_CALENDAR_MONTH_PREFIX, STATE_WAITING_FOR_HISTORY_DATE,
    CALLBACK_SETTINGS_STYLE_PREFIX, CALLBACK_SETTINGS_LANG_PREFIX, CALLBACK_SETTINGS_SET_API_KEY,
    CALLBACK_SETTINGS_CHOOSE_MODEL_MENU, CALLBACK_SETTINGS_MODEL_PREFIX,
    CALLBACK_IGNORE, STATE_WAITING_FOR_API_KEY,
    CALLBACK_SETTINGS_PERSONA_MENU, CALLBACK_SETTINGS_PERSONA_PREFIX, BOT_PERSONAS # <-- Импорты для персон
)
from database import db_manager
from services import gemini_service
from services.gemini_service import GeminiAPIError 
from utils import markup_helpers as mk
from utils import localization as loc
from . import telegram_helpers as tg_helpers

from logger_config import get_logger

logger = get_logger(__name__)


# --- Основной обработчик ---

async def handle_callback_query(call: types.CallbackQuery, bot: AsyncTeleBot):
    """Обрабатывает все callback запросы."""
    user_id = call.from_user.id
    data = call.data
    message = call.message

    if not message:
        await tg_helpers.answer_callback_query(bot, call)
        return

    db_manager.add_or_update_user(user_id)
    lang_code = db_manager.get_user_language(user_id)

    try:
        if data == CALLBACK_IGNORE:
            await tg_helpers.answer_callback_query(bot, call)
        elif data.startswith(CALLBACK_LANG_PREFIX):
            await handle_language_selection_for_translation(bot, call, lang_code)
        elif data.startswith(CALLBACK_SETTINGS_STYLE_PREFIX):
            await handle_style_setting(bot, call, lang_code)
        elif data.startswith(CALLBACK_SETTINGS_LANG_PREFIX):
            await handle_language_setting(bot, call)
        elif data == CALLBACK_SETTINGS_SET_API_KEY:
            await handle_set_api_key_from_settings(bot, call, lang_code)
        # НОВЫЕ УСЛОВИЯ ДЛЯ ПЕРСОН
        elif data == CALLBACK_SETTINGS_PERSONA_MENU:
            await handle_persona_menu(bot, call, lang_code)
        elif data.startswith(CALLBACK_SETTINGS_PERSONA_PREFIX):
            await handle_persona_selection(bot, call, lang_code)
        elif data == CALLBACK_SETTINGS_CHOOSE_MODEL_MENU:
            await handle_choose_model_menu(bot, call, lang_code)
        elif data.startswith(CALLBACK_SETTINGS_MODEL_PREFIX):
            await handle_model_selection(bot, call, lang_code)
        elif data == CALLBACK_SETTINGS_BACK_TO_MAIN:
            await handle_back_to_main_settings(bot, call, lang_code)
        elif data.startswith(CALLBACK_CALENDAR_DATE_PREFIX):
            await handle_calendar_date_selection(bot, call, lang_code)
        elif data.startswith(CALLBACK_CALENDAR_MONTH_PREFIX):
            await handle_calendar_month_navigation(bot, call)
        else:
            await tg_helpers.answer_callback_query(bot, call, text="Unknown action", show_alert=True)
    except GeminiAPIError as e:
        user_friendly_error = loc.get_text(e.error_key, lang_code)
        await tg_helpers.answer_callback_query(bot, call, text=user_friendly_error, show_alert=True)
        await handle_back_to_main_settings(bot, call, lang_code)
    except Exception as e:
        logger.exception(f"Критическая ошибка обработки callback query: {e}", extra={'user_id': str(user_id)})
        await tg_helpers.answer_callback_query(bot, call, text="An internal error occurred.", show_alert=True)


# --- Обработчики конкретных колбэков ---

async def handle_back_to_main_settings(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Возвращает пользователя в главное меню настроек."""
    user_id = call.from_user.id
    settings_markup = mk.create_settings_keyboard(user_id)
    await tg_helpers.edit_message_text_safe(
        bot,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=loc.get_text('settings_title', lang_code),
        reply_markup=settings_markup
    )
    await tg_helpers.answer_callback_query(bot, call)

async def handle_set_api_key_from_settings(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Обрабатывает нажатие на кнопку установки API-ключа в настройках."""
    await bot.set_state(call.from_user.id, STATE_WAITING_FOR_API_KEY, call.message.chat.id)
    await tg_helpers.answer_callback_query(bot, call)
    await tg_helpers.edit_message_text_safe(
        bot,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=loc.get_text('set_api_key_prompt', lang_code),
        reply_markup=None
    )

async def handle_language_setting(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает смену языка интерфейса."""
    user_id = call.from_user.id
    new_lang_code = call.data[len(CALLBACK_SETTINGS_LANG_PREFIX):]
    db_manager.set_user_language(user_id, new_lang_code)
    new_markup = mk.create_settings_keyboard(user_id)
    await tg_helpers.edit_message_text_safe(
        bot, call.message.chat.id, call.message.message_id,
        loc.get_text('settings_title', new_lang_code),
        reply_markup=new_markup
    )
    await tg_helpers.answer_callback_query(bot, call, text=f"Language set to {'English' if new_lang_code == 'en' else 'Русский'}")

async def handle_style_setting(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Обрабатывает выбор стиля общения бота."""
    user_id = call.from_user.id
    style_code = call.data[len(CALLBACK_SETTINGS_STYLE_PREFIX):]
    if style_code in BOT_STYLES:
        db_manager.set_user_bot_style(user_id, style_code)
        gemini_service.reset_user_chat(user_id)
        new_markup = mk.create_settings_keyboard(user_id)
        await tg_helpers.edit_message_text_safe(
            bot, call.message.chat.id, call.message.message_id,
            loc.get_text('settings_title', lang_code),
            reply_markup=new_markup
        )
        await tg_helpers.answer_callback_query(bot, call, text=loc.get_text('style_changed_notice', lang_code))

# --- НОВЫЕ ОБРАБОТЧИКИ ДЛЯ ВЫБОРА ПЕРСОНЫ ---

async def handle_persona_menu(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Отображает меню выбора персоны."""
    user_id = call.from_user.id
    keyboard = mk.create_persona_selection_keyboard(user_id)
    text = (f"{loc.get_text('persona_selection_title', lang_code)}\n\n"
            f"{loc.get_text('persona_selection_desc', lang_code)}")
    await tg_helpers.edit_message_text_safe(
        bot, call.message.chat.id, call.message.message_id,
        text=text,
        reply_markup=keyboard
    )
    await tg_helpers.answer_callback_query(bot, call)

async def handle_persona_selection(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Обрабатывает выбор конкретной персоны."""
    user_id = call.from_user.id
    persona_id = call.data[len(CALLBACK_SETTINGS_PERSONA_PREFIX):]

    if persona_id in BOT_PERSONAS:
        db_manager.set_user_persona(user_id, persona_id)
        gemini_service.reset_user_chat(user_id)

        # Получаем имя персоны на языке пользователя для уведомления
        persona_info = BOT_PERSONAS[persona_id]
        persona_name = persona_info.get(f"name_{lang_code}", persona_info['name_ru'])

        # Возвращаемся в главное меню настроек
        await handle_back_to_main_settings(bot, call, lang_code)

        await tg_helpers.answer_callback_query(
            bot, call,
            text=loc.get_text('persona_changed_notice', lang_code).format(persona_name=persona_name)
        )

# --- Обработчики выбора модели ---

async def handle_choose_model_menu(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Отображает меню выбора модели."""
    user_id = call.from_user.id
    api_key = db_manager.get_user_api_key(user_id)

    if not api_key:
        await tg_helpers.answer_callback_query(bot, call, text=loc.get_text('api_key_needed_for_feature', lang_code), show_alert=True)
        return

    await tg_helpers.edit_message_text_safe(
        bot, call.message.chat.id, call.message.message_id,
        text=loc.get_text('model_selection_loading', lang_code),
        reply_markup=None
    )

    models = await gemini_service.get_available_models(api_key)
    if not models:
        await tg_helpers.edit_message_text_safe(
            bot, call.message.chat.id, call.message.message_id,
            text=loc.get_text('model_selection_error', lang_code)
        )
        await handle_back_to_main_settings(bot, call, lang_code)
        return

    current_model = db_manager.get_user_gemini_model(user_id)
    keyboard = mk.create_model_selection_keyboard(models, current_model, lang_code)

    await tg_helpers.edit_message_text_safe(
        bot, call.message.chat.id, call.message.message_id,
        text=loc.get_text('model_selection_title', lang_code),
        reply_markup=keyboard
    )

async def handle_model_selection(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Обрабатывает выбор конкретной модели."""
    user_id = call.from_user.id
    model_name = call.data[len(CALLBACK_SETTINGS_MODEL_PREFIX):]

    db_manager.set_user_gemini_model(user_id, model_name)
    gemini_service.reset_user_chat(user_id)

    await handle_back_to_main_settings(bot, call, lang_code)

    await tg_helpers.answer_callback_query(
        bot, call,
        text=loc.get_text('model_changed_notice', lang_code).format(model_name=model_name)
    )

# --- Прочие обработчики ---

async def handle_language_selection_for_translation(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Обрабатывает выбор языка для перевода."""
    user_id = call.from_user.id
    target_lang_code = call.data[len(CALLBACK_LANG_PREFIX):]
    lang_name = TRANSLATE_LANGUAGES.get(target_lang_code, target_lang_code)

    await bot.set_state(user_id, STATE_WAITING_FOR_TRANSLATE_TEXT, call.message.chat.id)
    await bot.add_data(user_id, call.message.chat.id, target_lang=target_lang_code)

    await tg_helpers.answer_callback_query(bot, call, text=loc.get_text('language_selected_notice', lang_code).format(lang_name=lang_name))

    text = loc.get_text('send_text_to_translate_prompt', lang_code).format(lang_name=lang_name)
    await tg_helpers.edit_message_text_safe(
        bot, call.message.chat.id, call.message.message_id,
        text, reply_markup=None
    )

async def handle_calendar_date_selection(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Обрабатывает выбор даты в календаре для истории."""
    user_id = call.from_user.id
    selected_date_str = call.data[len(CALLBACK_CALENDAR_DATE_PREFIX):]

    current_state = await bot.get_state(user_id, call.message.chat.id)

    if current_state == STATE_WAITING_FOR_HISTORY_DATE:
        await tg_helpers.answer_callback_query(bot, call)
        await tg_helpers.edit_message_text_safe(
            bot, call.message.chat.id, call.message.message_id,
            loc.get_text('history_loading', lang_code),
            reply_markup=None
        )

        try:
            selected_date = datetime.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            history = db_manager.get_conversation_history_by_date(user_id, selected_date)

            if history:
                history_text = f"📜 {loc.get_text('history_for_date', lang_code)} {selected_date.strftime('%d.%m.%Y')}:\n\n"
                for item in history:
                    role = item.get('role', 'unknown')
                    prefix = f"👤 *{loc.get_text('history_role_user', lang_code)}:*" if role == 'user' else f"🤖 *{loc.get_text('history_role_bot', lang_code)}:*"
                    history_text += f"{prefix}\n{item.get('message_text', '')}\n\n"

                await tg_helpers.send_long_message(bot, user_id, history_text)
            else:
                await bot.send_message(user_id, loc.get_text('history_no_messages', lang_code))

            await bot.delete_state(user_id, call.message.chat.id)

        except (ValueError, TypeError) as e:
            logger.error(f"Ошибка при обработке даты истории '{selected_date_str}' для user_id {user_id}: {e}", extra={'user_id': str(user_id)})
            await bot.send_message(user_id, loc.get_text('history_date_error', lang_code))
            await bot.delete_state(user_id, call.message.chat.id)


async def handle_calendar_month_navigation(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает навигацию по месяцам в календаре."""
    try:
        year, month = map(int, call.data[len(CALLBACK_CALENDAR_MONTH_PREFIX):].split('-'))
        new_markup = mk.create_calendar_keyboard(year, month)
        await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=new_markup)
    except Exception as e:
        logger.error(f"Ошибка навигации по календарю: {e}", extra={'user_id': str(call.from_user.id)})
    finally:
        await tg_helpers.answer_callback_query(bot, call)


def register_callback_handlers(bot: AsyncTeleBot):
    """Регистрирует основной обработчик callback запросов."""
    bot.register_callback_query_handler(handle_callback_query, func=lambda call: True, pass_bot=True)
    logger.info("Обработчик callback query зарегистрирован.")
