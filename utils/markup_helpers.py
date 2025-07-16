# File: utils/markup_helpers.py
from telebot import types
import datetime
from typing import List, Optional, Dict, Any

from config.settings import (
    BOT_STYLES, TRANSLATE_LANGUAGES,
    CALLBACK_SETTINGS_STYLE_PREFIX, CALLBACK_IGNORE,
    CALLBACK_CALENDAR_DATE_PREFIX, CALLBACK_CALENDAR_MONTH_PREFIX,
    CALLBACK_REPORT_ERROR, CALLBACK_LANG_PREFIX,
    CALLBACK_SETTINGS_LANG_PREFIX, CALLBACK_SETTINGS_SET_API_KEY,
    CALLBACK_SETTINGS_CHOOSE_MODEL_MENU, CALLBACK_SETTINGS_MODEL_PREFIX, CALLBACK_SETTINGS_BACK_TO_MAIN
)
from database import db_manager
from logger_config import get_logger
# Импортируем наш модуль локализации
from . import localization as loc

logger = get_logger('markup_helpers')

def create_main_keyboard(lang_code: str) -> types.ReplyKeyboardMarkup:
    """Создает основную клавиатуру с кнопками команд на основе языка пользователя."""
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True) # ИЗМЕНЕНО: row_width=3

    # ИЗМЕНЕНО: Добавляем кнопку "Расходы" и меняем компоновку
    buttons = [
        types.KeyboardButton(loc.get_text('btn_account', lang_code)),
        types.KeyboardButton(loc.get_text('btn_usage', lang_code)),
        types.KeyboardButton(loc.get_text('btn_settings', lang_code)),
        types.KeyboardButton(loc.get_text('btn_translate', lang_code)),
        types.KeyboardButton(loc.get_text('btn_history', lang_code)),
        types.KeyboardButton(loc.get_text('btn_reset', lang_code)),
        types.KeyboardButton(loc.get_text('btn_help', lang_code)),
    ]
    markup.add(*buttons)
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


def create_settings_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    """Создает inline-клавиатуру настроек, включая стиль, язык и API ключ."""
    markup = types.InlineKeyboardMarkup(row_width=1)

    # Получаем текущие настройки пользователя
    current_style = db_manager.get_user_bot_style(user_id)
    current_lang = db_manager.get_user_language(user_id)

    # --- Секция API ключа ---
    markup.add(types.InlineKeyboardButton(loc.get_text('settings_api_key_section', current_lang), callback_data=CALLBACK_IGNORE))
    api_key_button = types.InlineKeyboardButton(
        loc.get_text('settings_btn_set_api_key', current_lang),
        callback_data=CALLBACK_SETTINGS_SET_API_KEY
    )
    markup.add(api_key_button)

    # --- Секция выбора модели ---
    markup.add(types.InlineKeyboardButton(loc.get_text('settings_model_section', current_lang), callback_data=CALLBACK_IGNORE))
    model_button = types.InlineKeyboardButton(
        loc.get_text('settings_btn_choose_model', current_lang),
        callback_data=CALLBACK_SETTINGS_CHOOSE_MODEL_MENU
    )
    markup.add(model_button)

    # --- Секция стиля общения ---
    markup.add(types.InlineKeyboardButton(loc.get_text('settings_style_section', current_lang), callback_data=CALLBACK_IGNORE))
    style_buttons = []
    for style_code, style_name in BOT_STYLES.items():
        button_text = f"✅ {style_name}" if style_code == current_style else style_name
        style_buttons.append(types.InlineKeyboardButton(button_text, callback_data=f'{CALLBACK_SETTINGS_STYLE_PREFIX}{style_code}'))

    # Размещаем кнопки стилей по две в ряд для компактности
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
        # Форматируем название месяца на английском, так как locale может быть не настроен
        month_name = datetime.date(year, month, 1).strftime("%B %Y")
    except ValueError:
        year, month = now.year, now.month
        month_name = datetime.date(year, month, 1).strftime("%B %Y")

    markup.row(types.InlineKeyboardButton(month_name, callback_data=CALLBACK_IGNORE))
    days_of_week = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    markup.row(*[types.InlineKeyboardButton(day, callback_data=CALLBACK_IGNORE) for day in days_of_week])

    try:
        first_day_of_month = datetime.date(year, month, 1)
        # Корректное определение последнего дня месяца
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

    # --- Навигация ---
    prev_month_date = first_day_of_month - datetime.timedelta(days=1)
    # Корректный переход на следующий месяц
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
