# File: handlers/message_handlers.py
"""
Центральный модуль для обработки сообщений от пользователя.
Здесь реализована явная маршрутизация на основе состояний.
"""
import PIL.Image
from io import BytesIO
from typing import List, Union
from telebot.async_telebot import AsyncTeleBot
from telebot import types

from . import telegram_helpers as tg_helpers
from utils import markup_helpers as mk
from utils import localization as loc
from utils import text_helpers as th
from config.settings import (
   STATE_WAITING_FOR_TRANSLATE_TEXT, STATE_WAITING_FOR_API_KEY,
    STATE_WAITING_FOR_NEW_DIALOG_NAME, STATE_WAITING_FOR_RENAME_DIALOG,
    STATE_WAITING_FOR_FEEDBACK, DEFAULT_MODEL_ID, BOT_PERSONAS, ADMIN_USER_ID,
    STATE_ADMIN_WAITING_FOR_BROADCAST_MSG, STATE_ADMIN_WAITING_FOR_USER_ID_TO_MANAGE,
    STATE_ADMIN_WAITING_FOR_USER_ID_TO_REPLY, STATE_ADMIN_WAITING_FOR_REPLY_MESSAGE
)
from database import db_manager
from services import gemini_service
from services.gemini_service import GeminiAPIError
from .decorators import admin_required
from .admin_handlers import handle_admin_command

from logger_config import get_logger

logger = get_logger(__name__)
user_logger = get_logger('user_messages')

# ===================================================================================
# --- ВНУТРЕННИЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ЭТОГО МОДУЛЯ ---
# ===================================================================================

async def _check_access(bot: AsyncTeleBot, user_id: int, lang_code: str) -> bool:
    """
    Проверяет, имеет ли пользователь доступ к боту (не заблокирован ли, не включен ли режим обслуживания).
    """
    if await db_manager.is_user_blocked(user_id):
        await bot.send_message(user_id, loc.get_text('user_is_blocked', lang_code))
        return False

    maintenance_mode_str = await db_manager.get_app_setting('maintenance_mode')
    if maintenance_mode_str == 'true' and user_id != ADMIN_USER_ID:
        await bot.send_message(user_id, loc.get_text('maintenance_mode_on', lang_code))
        return False
    return True

async def _create_context_header(user_id: int, lang_code: str) -> str:
    """
    Создает текстовый заголовок с информацией о текущем контексте (диалог, персона, модель).
    """
    context_info = await db_manager.get_user_context_info(user_id)
    if not context_info:
        return ""
    dialog_name = context_info.get('dialog_name', '..._')
    persona_id = context_info.get('active_persona', 'default')
    model_name = context_info.get('gemini_model') or DEFAULT_MODEL_ID
    persona_info = BOT_PERSONAS.get(persona_id, BOT_PERSONAS['default'])
    persona_name = persona_info.get(f"name_{lang_code}", persona_info.get('name_ru', '...'))
    header = (
        f"•  **Диалог:** `{dialog_name}`\n"
        f"•  **Персона:** `{persona_name}`\n"
        f"•  **Модель:** `{model_name}`\n"
        f"---"
    )
    return header

# ===================================================================================
# --- ЛОГИКА ОБРАБОТКИ СООБЩЕНИЙ В ЗАВИСИМОСТИ ОТ СОСТОЯНИЯ (STATE) ---
# ===================================================================================

# --- Административные состояния ---

@admin_required
async def _handle_state_admin_broadcast(message: types.Message, bot: AsyncTeleBot):
    """Логика для состояния STATE_ADMIN_WAITING_FOR_BROADCAST_MSG."""
    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    await bot.add_data(user_id, user_id, broadcast_message=message.text)
    all_users = await db_manager.get_all_user_ids()
    count = len(all_users)
    confirmation_text = loc.get_text('admin.broadcast_confirm_prompt', lang_code).format(
        count=count, message_text=message.text
    )
    confirm_keyboard = mk.create_broadcast_confirmation_keyboard(lang_code)
    await bot.send_message(user_id, confirmation_text, reply_markup=confirm_keyboard)

@admin_required
async def _handle_state_admin_user_id_manage(message: types.Message, bot: AsyncTeleBot):
    """Логика для состояния STATE_ADMIN_WAITING_FOR_USER_ID_TO_MANAGE."""
    admin_id = message.from_user.id
    lang_code = await db_manager.get_user_language(admin_id)

    if not message.text.isdigit():
        await bot.reply_to(message, "Ошибка: User ID должен быть числом.")
        return

    user_id_to_manage = int(message.text)
    await bot.delete_state(admin_id, admin_id)

    user_info_text = await tg_helpers.get_user_info_text(user_id_to_manage, lang_code)

    user_info = await db_manager.get_user_info_for_admin(user_id_to_manage)
    if user_info:
        keyboard = mk.create_user_management_keyboard(user_id_to_manage, user_info['is_blocked'], lang_code)
    else:
        keyboard = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
            loc.get_text('admin.btn_back_to_admin_menu', lang_code),
            callback_data='admin_main_menu'
        ))

    await bot.send_message(admin_id, user_info_text, reply_markup=keyboard, parse_mode="Markdown")

