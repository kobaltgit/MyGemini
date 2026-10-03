"""
Inline keyboards for MyGemini (aiogram 3.x).
Supports full settings menu, header style switcher, format switcher, thinking budget,
dialog actions, calendar, quick actions and admin panel.
"""

import datetime
from typing import List, Optional, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import (
    BOT_STYLES, BOT_PERSONAS, TRANSLATE_LANGUAGES, DONATION_URL,
    CALLBACK_IGNORE, CALLBACK_SETTINGS_STYLE_PREFIX, CALLBACK_LANG_PREFIX,
    CALLBACK_SETTINGS_LANG_PREFIX, CALLBACK_SETTINGS_SET_API_KEY,
    CALLBACK_SETTINGS_CHOOSE_MODEL_MENU, CALLBACK_SETTINGS_MODEL_PREFIX,
    CALLBACK_SETTINGS_BACK_TO_MAIN, CALLBACK_SETTINGS_PERSONA_PREFIX,
    CALLBACK_SETTINGS_PERSONA_MENU,
    CALLBACK_DIALOGS_MENU, CALLBACK_DIALOG_SWITCH_PREFIX, CALLBACK_DIALOG_RENAME_PREFIX,
    CALLBACK_DIALOG_DELETE_PREFIX, CALLBACK_DIALOG_CREATE, CALLBACK_DIALOG_CONFIRM_DELETE_PREFIX,
    CALLBACK_ADMIN_MAIN_MENU, CALLBACK_ADMIN_STATS_MENU, CALLBACK_ADMIN_COMMUNICATION_MENU,
    CALLBACK_ADMIN_USER_MANAGEMENT_MENU, CALLBACK_ADMIN_MAINTENANCE_MENU,
    CALLBACK_ADMIN_TOGGLE_MAINTENANCE, CALLBACK_ADMIN_BROADCAST,
    CALLBACK_ADMIN_CONFIRM_BROADCAST, CALLBACK_ADMIN_CANCEL_BROADCAST,
    CALLBACK_ADMIN_EXPORT_USERS, CALLBACK_CALENDAR_MONTH_PREFIX
)
from utils import localization as loc


def get_chat_quick_actions_keyboard(
    lang_code: str = "ru", dialog_id: Optional[int] = None, enable_code_execution: bool = True
) -> InlineKeyboardMarkup:
    """Action buttons under completed AI response."""
    regen_label = "🔄 Еще раз" if lang_code == "ru" else "🔄 Retry"
    undo_label = "↩️ Откатить шаг" if lang_code == "ru" else "↩️ Undo turn"
    sandbox_label = "🐍 В песочницу" if lang_code == "ru" else "🐍 To Sandbox"
    export_label = "📥 Экспорт в .md" if lang_code == "ru" else "📥 Export .md"
    export_cb = f"dialog_export:{dialog_id}" if dialog_id else "chat_action:export"

    row2 = []
    if enable_code_execution:
        row2.append(InlineKeyboardButton(text=sandbox_label, callback_data="chat_action:sandbox"))
    row2.append(InlineKeyboardButton(text=export_label, callback_data=export_cb))

    buttons = [
        [
            InlineKeyboardButton(text=regen_label, callback_data="chat_action:regen"),
            InlineKeyboardButton(text=undo_label, callback_data="chat_action:undo"),
        ],
        row2
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_sandbox_cancel_keyboard(lang_code: str = "ru") -> InlineKeyboardMarkup:
    """Builds cancel button for dedicated Python sandbox prompt mode."""
    cancel_text = "❌ Отмена" if lang_code == "ru" else "❌ Cancel"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cancel_text, callback_data="chat_action:sandbox_cancel")]
    ])


def get_streaming_stop_keyboard(lang_code: str = "ru") -> InlineKeyboardMarkup:
    """Button to interrupt live generation stream."""
    stop_label = "⏹️ Стоп" if lang_code == "ru" else "⏹️ Stop"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=stop_label, callback_data="chat_action:stop")]
    ])


