# File: utils/markup_helpers.py
from telebot import types
import datetime
from typing import List, Optional, Dict, Any

from config.settings import (
    BOT_STYLES, CALLBACK_ADMIN_BROADCAST, CALLBACK_ADMIN_CANCEL_BROADCAST, CALLBACK_ADMIN_CONFIRM_BROADCAST, TRANSLATE_LANGUAGES, BOT_PERSONAS, ADMIN_USER_ID,
    CALLBACK_SETTINGS_STYLE_PREFIX, CALLBACK_IGNORE,
    CALLBACK_CALENDAR_DATE_PREFIX, CALLBACK_CALENDAR_MONTH_PREFIX,
    CALLBACK_REPORT_ERROR, CALLBACK_LANG_PREFIX,
    CALLBACK_SETTINGS_LANG_PREFIX, CALLBACK_SETTINGS_SET_API_KEY,
    CALLBACK_SETTINGS_CHOOSE_MODEL_MENU, CALLBACK_SETTINGS_MODEL_PREFIX, CALLBACK_SETTINGS_BACK_TO_MAIN,
    CALLBACK_SETTINGS_PERSONA_MENU, CALLBACK_SETTINGS_PERSONA_PREFIX,
    # Dialogs
    CALLBACK_DIALOGS_MENU, CALLBACK_DIALOG_SWITCH_PREFIX, CALLBACK_DIALOG_RENAME_PREFIX,
    CALLBACK_DIALOG_DELETE_PREFIX, CALLBACK_DIALOG_CREATE, CALLBACK_DIALOG_CONFIRM_DELETE_PREFIX,
    # Admin Panel
    CALLBACK_ADMIN_MAIN_MENU, CALLBACK_ADMIN_STATS_MENU, CALLBACK_ADMIN_COMMUNICATION_MENU,
    CALLBACK_ADMIN_USER_MANAGEMENT_MENU, CALLBACK_ADMIN_TOGGLE_MAINTENANCE
)
from database import db_manager
from logger_config import get_logger
from . import localization as loc

logger = get_logger('markup_helpers')


def create_main_keyboard(lang_code: str, user_id: int) -> types.ReplyKeyboardMarkup:
    """Создает основную клавиатуру с кнопками команд на основе языка и ID пользователя."""
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)

    # Стандартные кнопки для всех
    buttons = [
        types.KeyboardButton(loc.get_text('btn_dialogs', lang_code)),
        types.KeyboardButton(loc.get_text('btn_account', lang_code)),
        types.KeyboardButton(loc.get_text('btn_usage', lang_code)),
        types.KeyboardButton(loc.get_text('btn_settings', lang_code)),
        types.KeyboardButton(loc.get_text('btn_translate', lang_code)),
        types.KeyboardButton(loc.get_text('btn_history', lang_code)),
        types.KeyboardButton(loc.get_text('btn_help', lang_code)),
        types.KeyboardButton(loc.get_text('btn_reset', lang_code)),
    ]

    # Добавляем админ-кнопку, если ID совпадает
    if user_id == ADMIN_USER_ID:
        admin_button = types.KeyboardButton(loc.get_text('btn_admin_panel', lang_code))
        # Вставляем админ-кнопку в начало для быстрого доступа
        buttons.insert(0, admin_button)

    markup.add(*buttons)
    return markup


async def create_dialogs_menu_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    """Создает клавиатуру для управления диалогами."""
    markup = types.InlineKeyboardMarkup(row_width=3)
    lang_code = await db_manager.get_user_language(user_id)
    dialogs = await db_manager.get_user_dialogs(user_id)
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)

    # Добавляем кнопки для каждого диалога
    for dialog in dialogs:
        is_active = dialog['dialog_id'] == active_dialog_id

        # Кнопка с названием диалога (для переключения)
        button_text = f"✅ {dialog['name']}" if is_active else dialog['name']
        callback_data = CALLBACK_IGNORE if is_active else f"{CALLBACK_DIALOG_SWITCH_PREFIX}{dialog['dialog_id']}"
        dialog_button = types.InlineKeyboardButton(button_text, callback_data=callback_data)

        # Кнопки управления для этого диалога
        rename_button = types.InlineKeyboardButton("✏️", callback_data=f"{CALLBACK_DIALOG_RENAME_PREFIX}{dialog['dialog_id']}")

        # Кнопку удаления показываем только для НЕактивных диалогов
        if not is_active:
            delete_button = types.InlineKeyboardButton("❌", callback_data=f"{CALLBACK_DIALOG_DELETE_PREFIX}{dialog['dialog_id']}")
            markup.row(dialog_button, rename_button, delete_button)
        else:
            # Для активного диалога кнопка удаления отсутствует
            markup.row(dialog_button, rename_button)

    # Общая кнопка для создания нового диалога
    markup.add(types.InlineKeyboardButton(
        "➕ " + loc.get_text('btn_create_dialog', lang_code),
        callback_data=CALLBACK_DIALOG_CREATE
    ))

    return markup