@admin_required
async def _handle_state_user_id_for_reply(message: types.Message, bot: AsyncTeleBot):
    """
    Логика для состояния STATE_ADMIN_WAITING_FOR_USER_ID_TO_REPLY.
    Проверяет ID и запрашивает сообщение для отправки.
    """
    admin_id = message.from_user.id
    lang_code = await db_manager.get_user_language(admin_id)

    if not message.text.isdigit():
        await bot.reply_to(message, "Ошибка: User ID должен быть числом. Попробуйте еще раз или введите /cancel для отмены.")
        return

    target_user_id = int(message.text)
    
    # Проверяем, существует ли такой пользователь в базе
    user_info = await db_manager.get_user_info_for_admin(target_user_id)
    if not user_info:
        await bot.reply_to(message, loc.get_text('admin.user_not_found', lang_code).format(user_id=target_user_id))
        await bot.delete_state(admin_id, admin_id)
        await handle_admin_command(message, bot) # Возвращаем в главное меню админки
        return

    # Сохраняем ID в данные состояния и переходим к следующему шагу
    await bot.add_data(admin_id, admin_id, target_user_id=target_user_id)
    await bot.set_state(admin_id, STATE_ADMIN_WAITING_FOR_REPLY_MESSAGE, admin_id)

    # Запрашиваем текст сообщения
    await bot.send_message(admin_id, loc.get_text('admin.reply_prompt_message', lang_code).format(user_id=target_user_id))


@admin_required
async def _handle_state_message_to_user(message: types.Message, bot: AsyncTeleBot):
    """
    Логика для состояния STATE_ADMIN_WAITING_FOR_REPLY_MESSAGE.
    Отправляет полученное сообщение целевому пользователю.
    """
    admin_id = message.from_user.id
    lang_code = await db_manager.get_user_language(admin_id)
    text_to_send = message.text

    async with bot.retrieve_data(admin_id, admin_id) as data:
        target_user_id = data.get('target_user_id')

    if not target_user_id:
        logger.error(f"Не найден target_user_id в состоянии для админа {admin_id}")
        await bot.delete_state(admin_id, admin_id)
        await bot.send_message(admin_id, "Произошла внутренняя ошибка, не удалось найти ID получателя.")
        return

    # Получаем язык целевого пользователя для корректной локализации уведомления
    target_lang_code = await db_manager.get_user_language(target_user_id)
    notification_text = loc.get_text('admin.reply_admin_notification', target_lang_code).format(text=text_to_send)

    try:
        await bot.send_message(target_user_id, notification_text, parse_mode='Markdown')
        await bot.send_message(admin_id, loc.get_text('admin.reply_sent_success', lang_code).format(user_id=target_user_id))
        logger.info(f"Администратор {admin_id} отправил сообщение пользователю {target_user_id} через меню.")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения от админа {admin_id} пользователю {target_user_id}: {e}")
        await bot.send_message(admin_id, loc.get_text('admin.reply_sent_fail', lang_code))
    finally:
        # Завершаем процесс и выходим из состояния
        await bot.delete_state(admin_id, admin_id)

# --- Пользовательские состояния ---

async def _handle_state_api_key(message: types.Message, bot: AsyncTeleBot):
    """Логика для состояния STATE_WAITING_FOR_API_KEY."""
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

        # ---> НАЧАЛО ИСПРАВЛЕНИЯ <---
        # Сбрасываем кэш текущего диалога, чтобы убрать из него сообщения "установите ключ"
        active_dialog_id = await db_manager.get_active_dialog_id(user_id)
        if active_dialog_id:
            gemini_service.reset_dialog_chat(active_dialog_id)
        # ---> КОНЕЦ ИСПРАВЛЕНИЯ <---

        await bot.delete_state(message.from_user.id, message.chat.id)
        text = loc.get_text('api_key_success', lang_code)
        await bot.send_message(user_id, text, reply_markup=mk.create_main_keyboard(lang_code, user_id))
    else:
        text = loc.get_text('api_key_invalid', lang_code)
        await bot.send_message(user_id, text)

async def _handle_state_translate(message: types.Message, bot: AsyncTeleBot):
    """Логика для состояния STATE_WAITING_FOR_TRANSLATE_TEXT."""
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
    try:
        translated_text = await gemini_service.generate_content_simple(api_key, f"Translate to {target_lang_code}: '{text_to_translate}'")
        if translated_text:
            await bot.reply_to(message, translated_text)
    except GeminiAPIError as e:
        user_friendly_error = loc.get_text(e.error_key, lang_code)
        await bot.reply_to(message, user_friendly_error)
    finally:
        await bot.delete_state(user_id, message.chat.id)

