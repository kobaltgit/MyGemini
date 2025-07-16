# File: handlers/command_handlers.py
from telebot.async_telebot import AsyncTeleBot
from telebot import types

from . import telegram_helpers as tg_helpers
from utils import markup_helpers as mk
from utils import localization as loc
from utils import guide_manager

from config.settings import (
    STATE_WAITING_FOR_HISTORY_DATE,
    STATE_WAITING_FOR_API_KEY,
    TOKEN_PRICING,
    GEMINI_MODEL_NAME,
    STATE_WAITING_FOR_NEW_DIALOG_NAME, # Импорт состояний
    STATE_WAITING_FOR_RENAME_DIALOG
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

    await db_manager.add_or_update_user(user_id)
    lang_code = await db_manager.get_user_language(user_id)

    await bot.delete_state(message.from_user.id, message.chat.id)
    # Сбрасываем кэш активного диалога
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)
    if active_dialog_id:
        gemini_service.reset_dialog_chat(active_dialog_id)

    welcome_text = loc.get_text('welcome', lang_code).format(name=first_name)
    await tg_helpers.send_long_message(
        bot, user_id, welcome_text,
        reply_markup=mk.create_main_keyboard(lang_code)
    )


async def handle_help(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /help."""
    user_id = message.chat.id
    lang_code = await db_manager.get_user_language(user_id)
    help_text = loc.get_text('cmd_help_text', lang_code)
    await tg_helpers.send_long_message(
        bot, user_id, help_text,
        reply_markup=mk.create_main_keyboard(lang_code)
    )


async def handle_reset(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /reset."""
    user_id = message.chat.id
    lang_code = await db_manager.get_user_language(user_id)

    await bot.delete_state(message.from_user.id, message.chat.id)
    # ИЗМЕНЕНО: сбрасываем кэш только для активного диалога
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)
    if active_dialog_id:
        gemini_service.reset_dialog_chat(active_dialog_id)

    reset_text = loc.get_text('cmd_reset_success', lang_code)
    main_keyboard = mk.create_main_keyboard(lang_code)
    await bot.reply_to(message, reset_text, reply_markup=main_keyboard)