def create_confirm_delete_keyboard(dialog_id: int, lang_code: str) -> types.InlineKeyboardMarkup:
    """Создает клавиатуру для подтверждения удаления диалога."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    confirm_button = types.InlineKeyboardButton(
        loc.get_text('btn_confirm_delete', lang_code),
        callback_data=f"{CALLBACK_DIALOG_CONFIRM_DELETE_PREFIX}{dialog_id}"
    )
    cancel_button = types.InlineKeyboardButton(
        loc.get_text('btn_cancel_delete', lang_code),
        callback_data=CALLBACK_DIALOGS_MENU
    )
    markup.add(confirm_button, cancel_button)
    return markup


def create_language_selection_keyboard() -> types.InlineKeyboardMarkup:
    """Создает inline-клавиатуру для выбора языка для ПЕРЕВОДА."""
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    sorted_languages = sorted(TRANSLATE_LANGUAGES.items(), key=lambda item: item[1])

    for lang_code, lang_name in sorted_languages:
        buttons.append(types.InlineKeyboardButton(lang_name, callback_data=f"{CALLBACK_LANG_PREFIX}{lang_code}"))

    for i in range(0, len(buttons), 3):
        markup.add(*buttons[i:i+3])
    return markup


async def create_settings_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    """Создает inline-клавиатуру настроек, включая стиль, язык и API ключ."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    current_style = await db_manager.get_user_bot_style(user_id)
    current_lang = await db_manager.get_user_language(user_id)

    # --- Секция API ключа ---
    markup.add(types.InlineKeyboardButton(loc.get_text('settings_api_key_section', current_lang), callback_data=CALLBACK_IGNORE))
    markup.add(types.InlineKeyboardButton(
        loc.get_text('settings_btn_set_api_key', current_lang),
        callback_data=CALLBACK_SETTINGS_SET_API_KEY
    ))

    # --- Секция выбора модели ---
    markup.add(types.InlineKeyboardButton(loc.get_text('settings_model_section', current_lang), callback_data=CALLBACK_IGNORE))
    markup.add(types.InlineKeyboardButton(
        loc.get_text('settings_btn_choose_model', current_lang),
        callback_data=CALLBACK_SETTINGS_CHOOSE_MODEL_MENU
    ))

    # --- Секция выбора персоны ---
    markup.add(types.InlineKeyboardButton(loc.get_text('settings_persona_section', current_lang), callback_data=CALLBACK_IGNORE))
    markup.add(types.InlineKeyboardButton(
        loc.get_text('settings_btn_choose_persona', current_lang),
        callback_data=CALLBACK_SETTINGS_PERSONA_MENU
    ))

    # --- Секция стиля общения (ВОЗВРАЩЕНА) ---
    markup.add(types.InlineKeyboardButton(loc.get_text('settings_style_section', current_lang), callback_data=CALLBACK_IGNORE))
    style_buttons = []
    for style_code, style_name in BOT_STYLES.items():
        button_text = f"✅ {style_name}" if style_code == current_style else style_name
        style_buttons.append(types.InlineKeyboardButton(button_text, callback_data=f'{CALLBACK_SETTINGS_STYLE_PREFIX}{style_code}'))

    style_rows = [style_buttons[i:i + 2] for i in range(0, len(style_buttons), 2)]
    for row in style_rows:
        markup.add(*row)

    # --- Секция языка интерфейса ---
    markup.add(types.InlineKeyboardButton(loc.get_text('settings_language_section', current_lang), callback_data=CALLBACK_IGNORE))
    lang_buttons = [
        types.InlineKeyboardButton(f"{'✅ ' if current_lang == 'ru' else ''}🇷🇺 Русский", callback_data=f"{CALLBACK_SETTINGS_LANG_PREFIX}ru"),
        types.InlineKeyboardButton(f"{'✅ ' if current_lang == 'en' else ''}🇺🇸 English", callback_data=f"{CALLBACK_SETTINGS_LANG_PREFIX}en")
    ]
    markup.add(*lang_buttons)

    return markup


