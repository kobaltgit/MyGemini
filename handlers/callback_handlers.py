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
    CALLBACK_SETTINGS_PERSONA_MENU, CALLBACK_SETTINGS_PERSONA_PREFIX, BOT_PERSONAS,
    # Импорты для диалогов
    CALLBACK_DIALOGS_MENU, CALLBACK_DIALOG_SWITCH_PREFIX, CALLBACK_DIALOG_RENAME_PREFIX,
    CALLBACK_DIALOG_DELETE_PREFIX, CALLBACK_DIALOG_CREATE, CALLBACK_DIALOG_CONFIRM_DELETE_PREFIX,
    STATE_WAITING_FOR_NEW_DIALOG_NAME, STATE_WAITING_FOR_RENAME_DIALOG
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

    await db_manager.add_or_update_user(user_id)
    lang_code = await db_manager.get_user_language(user_id)

    # Маршрутизатор колбэков
    try:
        if data == CALLBACK_IGNORE:
            await tg_helpers.answer_callback_query(bot, call)
        # --- Настройки ---
        elif data.startswith(CALLBACK_SETTINGS_STYLE_PREFIX):
            await handle_style_setting(bot, call, lang_code)
        elif data.startswith(CALLBACK_SETTINGS_LANG_PREFIX):
            await handle_language_setting(bot, call)
        elif data == CALLBACK_SETTINGS_SET_API_KEY:
            await handle_set_api_key_from_settings(bot, call, lang_code)
        elif data == CALLBACK_SETTINGS_CHOOSE_MODEL_MENU:
            await handle_choose_model_menu(bot, call, lang_code)
        elif data.startswith(CALLBACK_SETTINGS_MODEL_PREFIX):
            await handle_model_selection(bot, call, lang_code)
        elif data == CALLBACK_SETTINGS_PERSONA_MENU:
            await handle_persona_menu(bot, call, lang_code)
        elif data.startswith(CALLBACK_SETTINGS_PERSONA_PREFIX):
            await handle_persona_selection(bot, call, lang_code)
        elif data == CALLBACK_SETTINGS_BACK_TO_MAIN:
            await handle_back_to_main_settings(bot, call, lang_code)
        # --- Диалоги ---
        elif data == CALLBACK_DIALOGS_MENU:
            await handle_dialogs_menu(bot, call, lang_code)
        elif data == CALLBACK_DIALOG_CREATE:
            await handle_create_dialog_start(bot, call, lang_code)
        elif data.startswith(CALLBACK_DIALOG_SWITCH_PREFIX):
            await handle_switch_dialog(bot, call, lang_code)
        elif data.startswith(CALLBACK_DIALOG_RENAME_PREFIX):
            await handle_rename_dialog_start(bot, call, lang_code)
        elif data.startswith(CALLBACK_DIALOG_DELETE_PREFIX):
            await handle_delete_dialog_start(bot, call, lang_code)
        elif data.startswith(CALLBACK_DIALOG_CONFIRM_DELETE_PREFIX):
            await handle_delete_dialog_confirm(bot, call, lang_code)
        # --- Прочее ---
        elif data.startswith(CALLBACK_LANG_PREFIX):
            await handle_language_selection_for_translation(bot, call, lang_code)
        elif data.startswith(CALLBACK_CALENDAR_DATE_PREFIX):
            await handle_calendar_date_selection(bot, call, lang_code)
        elif data.startswith(CALLBACK_CALENDAR_MONTH_PREFIX):
            await handle_calendar_month_navigation(bot, call)
        else:
            await tg_helpers.answer_callback_query(bot, call, text="Unknown action", show_alert=True)
    except GeminiAPIError as e:
        user_friendly_error = loc.get_text(e.error_key, lang_code)
        await tg_helpers.answer_callback_query(bot, call, text=user_friendly_error, show_alert=True)
    except Exception as e:
        logger.exception(f"Критическая ошибка обработки callback query: {e}", extra={'user_id': str(user_id)})
        await tg_helpers.answer_callback_query(bot, call, text="An internal error occurred.", show_alert=True)


# --- НОВЫЕ ОБРАБОТЧИКИ ДИАЛОГОВ ---