async def handle_set_api_key(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /set_api_key."""
    user_id = message.chat.id
    lang_code = await db_manager.get_user_language(user_id)

    text = loc.get_text('set_api_key_prompt', lang_code)
    await bot.set_state(message.from_user.id, STATE_WAITING_FOR_API_KEY, message.chat.id)
    await bot.reply_to(message, text, reply_markup=types.ReplyKeyboardRemove())


async def handle_history(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /history."""
    user_id = message.chat.id
    lang_code = await db_manager.get_user_language(user_id)

    calendar_markup = mk.create_calendar_keyboard()
    text = loc.get_text('history_prompt', lang_code)
    await bot.send_message(user_id, text, reply_markup=calendar_markup)
    await bot.set_state(message.from_user.id, STATE_WAITING_FOR_HISTORY_DATE, message.chat.id)


async def handle_settings(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /settings."""
    user_id = message.chat.id
    lang_code = await db_manager.get_user_language(user_id)
    settings_markup = await mk.create_settings_keyboard(user_id)
    await bot.send_message(
        user_id, loc.get_text('settings_title', lang_code),
        reply_markup=settings_markup
    )

# НОВЫЙ ОБРАБОТЧИК
async def handle_dialogs(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /dialogs."""
    user_id = message.chat.id
    lang_code = await db_manager.get_user_language(user_id)

    text = f"{loc.get_text('dialogs_menu_title', lang_code)}\n\n" \
           f"{loc.get_text('dialogs_menu_desc', lang_code)}"

    dialogs_keyboard = await mk.create_dialogs_menu_keyboard(user_id)
    await bot.send_message(
        user_id,
        text,
        reply_markup=dialogs_keyboard
    )

async def handle_translate(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /translate."""
    user_id = message.chat.id
    lang_code = await db_manager.get_user_language(user_id)

    lang_markup = mk.create_language_selection_keyboard()
    text = loc.get_text('translate_prompt', lang_code)
    await bot.send_message(user_id, text, reply_markup=lang_markup)


async def handle_personal_account_button(message: types.Message, bot: AsyncTeleBot):
    """Обработчик нажатия на кнопку 'Личный кабинет'."""
    user_id = message.chat.id
    await tg_helpers.send_typing_action(bot, user_id)
    info_text = await personal_account.get_personal_account_info(user_id)
    lang_code = await db_manager.get_user_language(user_id)
    main_keyboard = mk.create_main_keyboard(lang_code)
    await tg_helpers.send_long_message(
        bot, user_id, info_text,
        reply_markup=main_keyboard
    )


async def handle_usage(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /usage для отображения статистики расходов."""
    user_id = message.chat.id
    lang_code = await db_manager.get_user_language(user_id)

    api_key_exists = await db_manager.get_user_api_key(user_id)
    if not api_key_exists:
        await bot.reply_to(message, loc.get_text('api_key_needed_for_feature', lang_code))
        return

    usage_today = await db_manager.get_token_usage_by_period(user_id, 'today')
    usage_month = await db_manager.get_token_usage_by_period(user_id, 'month')

    user_model = await db_manager.get_user_gemini_model(user_id) or GEMINI_MODEL_NAME
    pricing = TOKEN_PRICING.get(user_model, TOKEN_PRICING['default'])

    def calculate_cost(usage_data):
        input_cost = (usage_data['prompt_tokens'] / 1_000_000) * pricing['input_usd_per_million']
        output_cost = (usage_data['completion_tokens'] / 1_000_000) * pricing['output_usd_per_million']
        return input_cost + output_cost

    cost_today = calculate_cost(usage_today)
    cost_month = calculate_cost(usage_month)

    report_text = f"{loc.get_text('usage_title', lang_code)}\n\n"
    report_text += f"{loc.get_text('usage_today_header', lang_code)}\n"
    if usage_today['total_tokens'] > 0:
        report_text += (
            f"`{loc.get_text('usage_prompt_tokens', lang_code):<25}: {usage_today['prompt_tokens']:,}`\n"
            f"`{loc.get_text('usage_completion_tokens', lang_code):<25}: {usage_today['completion_tokens']:,}`\n"
            f"`{loc.get_text('usage_total_tokens', lang_code):<25}: {usage_today['total_tokens']:,}`\n"
            f"`{loc.get_text('usage_estimated_cost', lang_code):<25}: ${cost_today:.4f}`\n\n"
        )
    else:
        report_text += f"_{loc.get_text('usage_no_data', lang_code)}_\n\n"

    report_text += f"{loc.get_text('usage_month_header', lang_code)}\n"
    if usage_month['total_tokens'] > 0:
        report_text += (
            f"`{loc.get_text('usage_prompt_tokens', lang_code):<25}: {usage_month['prompt_tokens']:,}`\n"
            f"`{loc.get_text('usage_completion_tokens', lang_code):<25}: {usage_month['completion_tokens']:,}`\n"
            f"`{loc.get_text('usage_total_tokens', lang_code):<25}: {usage_month['total_tokens']:,}`\n"
            f"`{loc.get_text('usage_estimated_cost', lang_code):<25}: ${cost_month:.4f}`"
        )
    else:
        report_text += f"_{loc.get_text('usage_no_data', lang_code)}_"

    report_text += loc.get_text('usage_cost_notice', lang_code)
    await bot.send_message(user_id, report_text, parse_mode='Markdown')

# --- НОВЫЕ ОБРАБОТЧИКИ ДЛЯ СПРАВКИ ---

async def handle_full_guide(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /help_guide, отправляет полную справку."""
    user_id = message.chat.id
    lang_code = await db_manager.get_user_language(user_id)
    
    # Отправляем typing action, так как отправка может занять время
    await tg_helpers.send_typing_action(bot, user_id)
    
    guide_text = guide_manager.get_full_guide(lang_code)
    await tg_helpers.send_long_message(bot, user_id, guide_text, parse_mode='Markdown')


async def handle_api_key_info(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /apikey_info, отправляет секцию про API ключ."""
    user_id = message.chat.id
    lang_code = await db_manager.get_user_language(user_id)

    await tg_helpers.send_typing_action(bot, user_id)
    
    guide_text = guide_manager.get_guide_section('API_KEY', lang_code)
    await tg_helpers.send_long_message(bot, user_id, guide_text, parse_mode='Markdown')

def register_command_handlers(bot: AsyncTeleBot):
    """Регистрирует все обработчики команд и кнопок-синонимов."""
    bot.register_message_handler(handle_start, commands=['start'], pass_bot=True)
    bot.register_message_handler(handle_help, commands=['help'], pass_bot=True)

    # --- НОВЫЕ КОМАНДЫ ---
    bot.register_message_handler(handle_full_guide, commands=['help_guide', 'guide'], pass_bot=True)
    bot.register_message_handler(handle_api_key_info, commands=['apikey_info', 'key_info'], pass_bot=True)
    # ---------------------

    bot.register_message_handler(handle_reset, commands=['reset'], pass_bot=True)
    bot.register_message_handler(handle_set_api_key, commands=['set_api_key', 'setapikey'], pass_bot=True)
    bot.register_message_handler(handle_settings, commands=['settings'], pass_bot=True)
    bot.register_message_handler(handle_history, commands=['history'], pass_bot=True)
    bot.register_message_handler(handle_translate, commands=['translate'], pass_bot=True)
    bot.register_message_handler(handle_usage, commands=['usage'], pass_bot=True)
    bot.register_message_handler(handle_dialogs, commands=['dialogs'], pass_bot=True) # РЕГИСТРАЦИЯ КОМАНДЫ

    # Регистрация кнопок-синонимов
    bot.register_message_handler(handle_dialogs,
                                 func=lambda msg: msg.text in [loc.get_text('btn_dialogs', 'ru'),
                                                               loc.get_text('btn_dialogs', 'en')], pass_bot=True)
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
    bot.register_message_handler(handle_usage,
                                 func=lambda msg: msg.text in [loc.get_text('btn_usage', 'ru'),
                                                               loc.get_text('btn_usage', 'en')], pass_bot=True)

    logger.info("Обработчики команд и кнопок-синонимов зарегистрированы.")