def get_settings_keyboard(
    current_model: str,
    current_style: str,
    current_persona: str,
    has_api_key: bool,
    lang_code: str = "ru",
    current_format: str = "rich",
    current_header_style: str = "blockquote",
    current_thinking_budget: int = 1024,
    code_execution_enabled: bool = False,
    google_search_enabled: bool = False,
) -> InlineKeyboardMarkup:
    """Builds complete settings keyboard."""
    if lang_code == "ru":
        key_status = "✅ Установлен" if has_api_key else "❌ Не установлен"
        key_label = f"🔑 API-ключ ({key_status})"
        model_label = f"🤖 Модель: {current_model}"
        persona_info = BOT_PERSONAS.get(current_persona, BOT_PERSONAS.get("default", {}))
        persona_name = persona_info.get("name_ru", current_persona)
        persona_label = f"🎭 Персона: {persona_name}"
        style_name = BOT_STYLES.get(current_style, current_style)
        style_label = f"🎨 Стиль: {style_name}"

        if current_thinking_budget == 0:
            thinking_label = "🧠 Размышления: ⚡ Мгновенно (0)"
        elif current_thinking_budget == 4096:
            thinking_label = "🧠 Размышления: 🔬 Глубокий (4096)"
        else:
            thinking_label = "🧠 Размышления: ⚖️ Баланс (1024)"

        code_exec_status = "🟢 Вкл" if code_execution_enabled else "🔴 Выкл"
        code_exec_label = f"🐍 Песочница Python: {code_exec_status}"

        search_status = "🟢 Вкл" if google_search_enabled else "🔴 Выкл"
        search_label = f"🌐 Поиск Google: {search_status}"

        format_label = "⚡ Формат: Rich (10.1+)" if current_format == "rich" else "📝 Формат: Классический"
        if current_header_style == "expandable":
            header_label = "📌 Шапка: 🔽 Под спойлером"
        elif current_header_style == "hidden":
            header_label = "📌 Шапка: 🚫 Скрыта"
        else:
            header_label = "📌 Шапка: ▎ Цитата"

        lang_label = "🌐 Язык: 🇷🇺 Русский"
        back_label = "⬅️ Главное меню"
    else:
        key_status = "✅ Set" if has_api_key else "❌ Not set"
        key_label = f"🔑 API Key ({key_status})"
        model_label = f"🤖 Model: {current_model}"
        persona_info = BOT_PERSONAS.get(current_persona, BOT_PERSONAS.get("default", {}))
        persona_name = persona_info.get("name_en", current_persona)
        persona_label = f"🎭 Persona: {persona_name}"
        style_name = BOT_STYLES.get(current_style, current_style)
        style_label = f"🎨 Style: {style_name}"

        if current_thinking_budget == 0:
            thinking_label = "🧠 Thinking: ⚡ Instant (0)"
        elif current_thinking_budget == 4096:
            thinking_label = "🧠 Thinking: 🔬 Deep (4096)"
        else:
            thinking_label = "🧠 Thinking: ⚖️ Balanced (1024)"

        code_exec_status = "🟢 On" if code_execution_enabled else "🔴 Off"
        code_exec_label = f"🐍 Python Sandbox: {code_exec_status}"

        search_status = "🟢 On" if google_search_enabled else "🔴 Off"
        search_label = f"🌐 Google Search: {search_status}"

        format_label = "⚡ Format: Rich (10.1+)" if current_format == "rich" else "📝 Format: Classic"
        if current_header_style == "expandable":
            header_label = "📌 Header: 🔽 Under spoiler"
        elif current_header_style == "hidden":
            header_label = "📌 Header: 🚫 Hidden"
        else:
            header_label = "📌 Header: ▎ Blockquote"

        lang_label = "🌐 Language: 🇬🇧 English"
        back_label = "⬅️ Main Menu"

    buttons = [
        [InlineKeyboardButton(text=model_label, callback_data="settings_models")],
        [InlineKeyboardButton(text=persona_label, callback_data="settings_personas")],
        [InlineKeyboardButton(text=style_label, callback_data="settings_styles")],
        [InlineKeyboardButton(text=thinking_label, callback_data="settings_thinking")],
        [InlineKeyboardButton(text=code_exec_label, callback_data="settings_toggle_code_exec")],
        [InlineKeyboardButton(text=search_label, callback_data="settings_toggle_search")],
        [InlineKeyboardButton(text=format_label, callback_data="settings_format")],
        [InlineKeyboardButton(text=header_label, callback_data="settings_header")],
        [InlineKeyboardButton(text=key_label, callback_data="settings_api_key")],
        [InlineKeyboardButton(text=lang_label, callback_data="settings_language")],
        [InlineKeyboardButton(text=back_label, callback_data="back_to_main")],
    ]
    if DONATION_URL:
        support_label = "❤️ " + loc.get_text('btn_support', lang_code)
        buttons.insert(-1, [InlineKeyboardButton(text=support_label, url=DONATION_URL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_header_style_keyboard(current_style: str = "blockquote", lang_code: str = "ru") -> InlineKeyboardMarkup:
    """Builds header style selection keyboard (Blockquote vs Expandable spoiler vs Hidden)."""
    quote_check = "✅ " if current_style == "blockquote" else ""
    expand_check = "✅ " if current_style == "expandable" else ""
    hidden_check = "✅ " if current_style == "hidden" else ""
    back_label = "⬅️ Назад в настройки" if lang_code == "ru" else "⬅️ Back to Settings"

    quote_text = f"{quote_check}▎ Открытая цитата (Вариант 1)" if lang_code == "ru" else f"{quote_check}▎ Standard Quote (Option 1)"
    expand_text = f"{expand_check}🔽 Сворачивать под спойлер" if lang_code == "ru" else f"{expand_check}🔽 Collapse Under Spoiler"
    hidden_text = f"{hidden_check}🚫 Скрыть шапку" if lang_code == "ru" else f"{hidden_check}🚫 Hide Header"

    buttons = [
        [InlineKeyboardButton(text=quote_text, callback_data="set_header_style:blockquote")],
        [InlineKeyboardButton(text=expand_text, callback_data="set_header_style:expandable")],
        [InlineKeyboardButton(text=hidden_text, callback_data="set_header_style:hidden")],
        [InlineKeyboardButton(text=back_label, callback_data="menu_settings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_format_keyboard(current_format: str = "rich", lang_code: str = "ru") -> InlineKeyboardMarkup:
    """Builds format selection keyboard (Rich vs Classic)."""
    rich_check = "✅ " if current_format == "rich" else ""
    classic_check = "✅ " if current_format == "classic" else ""
    back_label = "⬅️ Назад в настройки" if lang_code == "ru" else "⬅️ Back to Settings"

    rich_text = f"{rich_check}⚡ Rich Messages (10.1+)" if lang_code == "ru" else f"{rich_check}⚡ Rich Messages (10.1+)"
    classic_text = f"{classic_check}📝 Классический (Markdown)" if lang_code == "ru" else f"{classic_check}📝 Classic (Markdown)"

    buttons = [
        [InlineKeyboardButton(text=rich_text, callback_data="set_format:rich")],
        [InlineKeyboardButton(text=classic_text, callback_data="set_format:classic")],
        [InlineKeyboardButton(text=back_label, callback_data="menu_settings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_thinking_budget_keyboard(current_budget: int = 1024, lang_code: str = "ru") -> InlineKeyboardMarkup:
    """Builds thinking budget selector."""
    b0 = "✅ " if current_budget == 0 else ""
    b1024 = "✅ " if current_budget == 1024 else ""
    b4096 = "✅ " if current_budget == 4096 else ""
    back_label = "⬅️ Назад в настройки" if lang_code == "ru" else "⬅️ Back to Settings"

    if lang_code == "ru":
        t0 = f"{b0}⚡ Мгновенно (0)"
        t1024 = f"{b1024}⚖️ Баланс (1024)"
        t4096 = f"{b4096}🔬 Глубокий анализ (4096)"
    else:
        t0 = f"{b0}⚡ Instant (0)"
        t1024 = f"{b1024}⚖️ Balanced (1024)"
        t4096 = f"{b4096}🔬 Deep Analysis (4096)"

    buttons = [
        [InlineKeyboardButton(text=t0, callback_data="set_thinking:0")],
        [InlineKeyboardButton(text=t1024, callback_data="set_thinking:1024")],
        [InlineKeyboardButton(text=t4096, callback_data="set_thinking:4096")],
        [InlineKeyboardButton(text=back_label, callback_data="menu_settings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_model_selection_keyboard(
    models: List[Dict[str, Any]],
    current_model: str,
    page: int = 0,
    page_size: int = 8,
    lang_code: str = "ru"
) -> InlineKeyboardMarkup:
    """Builds model selection keyboard with dynamic pagination arrows."""
    total_models = len(models)
    total_pages = max(1, (total_models + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))

    start_idx = page * page_size
    end_idx = min(start_idx + page_size, total_models)
    page_models = models[start_idx:end_idx]

    rows = []
    for m in page_models:
        mid = m.get("id") or m.get("name", "")
        dname = m.get("display_name") or mid
        check = "✅ " if mid == current_model else ""
        rows.append([InlineKeyboardButton(text=f"{check}{dname}", callback_data=f"{CALLBACK_SETTINGS_MODEL_PREFIX}{mid}")])

    # Navigation pagination row if more than 1 page
    if total_pages > 1:
        prev_btn = InlineKeyboardButton(text="◀️", callback_data=f"models_page:{page - 1}") if page > 0 else InlineKeyboardButton(text="◀️", callback_data=CALLBACK_IGNORE)
        page_btn = InlineKeyboardButton(text=f"📄 {page + 1} / {total_pages}", callback_data=CALLBACK_IGNORE)
        next_btn = InlineKeyboardButton(text="▶️", callback_data=f"models_page:{page + 1}") if page < total_pages - 1 else InlineKeyboardButton(text="▶️", callback_data=CALLBACK_IGNORE)
        rows.append([prev_btn, page_btn, next_btn])

    back_label = "⬅️ Назад в настройки" if lang_code == "ru" else "⬅️ Back to Settings"
    rows.append([InlineKeyboardButton(text=back_label, callback_data="menu_settings")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_language_keyboard(current_lang: str = "ru", lang_code: str = "ru") -> InlineKeyboardMarkup:
    """Builds interface language selector."""
    ru_check = "✅ " if current_lang == "ru" else ""
    en_check = "✅ " if current_lang == "en" else ""
    back_label = "⬅️ Назад в настройки" if lang_code == "ru" else "⬅️ Back to Settings"

    buttons = [
        [InlineKeyboardButton(text=f"{ru_check}🇷🇺 Русский", callback_data=f"{CALLBACK_SETTINGS_LANG_PREFIX}ru")],
        [InlineKeyboardButton(text=f"{en_check}🇬🇧 English", callback_data=f"{CALLBACK_SETTINGS_LANG_PREFIX}en")],
        [InlineKeyboardButton(text=back_label, callback_data="menu_settings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_translation_keyboard() -> InlineKeyboardMarkup:
    """Builds target language keyboard for /translate."""
    buttons = []
    sorted_languages = sorted(TRANSLATE_LANGUAGES.items(), key=lambda item: item[1])
    for lang_code, lang_name in sorted_languages:
        buttons.append(InlineKeyboardButton(text=lang_name, callback_data=f"{CALLBACK_LANG_PREFIX}{lang_code}"))
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


MONTHS_RU = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
MONTHS_EN = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
DAYS_EN = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def create_calendar_keyboard(
    year: Optional[int] = None, month: Optional[int] = None, lang_code: str = "ru"
) -> InlineKeyboardMarkup:
    """Builds interactive calendar keyboard for history selection with month navigation."""
    now = datetime.datetime.now()
    year = year or now.year
    month = month or now.month

    # Normalize month underflow/overflow
    while month > 12:
        month -= 12
        year += 1
    while month < 1:
        month += 12
        year -= 1

    if lang_code == "ru":
        month_label = f"{MONTHS_RU[month]} {year}"
        days = DAYS_RU
        close_text = "❌ Закрыть"
    else:
        month_label = f"{MONTHS_EN[month]} {year}"
        days = DAYS_EN
        close_text = "❌ Close"

    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)

    # Row 1: [ ◀️ ] [ Month Year ] [ ▶️ ]
    rows = [
        [
            InlineKeyboardButton(text="◀️", callback_data=f"{CALLBACK_CALENDAR_MONTH_PREFIX}{prev_y}-{prev_m}"),
            InlineKeyboardButton(text=month_label, callback_data=CALLBACK_IGNORE),
            InlineKeyboardButton(text="▶️", callback_data=f"{CALLBACK_CALENDAR_MONTH_PREFIX}{next_y}-{next_m}"),
        ],
        # Row 2: Days of week
        [InlineKeyboardButton(text=day, callback_data=CALLBACK_IGNORE) for day in days],
    ]

    first_day = datetime.date(year, month, 1)
    if month == 12:
        last_day = 31
    else:
        last_day = (datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)).day

    row = [InlineKeyboardButton(text=" ", callback_data=CALLBACK_IGNORE)] * first_day.weekday()
    for day_num in range(1, last_day + 1):
        d_str = f"{year:04d}-{month:02d}-{day_num:02d}"
        row.append(InlineKeyboardButton(text=str(day_num), callback_data=f"calendar_date:{d_str}"))
        if len(row) == 7:
            rows.append(row)
            row = []
    if row:
        while len(row) < 7:
            row.append(InlineKeyboardButton(text=" ", callback_data=CALLBACK_IGNORE))
        rows.append(row)

    # Row N: Close button
    rows.append([InlineKeyboardButton(text=close_text, callback_data="calendar_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_dialogs_keyboard(dialogs: List[Dict[str, Any]], active_dialog_id: Optional[int], lang_code: str = "ru") -> InlineKeyboardMarkup:
    """Builds dialog management keyboard."""
    rows = []
    for d in dialogs:
        did = d['dialog_id']
        is_active = (did == active_dialog_id)
        name = f"✅ {d['name']}" if is_active else d['name']
        switch_cb = CALLBACK_IGNORE if is_active else f"{CALLBACK_DIALOG_SWITCH_PREFIX}{did}"
        d_btn = InlineKeyboardButton(text=name, callback_data=switch_cb)
        ren_btn = InlineKeyboardButton(text="✏️", callback_data=f"{CALLBACK_DIALOG_RENAME_PREFIX}{did}")
        exp_btn = InlineKeyboardButton(text="📥", callback_data=f"dialog_export:{did}")
        if not is_active:
            del_btn = InlineKeyboardButton(text="❌", callback_data=f"{CALLBACK_DIALOG_DELETE_PREFIX}{did}")
            rows.append([d_btn, ren_btn, exp_btn, del_btn])
        else:
            rows.append([d_btn, ren_btn, exp_btn])

    create_label = "➕ " + loc.get_text('btn_create_dialog', lang_code)
    rows.append([InlineKeyboardButton(text=create_label, callback_data=CALLBACK_DIALOG_CREATE)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_confirm_delete_dialog_keyboard(dialog_id: int, lang_code: str = "ru") -> InlineKeyboardMarkup:
    """Confirm dialog deletion."""
    confirm_label = loc.get_text('btn_confirm_delete', lang_code)
    cancel_label = loc.get_text('btn_cancel_delete', lang_code)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=confirm_label, callback_data=f"{CALLBACK_DIALOG_CONFIRM_DELETE_PREFIX}{dialog_id}"),
            InlineKeyboardButton(text=cancel_label, callback_data=CALLBACK_DIALOGS_MENU),
        ]
    ])


def get_close_button(lang_code: str = "ru") -> InlineKeyboardButton:
    """Builds a standardized close button."""
    text = "❌ Закрыть" if lang_code == "ru" else "❌ Close"
    return InlineKeyboardButton(text=text, callback_data="close_menu")


def get_cancel_keyboard(callback_data: str = "menu_admin", lang_code: str = "ru") -> InlineKeyboardMarkup:
    """Standardized cancel button keyboard."""
    cancel_text = "❌ Отмена" if lang_code == "ru" else "❌ Cancel"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cancel_text, callback_data=callback_data)]
    ])


def get_admin_keyboard(is_maintenance: bool = False, lang_code: str = "ru") -> InlineKeyboardMarkup:
    """Builds administrative control panel keyboard."""
    m_status = ("🔴 Выключить" if is_maintenance else "🟢 Включить") if lang_code == "ru" else ("🔴 Disable" if is_maintenance else "🟢 Enable")
    stats_text = "📊 Статистика активности" if lang_code == "ru" else "📊 Activity Stats"
    users_text = "👥 Список пользователей" if lang_code == "ru" else "👥 Users List"
    export_text = "📥 Экспорт в CSV (с BOM)" if lang_code == "ru" else "📥 Export CSV (BOM)"
    broadcast_text = "📢 Рассылка сообщений" if lang_code == "ru" else "📢 Broadcast Message"
    maint_text = f"🛠 Режим обслуживания: {m_status}" if lang_code == "ru" else f"🛠 Maintenance: {m_status}"
    search_user_text = "🔍 Поиск пользователя" if lang_code == "ru" else "🔍 Search User by ID"
    back_text = "⬅️ В главное меню" if lang_code == "ru" else "⬅️ Main Menu"

    buttons = [
        [
            InlineKeyboardButton(text=stats_text, callback_data="admin_stats"),
            InlineKeyboardButton(text=users_text, callback_data="admin_users_list"),
        ],
        [
            InlineKeyboardButton(text=export_text, callback_data="admin_export_csv"),
            InlineKeyboardButton(text=broadcast_text, callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton(text=search_user_text, callback_data="admin_user_search"),
            InlineKeyboardButton(text=maint_text, callback_data="admin_toggle_maintenance"),
        ],
        [InlineKeyboardButton(text=back_text, callback_data="menu_admin_close"), get_close_button(lang_code)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_user_actions_keyboard(target_user_id: int, is_blocked: bool, lang_code: str = "ru") -> InlineKeyboardMarkup:
    """Keyboard for managing a specific user card in admin panel."""
    block_text = ("✅ Разблокировать" if is_blocked else "🚫 Заблокировать") if lang_code == "ru" else ("✅ Unblock" if is_blocked else "🚫 Block")
    reset_text = "🔑 Сбросить API-ключ" if lang_code == "ru" else "🔑 Reset API Key"
    reply_text = "✉️ Ответить пользователю" if lang_code == "ru" else "✉️ Reply to User"
    back_text = "⬅️ Назад в админку" if lang_code == "ru" else "⬅️ Back to Admin"

    buttons = [
        [
            InlineKeyboardButton(text=block_text, callback_data=f"admin_toggle_block:{target_user_id}"),
            InlineKeyboardButton(text=reset_text, callback_data=f"admin_reset_key:{target_user_id}"),
        ],
        [
            InlineKeyboardButton(text=reply_text, callback_data=f"admin_reply_user:{target_user_id}"),
        ],
        [InlineKeyboardButton(text=back_text, callback_data="menu_admin"), get_close_button(lang_code)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_extend_sub_keyboard(target_user_id: int, lang_code: str = "ru") -> InlineKeyboardMarkup:
    """Legacy helper for backward compatibility."""
    back = "⬅️ Назад к пользователю" if lang_code == "ru" else "⬅️ Back to User"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=back, callback_data=f"admin_user_card:{target_user_id}"), get_close_button(lang_code)]
    ])

