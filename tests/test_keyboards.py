import pytest
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup
from config.settings import ADMIN_USER_ID
from utils import localization as loc
from keyboards.aiogram_reply import create_main_keyboard
from keyboards.aiogram_inline import (
    get_chat_quick_actions_keyboard, get_streaming_stop_keyboard,
    get_settings_keyboard, get_header_style_keyboard,
    get_format_keyboard, get_thinking_budget_keyboard,
    get_translation_keyboard, create_calendar_keyboard,
    get_dialogs_keyboard, get_confirm_delete_dialog_keyboard
)


def test_main_reply_keyboard_regular_user():
    """Verify regular user gets 3 rows with 8 buttons."""
    # Use non-admin ID
    regular_id = 999999999 if ADMIN_USER_ID != 999999999 else 888888888
    kb = create_main_keyboard(lang_code="ru", user_id=regular_id)
    assert isinstance(kb, ReplyKeyboardMarkup)
    assert len(kb.keyboard) == 3

    # Row 1: [🗂️ Диалоги] [👤 Личный кабинет]
    assert len(kb.keyboard[0]) == 2
    assert kb.keyboard[0][0].text == "🗂️ Диалоги"
    assert kb.keyboard[0][1].text == "👤 Личный кабинет"

    # Row 2: [📊 Расходы] [⚙️ Настройки] [🇷🇺 Перевести]
    assert len(kb.keyboard[1]) == 3
    assert kb.keyboard[1][0].text == "📊 Расходы"
    assert kb.keyboard[1][1].text == "⚙️ Настройки"
    assert kb.keyboard[1][2].text == "🇷🇺 Перевести"

    # Row 3: [📜 История] [❓ Помощь] [🔄 Сброс]
    assert len(kb.keyboard[2]) == 3
    assert kb.keyboard[2][0].text == "📜 История"
    assert kb.keyboard[2][1].text == "❓ Помощь"
    assert kb.keyboard[2][2].text == "🔄 Сброс"


def test_main_reply_keyboard_admin_user():
    """Verify admin gets 3 rows with 9 buttons (Row 1 starts with Admin Panel)."""
    if ADMIN_USER_ID is None:
        pytest.skip("ADMIN_USER_ID is not configured in environment")

    kb = create_main_keyboard(lang_code="ru", user_id=ADMIN_USER_ID)
    assert isinstance(kb, ReplyKeyboardMarkup)
    assert len(kb.keyboard) == 3

    # Row 1: [👑 Админ-панель] [🗂️ Диалоги] [👤 Личный кабинет]
    assert len(kb.keyboard[0]) == 3
    assert kb.keyboard[0][0].text == "👑 Админ-панель"
    assert kb.keyboard[0][1].text == "🗂️ Диалоги"
    assert kb.keyboard[0][2].text == "👤 Личный кабинет"

    # Total buttons: 9 (3x3 grid)
    total_buttons = sum(len(row) for row in kb.keyboard)
    assert total_buttons == 9


def test_inline_quick_actions_and_stop():
    """Verify quick actions and stop keyboard buttons."""
    quick_kb = get_chat_quick_actions_keyboard(lang_code="ru", dialog_id=42)
    assert isinstance(quick_kb, InlineKeyboardMarkup)
    assert any("chat_action:regen" in btn.callback_data for row in quick_kb.inline_keyboard for btn in row)
    assert any("chat_action:undo" in btn.callback_data for row in quick_kb.inline_keyboard for btn in row)
    assert any("dialog_export:42" in btn.callback_data for row in quick_kb.inline_keyboard for btn in row)

    stop_kb = get_streaming_stop_keyboard(lang_code="ru")
    assert any(btn.callback_data == "chat_action:stop" for row in stop_kb.inline_keyboard for btn in row)


def test_inline_settings_and_header_style():
    """Verify settings and header style switches."""
    settings_kb = get_settings_keyboard(
        current_model="gemini-2.5-flash",
        current_style="default",
        current_persona="default",
        has_api_key=True,
        lang_code="ru",
        current_format="rich",
        current_header_style="blockquote",
        current_thinking_budget=1024,
        code_execution_enabled=True,
        google_search_enabled=False
    )
    callbacks = [btn.callback_data for row in settings_kb.inline_keyboard for btn in row if btn.callback_data]
    assert "settings_models" in callbacks
    assert "settings_personas" in callbacks
    assert "settings_thinking" in callbacks
    assert "settings_toggle_code_exec" in callbacks
    assert "settings_toggle_search" in callbacks
    assert "settings_format" in callbacks
    assert "settings_header" in callbacks

    # Header style keyboard
    hdr_kb = get_header_style_keyboard(current_style="blockquote", lang_code="ru")
    hdr_callbacks = [btn.callback_data for row in hdr_kb.inline_keyboard for btn in row]
    assert "set_header_style:blockquote" in hdr_callbacks
    assert "set_header_style:expandable" in hdr_callbacks
    assert "set_header_style:hidden" in hdr_callbacks

    # Format keyboard
    fmt_kb = get_format_keyboard(current_format="rich", lang_code="ru")
    fmt_callbacks = [btn.callback_data for row in fmt_kb.inline_keyboard for btn in row]
    assert "set_format:rich" in fmt_callbacks
    assert "set_format:classic" in fmt_callbacks

    # Thinking budget keyboard
    tb_kb = get_thinking_budget_keyboard(current_budget=1024, lang_code="ru")
    tb_callbacks = [btn.callback_data for row in tb_kb.inline_keyboard for btn in row]
    assert "set_thinking:0" in tb_callbacks
    assert "set_thinking:1024" in tb_callbacks
    assert "set_thinking:4096" in tb_callbacks