async def create_persona_selection_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    """Создает клавиатуру для выбора персоны."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    lang_code = await db_manager.get_user_language(user_id)
    current_persona_id = await db_manager.get_user_persona(user_id)

    buttons = []
    for persona_id, persona_data in BOT_PERSONAS.items():
        persona_name = persona_data.get(f"name_{lang_code}", persona_data["name_ru"])
        button_text = f"✅ {persona_name}" if persona_id == current_persona_id else persona_name
        buttons.append(types.InlineKeyboardButton(
            text=button_text,
            callback_data=f"{CALLBACK_SETTINGS_PERSONA_PREFIX}{persona_id}"
        ))

    for i in range(0, len(buttons), 2):
        markup.add(*buttons[i:i + 2])

    markup.add(types.InlineKeyboardButton(
        loc.get_text('btn_back_to_settings', lang_code),
        callback_data=CALLBACK_SETTINGS_BACK_TO_MAIN
    ))
    return markup


def create_model_selection_keyboard(models: List[Dict[str, str]], current_model: Optional[str], lang_code: str) -> types.InlineKeyboardMarkup:
    """Создает клавиатуру для выбора модели Gemini."""
    markup = types.InlineKeyboardMarkup(row_width=1)

    for model in models:
        model_id = model['name']
        display_name = model['display_name']
        text = f"✅ {display_name}" if model_id == current_model else display_name
        markup.add(types.InlineKeyboardButton(
            text,
            callback_data=f"{CALLBACK_SETTINGS_MODEL_PREFIX}{model_id}"
        ))

    markup.add(types.InlineKeyboardButton(
        loc.get_text('btn_back_to_settings', lang_code),
        callback_data=CALLBACK_SETTINGS_BACK_TO_MAIN
    ))
    return markup


def create_calendar_keyboard(year: Optional[int] = None, month: Optional[int] = None) -> types.InlineKeyboardMarkup:
    """Создает inline-клавиатуру с календарем для выбора даты истории."""
    now = datetime.datetime.now()
    year = year or now.year
    month = month or now.month
    markup = types.InlineKeyboardMarkup(row_width=7)

    try:
        month_name = datetime.date(year, month, 1).strftime("%B %Y")
    except ValueError:
        year, month = now.year, now.month
        month_name = datetime.date(year, month, 1).strftime("%B %Y")

    markup.row(types.InlineKeyboardButton(month_name, callback_data=CALLBACK_IGNORE))
    days_of_week = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    markup.row(*[types.InlineKeyboardButton(day, callback_data=CALLBACK_IGNORE) for day in days_of_week])

    try:
        first_day_of_month = datetime.date(year, month, 1)
        if month == 12:
            last_day_of_month_day = 31
        else:
            last_day_of_month_day = (datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)).day

        row_buttons = [types.InlineKeyboardButton(" ", callback_data=CALLBACK_IGNORE)] * first_day_of_month.weekday()

        for day_num in range(1, last_day_of_month_day + 1):
            current_date = datetime.date(year, month, day_num)
            callback_value = f"{CALLBACK_CALENDAR_DATE_PREFIX}{current_date.strftime('%Y-%m-%d')}"
            row_buttons.append(types.InlineKeyboardButton(str(day_num), callback_data=callback_value))

            if len(row_buttons) == 7:
                markup.row(*row_buttons)
                row_buttons = []

        if row_buttons:
            row_buttons.extend([types.InlineKeyboardButton(" ", callback_data=CALLBACK_IGNORE)] * (7 - len(row_buttons)))
            markup.row(*row_buttons)

    except ValueError as date_err:
        logger.error(f"Ошибка генерации дней календаря для {year}-{month}: {date_err}")

    prev_month_date = first_day_of_month - datetime.timedelta(days=1)
    if month == 12:
        next_month_date = datetime.date(year + 1, 1, 1)
    else:
        next_month_date = datetime.date(year, month + 1, 1)

    nav_buttons = [
        types.InlineKeyboardButton("⬅️", callback_data=f"{CALLBACK_CALENDAR_MONTH_PREFIX}{prev_month_date.year}-{prev_month_date.month}"),
        types.InlineKeyboardButton(" ", callback_data=CALLBACK_IGNORE),
        types.InlineKeyboardButton("➡️", callback_data=f"{CALLBACK_CALENDAR_MONTH_PREFIX}{next_month_date.year}-{next_month_date.month}")
    ]
    markup.row(*nav_buttons)
    return markup


def create_error_report_button() -> types.InlineKeyboardMarkup:
    """Создает inline-клавиатуру с кнопкой 'Сообщить об ошибке'."""
    markup = types.InlineKeyboardMarkup()
    btn_report_error = types.InlineKeyboardButton('🆘 Сообщить об ошибке / Report Error', callback_data=CALLBACK_REPORT_ERROR)
    markup.add(btn_report_error)
    return markup


# --- НОВЫЕ ФУНКЦИИ ДЛЯ АДМИН-ПАНЕЛИ ---

async def create_admin_main_menu_keyboard(lang_code: str) -> types.InlineKeyboardMarkup:
    """Создает главное меню админ-панели."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    stats_btn = types.InlineKeyboardButton(
        loc.get_text('admin.btn_stats', lang_code),
        callback_data=CALLBACK_ADMIN_STATS_MENU
    )
    comm_btn = types.InlineKeyboardButton(
        loc.get_text('admin.btn_communication', lang_code),
        callback_data=CALLBACK_ADMIN_COMMUNICATION_MENU
    )
    user_mgmt_btn = types.InlineKeyboardButton(
        loc.get_text('admin.btn_user_management', lang_code),
        callback_data=CALLBACK_ADMIN_USER_MANAGEMENT_MENU
    )
    # Используем правильную константу, которую добавили в settings.py
    maintenance_btn = types.InlineKeyboardButton(
        loc.get_text('admin.btn_maintenance', lang_code),
        callback_data='admin_maintenance_menu' # Заменяем заглушку на правильный callback
    )
    markup.add(stats_btn, comm_btn)
    markup.add(user_mgmt_btn, maintenance_btn)
    return markup

