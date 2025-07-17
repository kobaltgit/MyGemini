# File: handlers/admin_handlers.py
"""
Обработчики для админ-панели. Доступ к этим функциям строго ограничен
переменной ADMIN_USER_ID из файла настроек.
"""
import asyncio
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from telebot.apihelper import ApiException
from functools import wraps

from config.settings import ADMIN_USER_ID, CALLBACK_ADMIN_MAIN_MENU, CALLBACK_ADMIN_TOGGLE_MAINTENANCE, \
    CALLBACK_ADMIN_MAINTENANCE_MENU, CALLBACK_ADMIN_COMMUNICATION_MENU, \
    CALLBACK_ADMIN_BROADCAST, STATE_ADMIN_WAITING_FOR_BROADCAST_MSG, \
    CALLBACK_ADMIN_CONFIRM_BROADCAST, CALLBACK_ADMIN_CANCEL_BROADCAST
from utils import markup_helpers as mk
from utils import localization as loc
from . import telegram_helpers as tg_helpers
from database import db_manager
from logger_config import get_logger

logger = get_logger(__name__)

# --- Декоратор для проверки прав администратора ---

def admin_required(func):
    """
    Декоратор, который проверяет, является ли пользователь администратором.
    Работает как для обработчиков сообщений, так и для callback-запросов.
    """
    @wraps(func)
    async def wrapper(message_or_call, *args, **kwargs):
        user_id = message_or_call.from_user.id
        if user_id != ADMIN_USER_ID:
            lang_code = await db_manager.get_user_language(user_id)
            error_text = loc.get_text('admin.not_admin', lang_code)
            
            bot = args[0] if args and isinstance(args[0], AsyncTeleBot) else kwargs.get('bot')
            if not bot:
                 # Попытка найти бота в другом месте, если он не передан как второй аргумент
                 if isinstance(message_or_call, types.CallbackQuery):
                     bot = message_or_call.bot
                 elif isinstance(message_or_call, types.Message):
                     # Это маловероятно, но на всякий случай
                     logger.error("Не удалось найти экземпляр бота для ответа на не-админ команду.")
                     return
            
            if isinstance(message_or_call, types.Message):
                if bot: await bot.reply_to(message_or_call, error_text)
            elif isinstance(message_or_call, types.CallbackQuery):
                if bot: await bot.answer_callback_query(message_or_call.id, text=error_text, show_alert=True)
            
            logger.warning(f"Попытка несанкционированного доступа к админ-команде от user_id: {user_id}")
            return
        return await func(message_or_call, *args, **kwargs)
    return wrapper

# --- Обработчики команд и кнопок ---

@admin_required
async def handle_admin_command(message: types.Message, bot: AsyncTeleBot):
    """
    Обрабатывает команду /admin и нажатие на кнопку 'Админ-панель'.
    """
    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    
    admin_keyboard = await mk.create_admin_main_menu_keyboard(lang_code)
    await bot.send_message(
        user_id,
        text=loc.get_text('admin.panel_title', lang_code),
        reply_markup=admin_keyboard
    )

@admin_required
async def handle_cancel_state(message: types.Message, bot: AsyncTeleBot):
    """
    Отменяет текущее состояние админа (например, рассылку).
    """
    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    await bot.delete_state(user_id, user_id)
    await bot.send_message(user_id, loc.get_text('admin.broadcast_cancelled', lang_code))
    await handle_admin_command(message, bot) # Возвращаем в главное меню

@admin_required
async def handle_reply_command(message: types.Message, bot: AsyncTeleBot):
    """
    Обрабатывает команду /reply <user_id> <text> для ответа пользователю.
    """
    admin_id = message.from_user.id
    lang_code = await db_manager.get_user_language(admin_id)
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await bot.reply_to(message, "Использование: `/reply <user_id> <текст сообщения>`")
        return

    target_user_id_str, text_to_send = parts[1], parts[2]

    if not target_user_id_str.isdigit():
        await bot.reply_to(message, f"Ошибка: User ID '{target_user_id_str}' должен быть числом.")
        return
        
    target_user_id = int(target_user_id_str)
    
    # Получаем язык целевого пользователя, чтобы отправить ему локализованное уведомление
    target_lang_code = await db_manager.get_user_language(target_user_id)
    if not target_lang_code: # Если пользователя нет в БД
        await bot.reply_to(message, loc.get_text('admin.user_not_found', lang_code).format(user_id=target_user_id))
        return

    notification_text = loc.get_text('admin.reply_admin_notification', target_lang_code).format(text=text_to_send)
    
    try:
        await bot.send_message(target_user_id, notification_text, parse_mode='Markdown')
        await bot.reply_to(message, loc.get_text('admin.reply_sent_success', lang_code).format(user_id=target_user_id))
        logger.info(f"Администратор {admin_id} отправил ответ пользователю {target_user_id}.")
    except ApiException as e:
        if "bot was blocked by the user" in e.description:
            await bot.reply_to(message, loc.get_text('admin.reply_sent_fail', lang_code))
        else:
            await bot.reply_to(message, f"Не удалось отправить сообщение: {e.description}")
        logger.error(f"Ошибка при отправке ответа от админа {admin_id} пользователю {target_user_id}: {e}")

