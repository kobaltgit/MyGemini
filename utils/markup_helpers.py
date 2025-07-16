# --- START OF FILE utils/markup_helpers.py ---
from telebot import types
import datetime
# import sqlite3 # <-- Убираем, тип List[Dict[str, Any]] приходит из db_manager
import pytz # <-- Добавляем для списка таймзон
from typing import List, Optional, Dict, Any # <-- Добавляем Dict, Any

# Импортируем константы и словари из настроек
from config.settings import (
    BOT_STYLES, LANGUAGE_FLAGS,
    CALLBACK_SETTINGS_STYLE_PREFIX, CALLBACK_IGNORE,
    CALLBACK_CALENDAR_DATE_PREFIX, CALLBACK_CALENDAR_MONTH_PREFIX,
    CALLBACK_SET_REMINDER_PREFIX, # CALLBACK_VIEW_REMINDERS - не используется
    CALLBACK_DELETE_REMINDER_PREFIX, CALLBACK_REPORT_ERROR,
    CALLBACK_LANG_PREFIX,
    # --- Добавляем префиксы для настроек таймзоны ---
    CALLBACK_SETTINGS_SET_TIMEZONE_PREFIX, # Для кнопки "Установить часовой пояс"
    CALLBACK_SETTINGS_DETECT_TIMEZONE # Для кнопки "Определить по геолокации"
)
# Импортируем db_manager для получения текущей таймзоны пользователя
from database import db_manager
# Импортируем логгер
from logger_config import get_logger

logger = get_logger('markup_helpers')


def create_main_keyboard() -> types.ReplyKeyboardMarkup:
    """Создает основную клавиатуру с кнопками команд."""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=False) # one_time_keyboard=False чтобы не скрывалась

    # Кнопки из словаря, чтобы легко добавлять/убирать
    buttons = [
        types.KeyboardButton('🇷🇺 Перевести'),
        types.KeyboardButton('📝 Изложить'),
        types.KeyboardButton('💰 План дохода'),
        types.KeyboardButton('📜 История'),
        types.KeyboardButton('⏰ Напоминания'),
        types.KeyboardButton('👤 Личный кабинет'),
        types.KeyboardButton('⚙️ Настройки'),
        types.KeyboardButton('❓ Помощь'),
        types.KeyboardButton('🔄 Сброс'),
    ]
    # Добавляем кнопки парами, последняя нечетная - одна в ряду
    markup.add(*buttons) # Можно добавить все сразу, библиотека сама распределит по row_width

    return markup

def create_language_selection_keyboard() -> types.InlineKeyboardMarkup:
    """Создает inline-клавиатуру для выбора языка перевода."""
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    # Сортируем языки по названию для удобства
    sorted_languages = sorted(LANGUAGE_FLAGS.items(), key=lambda item: item[1])

    for lang_code, lang_name in sorted_languages:
        buttons.append(types.InlineKeyboardButton(lang_name, callback_data=f"{CALLBACK_LANG_PREFIX}{lang_code}"))

    # Группируем кнопки по 3 в ряд
    for i in range(0, len(buttons), 3):
        markup.add(*buttons[i:i+3]) # Распаковываем срез кнопок

    return markup

def create_settings_keyboard(user_id: int) -> types.InlineKeyboardMarkup: # Добавили user_id
    """Создает inline-клавиатуру настроек, включая часовой пояс."""
    markup = types.InlineKeyboardMarkup(row_width=1) # По одной кнопке в ряд для ясности

    # --- Настройки стиля бота ---
    markup.add(types.InlineKeyboardButton("--- Стиль общения бота ---", callback_data=CALLBACK_IGNORE))

    style_buttons = []
    current_style = db_manager.get_user_bot_style(user_id) # Получаем текущий стиль
    for style_code, style_name in BOT_STYLES.items():
        # Отмечаем текущий стиль
        button_text = f"✅ {style_name}" if style_code == current_style else style_name
        style_buttons.append(types.InlineKeyboardButton(button_text, callback_data=f'{CALLBACK_SETTINGS_STYLE_PREFIX}{style_code}'))
    # Добавляем кнопки стилей по 2 в ряд
    for i in range(0, len(style_buttons), 2):
         if i + 1 < len(style_buttons):
             markup.add(style_buttons[i], style_buttons[i+1])
         else:
             markup.add(style_buttons[i])

    # --- Настройки часового пояса ---
    markup.add(types.InlineKeyboardButton("--- Часовой пояс ---", callback_data=CALLBACK_IGNORE))
    current_timezone = db_manager.get_user_timezone(user_id)
    if current_timezone:
        # Показываем текущий пояс и кнопку для изменения
        markup.add(types.InlineKeyboardButton(f"Текущий: {current_timezone}", callback_data=CALLBACK_IGNORE))
        markup.add(types.InlineKeyboardButton("Изменить часовой пояс", callback_data=CALLBACK_SETTINGS_SET_TIMEZONE_PREFIX))
    else:
        # Предлагаем установить пояс
        markup.add(types.InlineKeyboardButton("Установить часовой пояс", callback_data=CALLBACK_SETTINGS_SET_TIMEZONE_PREFIX))
        # Предлагаем определить по геолокации
        markup.add(types.InlineKeyboardButton("📍 Определить по геолокации", callback_data=CALLBACK_SETTINGS_DETECT_TIMEZONE))


    # Можно добавить другие настройки сюда, если появятся
    # markup.add(types.InlineKeyboardButton("--- Другие настройки ---", callback_data=CALLBACK_IGNORE))
    # markup.add(types.InlineKeyboardButton("Другая настройка", callback_data="other_setting"))

    # Кнопка для возврата в главное меню (опционально)
    # markup.add(types.InlineKeyboardButton("<< Назад", callback_data="back_to_main"))

    return markup