async def create_maintenance_menu_keyboard(lang_code: str) -> types.InlineKeyboardMarkup:
    """Создает клавиатуру для управления режимом обслуживания."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    maintenance_mode_str = await db_manager.get_app_setting('maintenance_mode')
    is_on = maintenance_mode_str == 'true'

    status_text = loc.get_text('admin.maintenance_status_on', lang_code) if is_on else loc.get_text('admin.maintenance_status_off', lang_code)
    markup.add(types.InlineKeyboardButton(status_text, callback_data=CALLBACK_IGNORE))

    if is_on:
        toggle_btn = types.InlineKeyboardButton(
            loc.get_text('admin.btn_maintenance_disable', lang_code),
            callback_data=f"{CALLBACK_ADMIN_TOGGLE_MAINTENANCE}:off"
        )
    else:
        toggle_btn = types.InlineKeyboardButton(
            loc.get_text('admin.btn_maintenance_enable', lang_code),
            callback_data=f"{CALLBACK_ADMIN_TOGGLE_MAINTENANCE}:on"
        )
    markup.add(toggle_btn)

    markup.add(types.InlineKeyboardButton(
        loc.get_text('admin.btn_back_to_admin_menu', lang_code),
        callback_data=CALLBACK_ADMIN_MAIN_MENU
    ))
    return markup

async def create_communication_menu_keyboard(lang_code: str) -> types.InlineKeyboardMarkup:
    """Создает меню для раздела 'Коммуникация'."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    broadcast_btn = types.InlineKeyboardButton(
        loc.get_text('admin.btn_broadcast', lang_code),
        callback_data=CALLBACK_ADMIN_BROADCAST
    )
    # Сюда в будущем можно будет добавить кнопку "Личное сообщение"
    back_btn = types.InlineKeyboardButton(
        loc.get_text('admin.btn_back_to_admin_menu', lang_code),
        callback_data=CALLBACK_ADMIN_MAIN_MENU
    )
    markup.add(broadcast_btn, back_btn)
    return markup

def create_broadcast_confirmation_keyboard(lang_code: str) -> types.InlineKeyboardMarkup:
    """Создает клавиатуру для подтверждения рассылки."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    confirm_btn = types.InlineKeyboardButton(
        loc.get_text('admin.btn_confirm_broadcast', lang_code),
        callback_data=CALLBACK_ADMIN_CONFIRM_BROADCAST
    )
    cancel_btn = types.InlineKeyboardButton(
        loc.get_text('admin.btn_cancel_broadcast', lang_code),
        callback_data=CALLBACK_ADMIN_CANCEL_BROADCAST
    )
    markup.add(confirm_btn, cancel_btn)
    return markup