async def _handle_state_new_dialog_name(message: types.Message, bot: AsyncTeleBot):
    """Логика для состояния STATE_WAITING_FOR_NEW_DIALOG_NAME."""
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

    dialog_keyboard = await mk.create_dialogs_menu_keyboard(user_id)
    await bot.send_message(
        user_id,
        f"{loc.get_text('dialogs_menu_title', lang_code)}\n\n{loc.get_text('dialogs_menu_desc', lang_code)}",
        reply_markup=dialog_keyboard
    )

async def _handle_state_rename_dialog(message: types.Message, bot: AsyncTeleBot):
    """Логика для состояния STATE_WAITING_FOR_RENAME_DIALOG."""
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
        await bot.send_message(user_id, loc.get_text('dialog_renamed_success', lang_code).format(new_name=new_name))

        dialog_keyboard = await mk.create_dialogs_menu_keyboard(user_id)
        await bot.send_message(
            user_id, f"{loc.get_text('dialogs_menu_title', lang_code)}\n\n{loc.get_text('dialogs_menu_desc', lang_code)}",
            reply_markup=dialog_keyboard
        )
    else:
        logger.error(f"Не найден dialog_id_to_rename в состоянии у {user_id}", extra={'user_id': str(user_id)})
        await bot.delete_state(user_id, message.chat.id)