def create_calendar_keyboard(year: Optional[int] = None, month: Optional[int] = None, disable_past: bool = True) -> types.InlineKeyboardMarkup:
    """
    Создает inline-клавиатуру с календарем для выбора даты.

    Args:
        year (Optional[int]): Год для отображения (по умолчанию текущий).
        month (Optional[int]): Месяц для отображения (по умолчанию текущий).
        disable_past (bool): Делать ли прошедшие даты неактивными (для напоминаний).
                               По умолчанию True. Для истории можно ставить False.
    """
    now = datetime.datetime.now()
    year = year or now.year
    month = month or now.month

    markup = types.InlineKeyboardMarkup(row_width=7)

    # --- Заголовок - Месяц Год ---
    # Используем английские названия месяцев + год для простоты и универсальности
    try:
        month_name = datetime.date(year, month, 1).strftime("%B %Y")
    except ValueError: # Если год/месяц некорректны
        logger.warning(f"Некорректные год ({year}) или месяц ({month}) переданы в create_calendar_keyboard.")
        # Возвращаем к текущему месяцу
        year, month = now.year, now.month
        month_name = datetime.date(year, month, 1).strftime("%B %Y")

    markup.row(types.InlineKeyboardButton(month_name, callback_data=CALLBACK_IGNORE))

    # --- Дни недели ---
    days_of_week = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"] # Английские сокращения
    markup.row(*[types.InlineKeyboardButton(day, callback_data=CALLBACK_IGNORE) for day in days_of_week])

    # --- Кнопки дней месяца ---
    try:
        first_day_of_month = datetime.date(year, month, 1)
        # Правильное определение последнего дня месяца
        if month == 12:
            last_day_of_month = datetime.date(year, 12, 31)
        else:
            last_day_of_month = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

        # Пустые кнопки до первого дня месяца
        first_day_weekday = first_day_of_month.weekday() # 0 = Пн, 6 = Вс
        row_buttons = [types.InlineKeyboardButton(" ", callback_data=CALLBACK_IGNORE)] * first_day_weekday

        # Добавляем кнопки дней
        for day_num in range(1, last_day_of_month.day + 1):
            current_date = datetime.date(year, month, day_num)
            # Проверяем, активна ли дата
            is_selectable = True
            if disable_past and current_date < now.date():
                is_selectable = False

            # Формируем текст и callback_data
            button_text = str(day_num)
            callback_value = f"{CALLBACK_CALENDAR_DATE_PREFIX}{current_date.strftime('%Y-%m-%d')}" if is_selectable else CALLBACK_IGNORE
            if not is_selectable:
                 button_text = f"·{day_num}·" # Помечаем неактивные дни точками

            row_buttons.append(types.InlineKeyboardButton(button_text, callback_data=callback_value))

            # Если ряд заполнен (7 дней), добавляем его в разметку
            if len(row_buttons) == 7:
                markup.row(*row_buttons)
                row_buttons = []

        # Добиваем последнюю строку пустыми кнопками, если нужно
        if row_buttons:
            row_buttons.extend([types.InlineKeyboardButton(" ", callback_data=CALLBACK_IGNORE)] * (7 - len(row_buttons)))
            markup.row(*row_buttons)

    except ValueError as date_err:
         logger.error(f"Ошибка генерации дней календаря для {year}-{month}: {date_err}")
         markup.row(types.InlineKeyboardButton("Ошибка генерации календаря", callback_data=CALLBACK_IGNORE))


    # --- Кнопки навигации по месяцам ---
    nav_buttons = []
    try:
        # Предыдущий месяц
        prev_month_date = first_day_of_month - datetime.timedelta(days=1)
        # Следующий месяц
        next_month_date = last_day_of_month + datetime.timedelta(days=1)

        # Кнопка "Предыдущий месяц"
        # Показываем, только если он не раньше текущего месяца (если disable_past=True)
        can_go_back = True
        if disable_past and (prev_month_date.year < now.year or (prev_month_date.year == now.year and prev_month_date.month < now.month)):
             can_go_back = False

        if can_go_back:
             nav_buttons.append(
                 types.InlineKeyboardButton("⬅️ Назад", callback_data=f"{CALLBACK_CALENDAR_MONTH_PREFIX}{prev_month_date.year}-{prev_month_date.month}")
             )
        else:
             nav_buttons.append(types.InlineKeyboardButton(" ", callback_data=CALLBACK_IGNORE)) # Пустая кнопка для выравнивания

        # Пустая кнопка для центрирования
        nav_buttons.append(types.InlineKeyboardButton(" ", callback_data=CALLBACK_IGNORE))

        # Кнопка "Следующий месяц" (всегда доступна)
        nav_buttons.append(
             types.InlineKeyboardButton("Вперед ➡️", callback_data=f"{CALLBACK_CALENDAR_MONTH_PREFIX}{next_month_date.year}-{next_month_date.month}")
        )
        markup.row(*nav_buttons)

    except Exception as nav_err:
         logger.error(f"Ошибка генерации навигации календаря: {nav_err}")

    return markup