# --- Обработчики Callback-запросов ---

@admin_required
async def handle_admin_main_menu(call: types.CallbackQuery, bot: AsyncTeleBot):
    """
    Возвращает в главное меню админ-панели.
    """
    user_id = call.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    
    admin_keyboard = await mk.create_admin_main_menu_keyboard(lang_code)
    await bot.edit_message_text(
        text=loc.get_text('admin.panel_title', lang_code),
        chat_id=user_id,
        message_id=call.message.message_id,
        reply_markup=admin_keyboard
    )
    await bot.answer_callback_query(call.id)

@admin_required
async def handle_maintenance_menu(call: types.CallbackQuery, bot: AsyncTeleBot):
    """
    Показывает меню управления режимом обслуживания.
    """
    user_id = call.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    
    maintenance_keyboard = await mk.create_maintenance_menu_keyboard(lang_code)
    await bot.edit_message_text(
        text=loc.get_text('admin.maintenance_menu_title', lang_code),
        chat_id=user_id,
        message_id=call.message.message_id,
        reply_markup=maintenance_keyboard
    )
    await bot.answer_callback_query(call.id)

@admin_required
async def handle_toggle_maintenance(call: types.CallbackQuery, bot: AsyncTeleBot):
    """
    Включает или выключает режим обслуживания.
    """
    action = call.data.split(':')[1] # 'on' or 'off'
    user_id = call.from_user.id
    lang_code = await db_manager.get_user_language(user_id)

    if action == 'on':
        await db_manager.set_app_setting('maintenance_mode', 'true')
        answer_text = loc.get_text('admin.maintenance_enabled_msg', lang_code)
        logger.warning("Активирован режим технического обслуживания.", extra={'user_id': str(user_id)})
    else:
        await db_manager.set_app_setting('maintenance_mode', 'false')
        answer_text = loc.get_text('admin.maintenance_disabled_msg', lang_code)
        logger.info("Режим технического обслуживания отключен.", extra={'user_id': str(user_id)})

    maintenance_keyboard = await mk.create_maintenance_menu_keyboard(lang_code)
    await bot.edit_message_reply_markup(
        chat_id=user_id,
        message_id=call.message.message_id,
        reply_markup=maintenance_keyboard
    )
    await bot.answer_callback_query(call.id, text=answer_text, show_alert=True)

# --- Блок коммуникации ---

@admin_required
async def handle_communication_menu(call: types.CallbackQuery, bot: AsyncTeleBot):
    """Показывает меню коммуникации."""
    user_id = call.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    
    comm_keyboard = await mk.create_communication_menu_keyboard(lang_code)
    await bot.edit_message_text(
        text=loc.get_text('admin.communication_title', lang_code),
        chat_id=user_id,
        message_id=call.message.message_id,
        reply_markup=comm_keyboard
    )
    await bot.answer_callback_query(call.id)

@admin_required
async def handle_broadcast_start(call: types.CallbackQuery, bot: AsyncTeleBot):
    """Начинает процесс создания рассылки."""
    user_id = call.from_user.id
    lang_code = await db_manager.get_user_language(user_id)

    await bot.set_state(user_id, STATE_ADMIN_WAITING_FOR_BROADCAST_MSG, user_id)
    await bot.edit_message_text(
        text=loc.get_text('admin.broadcast_prompt', lang_code),
        chat_id=user_id,
        message_id=call.message.message_id
    )
    await bot.answer_callback_query(call.id)

@admin_required
async def handle_broadcast_message(message: types.Message, bot: AsyncTeleBot):
    """Получает сообщение для рассылки и запрашивает подтверждение."""
    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    
    # Сохраняем текст сообщения в состояние для последующего использования
    await bot.add_data(user_id, user_id, broadcast_message=message.text)
    
    all_users = await db_manager.get_all_user_ids()
    count = len(all_users)
    
    confirmation_text = loc.get_text('admin.broadcast_confirm_prompt', lang_code).format(
        count=count,
        message_text=message.text
    )
    confirm_keyboard = mk.create_broadcast_confirmation_keyboard(lang_code)
    
    await bot.send_message(user_id, confirmation_text, reply_markup=confirm_keyboard)

@admin_required
async def handle_broadcast_cancel(call: types.CallbackQuery, bot: AsyncTeleBot):
    """Отменяет рассылку на этапе подтверждения."""
    user_id = call.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    
    await bot.delete_state(user_id, user_id)
    await bot.edit_message_text(
        text=loc.get_text('admin.broadcast_cancelled', lang_code),
        chat_id=user_id,
        message_id=call.message.message_id
    )
    # Через 2 секунды возвращаем в главное меню
    await asyncio.sleep(2)
    # Создаем фейковое сообщение, чтобы передать его в обработчик
    fake_message = types.Message(message_id=0, from_user=call.from_user, date=0, chat=call.message.chat, content_type='text', options={}, json_string="")
    await handle_admin_command(fake_message, bot)
    await bot.answer_callback_query(call.id)