def test_model_selection_pagination_keyboard():
    """Verify model selection keyboard has pagination arrows and full models list."""
    from keyboards.aiogram_inline import get_model_selection_keyboard

    dummy_models = [
        {"id": f"gemini-test-{i}", "name": f"models/gemini-test-{i}", "display_name": f"Test Model {i}"}
        for i in range(20)
    ]

    # Page 0 (first page of 3 pages with 8 per page)
    kb_p0 = get_model_selection_keyboard(dummy_models, current_model="gemini-test-0", page=0, page_size=8)
    callbacks_p0 = [btn.callback_data for row in kb_p0.inline_keyboard for btn in row]
    texts_p0 = [btn.text for row in kb_p0.inline_keyboard for btn in row]

    assert "settings_model:gemini-test-0" in callbacks_p0
    assert "models_page:1" in callbacks_p0
    assert any("1 / 3" in t for t in texts_p0)

    # Page 1 (middle page)
    kb_p1 = get_model_selection_keyboard(dummy_models, current_model="gemini-test-0", page=1, page_size=8)
    callbacks_p1 = [btn.callback_data for row in kb_p1.inline_keyboard for btn in row]
    assert "models_page:0" in callbacks_p1
    assert "models_page:2" in callbacks_p1

    # Page 2 (last page)
    kb_p2 = get_model_selection_keyboard(dummy_models, current_model="gemini-test-0", page=2, page_size=8)
    callbacks_p2 = [btn.callback_data for row in kb_p2.inline_keyboard for btn in row]
    assert "models_page:1" in callbacks_p2
    assert "models_page:3" not in callbacks_p2


def test_main_reply_keyboard_english():
    """Verify English reply keyboard layout and button texts."""
    regular_id = 999999999 if ADMIN_USER_ID != 999999999 else 888888888
    kb = create_main_keyboard(lang_code="en", user_id=regular_id)
    assert isinstance(kb, ReplyKeyboardMarkup)
    assert len(kb.keyboard) == 3

    # Row 1: [🗂️ Dialogs] [👤 My Account]
    assert kb.keyboard[0][0].text == "🗂️ Dialogs"
    assert kb.keyboard[0][1].text == "👤 My Account"

    # Row 2: [📊 Usage] [⚙️ Settings] [🇬🇧 Translate]
    assert kb.keyboard[1][0].text == "📊 Usage"
    assert kb.keyboard[1][1].text == "⚙️ Settings"
    assert kb.keyboard[1][2].text == "🇬🇧 Translate"

    # Row 3: [📜 History] [❓ Help] [🔄 Reset]
    assert kb.keyboard[2][0].text == "📜 History"
    assert kb.keyboard[2][1].text == "❓ Help"
    assert kb.keyboard[2][2].text == "🔄 Reset"


def test_thinking_budget_keyboard_bilingual():
    """Verify thinking budget labels in both RU and EN."""
    ru_kb = get_thinking_budget_keyboard(current_budget=1024, lang_code="ru")
    ru_texts = [btn.text for row in ru_kb.inline_keyboard for btn in row]
    assert any("Мгновенно" in t for t in ru_texts)
    assert any("Баланс" in t for t in ru_texts)
    assert any("Глубокий анализ" in t for t in ru_texts)

    en_kb = get_thinking_budget_keyboard(current_budget=1024, lang_code="en")
    en_texts = [btn.text for row in en_kb.inline_keyboard for btn in row]
    assert any("Instant" in t for t in en_texts)
    assert any("Balanced" in t for t in en_texts)
    assert any("Deep Analysis" in t for t in en_texts)


def test_calendar_keyboard_navigation_and_localization():
    """Verify history calendar keyboard navigation buttons and Russian/English localization."""
    # Russian October 2026
    cal_ru = create_calendar_keyboard(year=2026, month=10, lang_code="ru")
    assert isinstance(cal_ru, InlineKeyboardMarkup)

    row1 = cal_ru.inline_keyboard[0]
    assert len(row1) == 3
    assert row1[0].text == "◀️"
    assert row1[0].callback_data == "calendar_month:2026-9"
    assert "Октябрь 2026" in row1[1].text
    assert row1[2].text == "▶️"
    assert row1[2].callback_data == "calendar_month:2026-11"

    # Weekdays row
    row2_ru = [b.text for b in cal_ru.inline_keyboard[1]]
    assert row2_ru == ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    # Close button row
    last_row_ru = cal_ru.inline_keyboard[-1]
    assert last_row_ru[0].text == "❌ Закрыть"
    assert last_row_ru[0].callback_data == "calendar_cancel"

    # Year crossing: January 2026 -> previous month should be 2025-12
    cal_jan = create_calendar_keyboard(year=2026, month=1, lang_code="en")
    assert cal_jan.inline_keyboard[0][0].callback_data == "calendar_month:2025-12"
    assert "January 2026" in cal_jan.inline_keyboard[0][1].text
    assert cal_jan.inline_keyboard[0][2].callback_data == "calendar_month:2026-2"

    # English weekdays & close
    row2_en = [b.text for b in cal_jan.inline_keyboard[1]]
    assert row2_en == ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    assert cal_jan.inline_keyboard[-1][0].text == "❌ Close"



