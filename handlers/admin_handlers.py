# File: handlers/admin_handlers.py
"""
Обработчики для админ-панели. Доступ к этим функциям строго ограничен
переменной ADMIN_USER_ID из файла настроек.
"""
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from functools import wraps

from config.settings import ADMIN_USER_ID, CALLBACK_ADMIN_MAIN_MENU, CALLBACK_ADMIN_TOGGLE_MAINTENANCE
from utils import markup_helpers as mk
from utils import localization as loc
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
            
            # Определяем, как отвечать: на сообщение или на callback
            if isinstance(message_or_call, types.Message):
                bot = args[0] if args and isinstance(args[0], AsyncTeleBot) else kwargs.get('bot')
                if bot:
                    await bot.reply_to(message_or_call, error_text)
            elif isinstance(message_or_call, types.CallbackQuery):
                bot = args[0] if args and isinstance(args[0], AsyncTeleBot) else kwargs.get('bot')
                if bot:
                    await bot.answer_callback_query(message_or_call.id, text=error_text, show_alert=True)
            
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

    # Обновляем клавиатуру, чтобы показать актуальный статус
    maintenance_keyboard = await mk.create_maintenance_menu_keyboard(lang_code)
    await bot.edit_message_reply_markup(
        chat_id=user_id,
        message_id=call.message.message_id,
        reply_markup=maintenance_keyboard
    )
    await bot.answer_callback_query(call.id, text=answer_text, show_alert=True)


# --- Регистрация всех обработчиков ---

def register_admin_handlers(bot: AsyncTeleBot):
    """
    Регистрирует все обработчики для админ-панели.
    """
    # Обработчик команды /admin и текстовой кнопки
    bot.register_message_handler(
        handle_admin_command,
        commands=['admin'],
        pass_bot=True
    )
    bot.register_message_handler(
        handle_admin_command,
        func=lambda msg: msg.text in [loc.get_text('btn_admin_panel', 'ru'),
                                       loc.get_text('btn_admin_panel', 'en')],
        pass_bot=True
    )

    # Обработчики callback-запросов
    bot.register_callback_query_handler(
        handle_admin_main_menu,
        func=lambda call: call.data == CALLBACK_ADMIN_MAIN_MENU,
        pass_bot=True
    )
    bot.register_callback_query_handler(
        handle_maintenance_menu,
        func=lambda call: call.data == 'admin_maintenance', # Временный, будет заменен на константу
        pass_bot=True
    )
    bot.register_callback_query_handler(
        handle_toggle_maintenance,
        func=lambda call: call.data.startswith(CALLBACK_ADMIN_TOGGLE_MAINTENANCE),
        pass_bot=True
    )
    
    logger.info("Обработчики админ-панели зарегистрированы.")