async def _handle_state_feedback(message: types.Message, bot: AsyncTeleBot):
    """Логика для состояния STATE_WAITING_FOR_FEEDBACK."""
    user_id = message.chat.id
    lang_code = await db_manager.get_user_language(user_id)

    await bot.delete_state(user_id, message.chat.id)
    await bot.send_message(user_id, loc.get_text('feedback_sent', lang_code))

    if ADMIN_USER_ID:
        try:
            # Экранируем все пользовательские данные для безопасной вставки в MarkdownV2
            safe_username = th.escape_markdown(message.from_user.username or 'N/A')
            safe_first_name = th.escape_markdown(message.from_user.first_name or 'N/A')
            safe_text = th.escape_markdown(message.text)

            admin_notification = loc.get_text('feedback_admin_notification', 'ru').format(
                user_id=user_id,
                username=safe_username,
                first_name=safe_first_name,
                text=safe_text
            )
            await bot.send_message(ADMIN_USER_ID, admin_notification, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о фидбэке администратору: {e}", extra={'user_id': 'System'})

# ===================================================================================
# --- ОБЩИЙ ОБРАБОТЧИК ДЛЯ СООБЩЕНИЙ БЕЗ СОСТОЯНИЯ ---
# ===================================================================================

# handlers/message_handlers.py

# ...

async def _handle_no_state_message(message: types.Message, bot: AsyncTeleBot):
    """Обрабатывает текстовые сообщения и фото, когда пользователь не находится ни в каком состоянии."""
    user_id = message.from_user.id
    content_type = message.content_type
    lang_code = await db_manager.get_user_language(user_id)
    
    try:
        # --- Общая логика для текста и фото ---
        api_key_exists = await db_manager.get_user_api_key(user_id)
        if not api_key_exists:
            # Подбираем правильное сообщение об ошибке
            error_text_key = 'api_key_needed_for_chat' if content_type == 'text' else 'api_key_needed_for_vision'
            await bot.reply_to(message, loc.get_text(error_text_key, lang_code))
            return

        await tg_helpers.send_typing_action(bot, user_id)
        
        # Формируем промпт в зависимости от типа контента
        prompt: Union[str, List[Union[str, PIL.Image.Image]]]
        if content_type == 'text':
            prompt = message.text
        elif content_type == 'photo':
            file_info = await bot.get_file(message.photo[-1].file_id)
            downloaded_bytes = await bot.download_file(file_info.file_path)
            image = PIL.Image.open(BytesIO(downloaded_bytes))
            prompt_text = message.caption or "Опиши это изображение."
            prompt = [prompt_text, image]
        else:
            await bot.reply_to(message, loc.get_text('unsupported_content', lang_code))
            return
            
        # --- Получаем ответ и источники ---
        response_text, sources = await gemini_service.generate_response(user_id, prompt)
        
        header = await _create_context_header(user_id, lang_code)
        
        # --- Формируем финальное сообщение с источниками ---
        final_message = f"{header}\n\n{response_text}"
        if sources:
            sources_text = "\n\n---\n*Источники:*\n"
            for i, source in enumerate(sources, 1):
                # Экранируем title для Markdown
                safe_title = tg_helpers.th.escape_markdown(source['title'])
                sources_text += f"{i}. [{safe_title}]({source['uri']})\n"
            final_message += sources_text

            # ---> НАЧАЛО ДИАГНОСТИЧЕСКОГО КОДА <---
        # logger.info(f"Полный текст, ПЕРЕДАВАЕМЫЙ в send_long_message:\n---\n{final_message}\n---", extra={'user_id': str(user_id)})
        # ---> КОНЕЦ ДИАГНОСТИЧЕСКОГО КОДА <---
            
        await tg_helpers.send_long_message(bot, user_id, final_message, disable_web_page_preview=True)

    except GeminiAPIError as e:
        user_model = await db_manager.get_user_gemini_model(user_id) or DEFAULT_MODEL_ID
        user_friendly_error = loc.get_text(e.error_key, lang_code).format(model_name=user_model)
        error_markup = mk.create_error_report_button()
        await tg_helpers.send_long_message(bot, user_id, user_friendly_error, reply_markup=error_markup)
        
    except Exception as e:
        await tg_helpers.send_error_reply(bot, message, f"Критическая ошибка в _handle_no_state_message: {e}")
        await bot.delete_state(user_id, message.chat.id)

# ===================================================================================
# --- ГЛАВНЫЙ ЕДИНЫЙ ОБРАБОТЧИК И РЕГИСТРАЦИЯ ---
# ===================================================================================

async def universal_message_router(message: types.Message, bot: AsyncTeleBot):
    """
    Единый обработчик, который маршрутизирует все текстовые сообщения и фото.
    """
    user = message.from_user
    user_id = user.id

    # Обновляем базовую информацию о пользователе
    user_logger.info(f"Получено сообщение ({message.content_type}) от user ID: {user_id}", extra={'user_id': str(user_id)})
    await db_manager.add_or_update_user(user.id, user.username, user.first_name, user.last_name)
    
    # Проверка на блокировку и режим обслуживания
    lang_code = await db_manager.get_user_language(user_id)
    if not await _check_access(bot, user_id, lang_code):
        return

    # Получаем текущее состояние пользователя
    current_state = await bot.get_state(user_id, user_id)
    logger.debug(f"Router: User {user_id}, State: {current_state}, Content: {message.content_type}")

    # Явная маршрутизация на основе состояния
    if message.content_type == 'text':
        if current_state == STATE_ADMIN_WAITING_FOR_BROADCAST_MSG:
            await _handle_state_admin_broadcast(message, bot)
        elif current_state == STATE_ADMIN_WAITING_FOR_USER_ID_TO_MANAGE:
            await _handle_state_admin_user_id_manage(message, bot)
        elif current_state == STATE_ADMIN_WAITING_FOR_USER_ID_TO_REPLY:
            await _handle_state_user_id_for_reply(message, bot)
        elif current_state == STATE_ADMIN_WAITING_FOR_REPLY_MESSAGE:
            await _handle_state_message_to_user(message, bot)
        elif current_state == STATE_WAITING_FOR_API_KEY:
            await _handle_state_api_key(message, bot)
        elif current_state == STATE_WAITING_FOR_TRANSLATE_TEXT:
            await _handle_state_translate(message, bot)
        elif current_state == STATE_WAITING_FOR_NEW_DIALOG_NAME:
            await _handle_state_new_dialog_name(message, bot)
        elif current_state == STATE_WAITING_FOR_RENAME_DIALOG:
            await _handle_state_rename_dialog(message, bot)
        elif current_state == STATE_WAITING_FOR_FEEDBACK:
            await _handle_state_feedback(message, bot)
        else: # state is None
            await _handle_no_state_message(message, bot)
    elif message.content_type == 'photo':
        if current_state is None:
            await _handle_no_state_message(message, bot)
        else:
            await bot.reply_to(message, loc.get_text('state_wrong_content_type', lang_code))
    else: # другие типы контента
        # Если пользователь не в состоянии ввода текста, то игнорируем прочий контент
        if current_state is None:
             await bot.reply_to(message, loc.get_text('unsupported_content', lang_code))
        else: # Если в состоянии ожидания текста, а прислал что-то другое
             await bot.reply_to(message, loc.get_text('state_wrong_content_type', lang_code))


def register_message_handlers(bot: AsyncTeleBot):
    """
    Регистрирует единственный универсальный обработчик для всех сообщений.
    """
    # Этот обработчик теперь должен ловить все типы контента, которые мы хотим игнорировать или обрабатывать
    bot.register_message_handler(
        universal_message_router,
        content_types=['text', 'photo', 'document', 'audio', 'video', 'sticker', 'voice', 'location', 'contact'],
        pass_bot=True
    )
    logger.info("Универсальный обработчик сообщений зарегистрирован.")