def create_reminders_keyboard(reminders: List[Dict[str, Any]]) -> types.InlineKeyboardMarkup:
    """Создает inline-клавиатуру для управления напоминаниями."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    # Кнопка добавления всегда сверху
    markup.add(types.InlineKeyboardButton("➕ Добавить напоминание", callback_data=f"{CALLBACK_SET_REMINDER_PREFIX}new"))

    if reminders:
        markup.add(types.InlineKeyboardButton("--- Активные напоминания ---", callback_data=CALLBACK_IGNORE))
        # Сортируем напоминания по времени (хотя они должны приходить уже отсортированными из БД)
        sorted_reminders = sorted(reminders, key=lambda r: r.get('reminder_time', ''))

        for reminder in sorted_reminders:
            try:
                reminder_id = reminder.get('reminder_id')
                reminder_text = reminder.get('reminder_text', 'Без текста')
                reminder_time_str = reminder.get('reminder_time')

                if not reminder_id or not reminder_time_str:
                     logger.warning(f"Неполные данные для напоминания в списке: {reminder}. Пропускаем.")
                     continue

                # Парсим время из ISO строки UTC
                reminder_time_dt_utc = datetime.datetime.fromisoformat(reminder_time_str.replace('Z', '+00:00'))

                # Форматируем для отображения (показываем UTC)
                time_str = reminder_time_dt_utc.strftime("%d.%m.%y %H:%M UTC")

                # Обрезаем текст напоминания для кнопки
                text_preview = reminder_text[:25] + '...' if len(reminder_text) > 25 else reminder_text

                markup.add(
                    types.InlineKeyboardButton(
                        f"🗑️ {time_str} - {text_preview}", # Значок корзины намекает на удаление
                        callback_data=f"{CALLBACK_DELETE_REMINDER_PREFIX}{reminder_id}"
                    )
                )
            except Exception as e:
                # Логируем ошибку парсинга или форматирования для конкретного напоминания
                reminder_id_log = reminder.get('reminder_id', 'N/A')
                logger.error(f"Ошибка обработки данных напоминания ID {reminder_id_log} для клавиатуры: {e}")
                markup.add(types.InlineKeyboardButton(f"⚠️ Ошибка данных напоминания ID {reminder_id_log}", callback_data=CALLBACK_IGNORE))
    else:
        markup.add(types.InlineKeyboardButton("У вас пока нет активных напоминаний.", callback_data=CALLBACK_IGNORE))

    return markup


def create_timezone_request_keyboard() -> types.ReplyKeyboardMarkup:
    """Создает клавиатуру с запросом геолокации для установки таймзоны."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True) # Скрывается после нажатия
    button_location = types.KeyboardButton("📍 Отправить мою геолокацию", request_location=True)
    markup.add(button_location)
    # Можно добавить кнопку "Отмена" или "Ввести вручную"
    markup.add(types.KeyboardButton("🚫 Отмена"))
    return markup


def create_error_report_button() -> types.InlineKeyboardMarkup:
    """Создает inline-клавиатуру с кнопкой 'Сообщить об ошибке'."""
    markup = types.InlineKeyboardMarkup()
    btn_report_error = types.InlineKeyboardButton('🆘 Сообщить об ошибке', callback_data=CALLBACK_REPORT_ERROR)
    markup.add(btn_report_error)
    return markup

# --- END OF FILE utils/markup_helpers.py ---