async def _run_broadcast(bot: AsyncTeleBot, admin_id: int, message_text: str, lang_code: str):
    """Выполняет саму рассылку в фоновом режиме."""
    all_user_ids = await db_manager.get_all_user_ids()
    sent_count = 0
    failed_count = 0
    
    for user_id in all_user_ids:
        try:
            await bot.send_message(user_id, message_text, disable_web_page_preview=True)
            sent_count += 1
            logger.info(f"Рассылка: успешно отправлено пользователю {user_id}")
        except Exception as e:
            failed_count += 1
            logger.error(f"Рассылка: не удалось отправить пользователю {user_id}. Ошибка: {e}")
        await asyncio.sleep(0.1) # Пауза 100мс между сообщениями
        
    result_text = loc.get_text('admin.broadcast_finished', lang_code).format(
        sent=sent_count,
        failed=failed_count
    )
    await bot.send_message(admin_id, result_text)


@admin_required
async def handle_broadcast_confirm(call: types.CallbackQuery, bot: AsyncTeleBot):
    """Запускает рассылку после подтверждения."""
    admin_id = call.from_user.id
    lang_code = await db_manager.get_user_language(admin_id)
    
    async with bot.retrieve_data(admin_id, admin_id) as data:
        message_text = data.get('broadcast_message')
        
    if not message_text:
        await bot.answer_callback_query(call.id, "Ошибка: текст для рассылки не найден.", show_alert=True)
        return
        
    await bot.delete_state(admin_id, admin_id)
    await bot.edit_message_text(
        text=loc.get_text('admin.broadcast_started', lang_code),
        chat_id=admin_id,
        message_id=call.message.message_id
    )
    
    # Запускаем рассылку в фоновой задаче, чтобы не блокировать бота
    asyncio.create_task(_run_broadcast(bot, admin_id, message_text, lang_code))
    await bot.answer_callback_query(call.id)

# --- Регистрация всех обработчиков ---

def register_admin_handlers(bot: AsyncTeleBot):
    """
    Регистрирует все обработчики для админ-панели.
    """
    # --- Состояния ---
    bot.register_message_handler(
        handle_broadcast_message,
        state=STATE_ADMIN_WAITING_FOR_BROADCAST_MSG,
        pass_bot=True
    )
    bot.register_message_handler(
        handle_cancel_state,
        commands=['cancel'],
        state="*", # Ловит команду /cancel в любом состоянии
        pass_bot=True
    )

    # --- Команды ---
    bot.register_message_handler(
        handle_admin_command,
        commands=['admin'],
        pass_bot=True
    )
    bot.register_message_handler(
        handle_reply_command,
        commands=['reply'],
        pass_bot=True
    )
    
    # --- Текстовая кнопка ---
    bot.register_message_handler(
        handle_admin_command,
        func=lambda msg: msg.text in [loc.get_text('btn_admin_panel', 'ru'),
                                       loc.get_text('btn_admin_panel', 'en')],
        pass_bot=True
    )

    # --- Callback-запросы ---
    # Навигация
    bot.register_callback_query_handler(
        handle_admin_main_menu,
        func=lambda call: call.data == CALLBACK_ADMIN_MAIN_MENU,
        pass_bot=True
    )
    bot.register_callback_query_handler(
        handle_communication_menu,
        func=lambda call: call.data == CALLBACK_ADMIN_COMMUNICATION_MENU,
        pass_bot=True
    )
    # Режим обслуживания
    bot.register_callback_query_handler(
        handle_maintenance_menu,
        func=lambda call: call.data == CALLBACK_ADMIN_MAINTENANCE_MENU,
        pass_bot=True
    )
    bot.register_callback_query_handler(
        handle_toggle_maintenance,
        func=lambda call: call.data.startswith(CALLBACK_ADMIN_TOGGLE_MAINTENANCE),
        pass_bot=True
    )
    # Рассылка
    bot.register_callback_query_handler(
        handle_broadcast_start,
        func=lambda call: call.data == CALLBACK_ADMIN_BROADCAST,
        pass_bot=True
    )
    bot.register_callback_query_handler(
        handle_broadcast_confirm,
        func=lambda call: call.data == CALLBACK_ADMIN_CONFIRM_BROADCAST,
        pass_bot=True
    )
    bot.register_callback_query_handler(
        handle_broadcast_cancel,
        func=lambda call: call.data == CALLBACK_ADMIN_CANCEL_BROADCAST,
        pass_bot=True
    )
    
    logger.info("Обработчики админ-панели зарегистрированы.")