async def handle_dialogs_menu(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Отображает меню управления диалогами."""
    text = f"{loc.get_text('dialogs_menu_title', lang_code)}\n\n" \
           f"{loc.get_text('dialogs_menu_desc', lang_code)}"
    
    dialogs_keyboard = await mk.create_dialogs_menu_keyboard(call.from_user.id)
    await tg_helpers.edit_message_text_safe(
        bot,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        reply_markup=dialogs_keyboard
    )
    await tg_helpers.answer_callback_query(bot, call)

async def handle_create_dialog_start(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Начинает процесс создания нового диалога."""
    await bot.set_state(call.from_user.id, STATE_WAITING_FOR_NEW_DIALOG_NAME, call.message.chat.id)
    await tg_helpers.edit_message_text_safe(
        bot, call.message.chat.id, call.message.message_id,
        text=loc.get_text('dialog_enter_new_name_prompt', lang_code)
    )
    await tg_helpers.answer_callback_query(bot, call)

async def handle_switch_dialog(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Переключает активный диалог."""
    dialog_id_to_switch = int(call.data[len(CALLBACK_DIALOG_SWITCH_PREFIX):])
    await db_manager.set_active_dialog(call.from_user.id, dialog_id_to_switch)

    dialogs = await db_manager.get_user_dialogs(call.from_user.id)
    switched_dialog_name = next((d['name'] for d in dialogs if d['dialog_id'] == dialog_id_to_switch), '???')

    await handle_dialogs_menu(bot, call, lang_code) # Обновляем меню
    await tg_helpers.answer_callback_query(bot, call, text=loc.get_text('dialog_switched_success', lang_code).format(name=switched_dialog_name))

async def handle_rename_dialog_start(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Начинает процесс переименования диалога."""
    dialog_id_to_rename = int(call.data[len(CALLBACK_DIALOG_RENAME_PREFIX):])
    dialogs = await db_manager.get_user_dialogs(call.from_user.id)
    dialog_name = next((d['name'] for d in dialogs if d['dialog_id'] == dialog_id_to_rename), '???')

    await bot.set_state(call.from_user.id, STATE_WAITING_FOR_RENAME_DIALOG, call.message.chat.id)
    await bot.add_data(call.from_user.id, call.message.chat.id, dialog_id_to_rename=dialog_id_to_rename)

    await tg_helpers.edit_message_text_safe(
        bot, call.message.chat.id, call.message.message_id,
        text=loc.get_text('dialog_enter_rename_prompt', lang_code).format(name=dialog_name)
    )
    await tg_helpers.answer_callback_query(bot, call)

async def handle_delete_dialog_start(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Показывает подтверждение на удаление диалога."""
    user_id = call.from_user.id
    dialog_id_to_delete = int(call.data[len(CALLBACK_DIALOG_DELETE_PREFIX):])
    
    dialogs = await db_manager.get_user_dialogs(user_id)
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)

    if dialog_id_to_delete == active_dialog_id:
        await tg_helpers.answer_callback_query(bot, call, text=loc.get_text('dialog_error_delete_active', lang_code), show_alert=True)
        return

    if len(dialogs) <= 1:
        # Эта проверка на случай, если что-то пошло не так, т.к. активный диалог уже не должен был дать сюда попасть.
        await tg_helpers.answer_callback_query(bot, call, text="Нельзя удалить последний диалог.", show_alert=True)
        return

    dialog_name = next((d['name'] for d in dialogs if d['dialog_id'] == dialog_id_to_delete), '???')

    await tg_helpers.edit_message_text_safe(
        bot, call.message.chat.id, call.message.message_id,
        text=loc.get_text('dialog_delete_confirmation', lang_code).format(name=dialog_name),
        reply_markup=mk.create_confirm_delete_keyboard(dialog_id_to_delete, lang_code)
    )
    await tg_helpers.answer_callback_query(bot, call)

async def handle_delete_dialog_confirm(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Окончательно удаляет диалог."""
    user_id = call.from_user.id
    dialog_id_to_delete = int(call.data[len(CALLBACK_DIALOG_CONFIRM_DELETE_PREFIX):])

    # Удаляем сам диалог
    deleted_dialog_name = await db_manager.delete_dialog(user_id, dialog_id_to_delete)
    if not deleted_dialog_name:
        await tg_helpers.answer_callback_query(bot, call, text="Ошибка при удалении диалога.", show_alert=True)
        return

    # После удаления проверяем, что осталось.
    remaining_dialogs = await db_manager.get_user_dialogs(user_id)
    if not remaining_dialogs:
        # Такого быть не должно из-за проверок выше, но это страховка
        new_dialog_name = "Основной диалог" if lang_code == 'ru' else "General Chat"
        await db_manager.create_dialog(user_id, new_dialog_name, set_active=True)
        await tg_helpers.answer_callback_query(bot, call, text=loc.get_text('dialog_deleted_last_success', lang_code).format(name=deleted_dialog_name))
    else:
         await tg_helpers.answer_callback_query(bot, call, text=loc.get_text('dialog_deleted_success', lang_code).format(name=deleted_dialog_name))

    # В любом случае обновляем меню, чтобы показать актуальный список
    await handle_dialogs_menu(bot, call, lang_code)

# --- Обработчики настроек ---

async def handle_back_to_main_settings(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    """Возвращает пользователя в главное меню настроек."""
    user_id = call.from_user.id
    settings_keyboard = await mk.create_settings_keyboard(user_id)
    await tg_helpers.edit_message_text_safe(
        bot,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=loc.get_text('settings_title', lang_code),
        reply_markup=settings_keyboard
    )
    await tg_helpers.answer_callback_query(bot, call)

async def handle_set_api_key_from_settings(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    await bot.set_state(call.from_user.id, STATE_WAITING_FOR_API_KEY, call.message.chat.id)
    await tg_helpers.answer_callback_query(bot, call)
    await tg_helpers.edit_message_text_safe(
        bot, chat_id=call.message.chat.id, message_id=call.message.message_id,
        text=loc.get_text('set_api_key_prompt', lang_code), reply_markup=None
    )

async def handle_language_setting(bot: AsyncTeleBot, call: types.CallbackQuery):
    user_id = call.from_user.id
    new_lang_code = call.data[len(CALLBACK_SETTINGS_LANG_PREFIX):]
    await db_manager.set_user_language(user_id, new_lang_code)
    await handle_back_to_main_settings(bot, call, new_lang_code)
    await tg_helpers.answer_callback_query(bot, call, text=f"Language set to {'English' if new_lang_code == 'en' else 'Русский'}")

async def handle_style_setting(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    user_id = call.from_user.id
    style_code = call.data[len(CALLBACK_SETTINGS_STYLE_PREFIX):]
    if style_code in BOT_STYLES:
        await db_manager.set_user_bot_style(user_id, style_code)
        active_dialog_id = await db_manager.get_active_dialog_id(user_id)
        if active_dialog_id:
            gemini_service.reset_dialog_chat(active_dialog_id)
        await handle_back_to_main_settings(bot, call, lang_code)
        await tg_helpers.answer_callback_query(bot, call, text=loc.get_text('style_changed_notice', lang_code))

async def handle_persona_menu(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    user_id = call.from_user.id
    text = (f"{loc.get_text('persona_selection_title', lang_code)}\n\n"
            f"{loc.get_text('persona_selection_desc', lang_code)}")
    persona_keyboard = await mk.create_persona_selection_keyboard(user_id)
    await tg_helpers.edit_message_text_safe(
        bot, call.message.chat.id, call.message.message_id,
        text=text, reply_markup=persona_keyboard
    )
    await tg_helpers.answer_callback_query(bot, call)

async def handle_persona_selection(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    user_id = call.from_user.id
    persona_id = call.data[len(CALLBACK_SETTINGS_PERSONA_PREFIX):]
    if persona_id in BOT_PERSONAS:
        await db_manager.set_user_persona(user_id, persona_id)
        active_dialog_id = await db_manager.get_active_dialog_id(user_id)
        if active_dialog_id:
            gemini_service.reset_dialog_chat(active_dialog_id)

        persona_info = BOT_PERSONAS[persona_id]
        persona_name = persona_info.get(f"name_{lang_code}", persona_info['name_ru'])

        await handle_back_to_main_settings(bot, call, lang_code)
        await tg_helpers.answer_callback_query(
            bot, call, text=loc.get_text('persona_changed_notice', lang_code).format(persona_name=persona_name)
        )

async def handle_choose_model_menu(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    user_id = call.from_user.id
    api_key = await db_manager.get_user_api_key(user_id)
    if not api_key:
        await tg_helpers.answer_callback_query(bot, call, text=loc.get_text('api_key_needed_for_feature', lang_code), show_alert=True)
        return
    await tg_helpers.edit_message_text_safe(
        bot, call.message.chat.id, call.message.message_id,
        text=loc.get_text('model_selection_loading', lang_code), reply_markup=None
    )
    models = await gemini_service.get_available_models(api_key)
    if not models:
        await tg_helpers.edit_message_text_safe(
            bot, call.message.chat.id, call.message.message_id,
            text=loc.get_text('model_selection_error', lang_code)
        )
        await handle_back_to_main_settings(bot, call, lang_code)
        return
    current_model = await db_manager.get_user_gemini_model(user_id)
    keyboard = mk.create_model_selection_keyboard(models, current_model, lang_code)
    await tg_helpers.edit_message_text_safe(
        bot, call.message.chat.id, call.message.message_id,
        text=loc.get_text('model_selection_title', lang_code), reply_markup=keyboard
    )

async def handle_model_selection(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    user_id = call.from_user.id
    model_name = call.data[len(CALLBACK_SETTINGS_MODEL_PREFIX):]
    await db_manager.set_user_gemini_model(user_id, model_name)
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)
    if active_dialog_id:
        gemini_service.reset_dialog_chat(active_dialog_id)
    await handle_back_to_main_settings(bot, call, lang_code)
    await tg_helpers.answer_callback_query(
        bot, call, text=loc.get_text('model_changed_notice', lang_code).format(model_name=model_name)
    )

# --- Прочие обработчики ---

async def handle_language_selection_for_translation(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    user_id = call.from_user.id
    target_lang_code = call.data[len(CALLBACK_LANG_PREFIX):]
    lang_name = TRANSLATE_LANGUAGES.get(target_lang_code, target_lang_code)
    await bot.set_state(user_id, STATE_WAITING_FOR_TRANSLATE_TEXT, call.message.chat.id)
    await bot.add_data(user_id, call.message.chat.id, target_lang=target_lang_code)
    await tg_helpers.answer_callback_query(bot, call, text=loc.get_text('language_selected_notice', lang_code).format(lang_name=lang_name))
    text = loc.get_text('send_text_to_translate_prompt', lang_code).format(lang_name=lang_name)
    await tg_helpers.edit_message_text_safe(
        bot, call.message.chat.id, call.message.message_id, text, reply_markup=None
    )

async def handle_calendar_date_selection(bot: AsyncTeleBot, call: types.CallbackQuery, lang_code: str):
    user_id = call.from_user.id
    selected_date_str = call.data[len(CALLBACK_CALENDAR_DATE_PREFIX):]
    current_state = await bot.get_state(user_id, call.message.chat.id)
    if current_state == STATE_WAITING_FOR_HISTORY_DATE:
        await tg_helpers.answer_callback_query(bot, call)
        await tg_helpers.edit_message_text_safe(
            bot, call.message.chat.id, call.message.message_id,
            loc.get_text('history_loading', lang_code), reply_markup=None
        )
        try:
            selected_date = datetime.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            # ИЗМЕНЕНО: получаем историю для активного диалога
            active_dialog_id = await db_manager.get_active_dialog_id(user_id)
            if active_dialog_id:
                history = await db_manager.get_conversation_history_by_date(active_dialog_id, selected_date)
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
            logger.error(f"Ошибка при обработке даты истории '{selected_date_str}': {e}", extra={'user_id': str(user_id)})
            await bot.send_message(user_id, loc.get_text('history_date_error', lang_code))
            await bot.delete_state(user_id, call.message.chat.id)

async def handle_calendar_month_navigation(bot: AsyncTeleBot, call: types.CallbackQuery):
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