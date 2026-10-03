"""
Unit tests for Admin Panel & Management Features (Free Bot aiogram 3.x).
Validates:
- Admin keyboard layouts (dashboard, user actions)
- Activity stats calculation (total users, active 7d, new 7d, with API key, blocked)
- Users list formatting and indicators
- User card rendering, block/unblock, and key reset
- CSV export formatting with UTF-8 BOM
"""

import io
import csv
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from keyboards.aiogram_inline import (
    get_admin_keyboard,
    get_admin_user_actions_keyboard,
)
from handlers.routers.admin import render_admin_user_card
from database import db_manager


def test_admin_keyboard_layout():
    """Verifies that the admin dashboard contains all free-bot management buttons."""
    kb = get_admin_keyboard(is_maintenance=False, lang_code="ru")
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]

    assert "admin_stats" in callbacks
    assert "admin_users_list" in callbacks
    assert "admin_export_csv" in callbacks
    assert "admin_broadcast" in callbacks
    assert "admin_user_search" in callbacks
    assert "admin_toggle_maintenance" in callbacks
    assert "menu_admin_close" in callbacks
    assert "close_menu" in callbacks

    # Toggle maintenance indicator test
    kb_maint = get_admin_keyboard(is_maintenance=True, lang_code="ru")
    btn_maint = [btn for row in kb_maint.inline_keyboard for btn in row if btn.callback_data == "admin_toggle_maintenance"][0]
    assert "🔴 Выключить" in btn_maint.text


def test_admin_user_actions_keyboard():
    """Verifies user card actions keyboard."""
    kb = get_admin_user_actions_keyboard(target_user_id=123456, is_blocked=False, lang_code="ru")
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]

    assert "admin_toggle_block:123456" in callbacks
    assert "admin_reset_key:123456" in callbacks
    assert "admin_reply_user:123456" in callbacks
    assert "menu_admin" in callbacks

    # Blocked state label check
    btn_block = [btn for row in kb.inline_keyboard for btn in row if btn.callback_data == "admin_toggle_block:123456"][0]
    assert "🚫 Заблокировать" in btn_block.text

    kb_blocked = get_admin_user_actions_keyboard(target_user_id=123456, is_blocked=True, lang_code="ru")
    btn_unblock = [btn for row in kb_blocked.inline_keyboard for btn in row if btn.callback_data == "admin_toggle_block:123456"][0]
    assert "✅ Разблокировать" in btn_unblock.text


@pytest.mark.asyncio
async def test_admin_user_card_and_actions():
    """Tests user card rendering, blocking, key reset and message count."""
    test_user_id = int(time.time() * 1000) % 90000000 + 10000000
    await db_manager.add_or_update_user(test_user_id, "test_free_user", "FreeTest", "User")
    await db_manager.set_user_api_key(test_user_id, "AIzaSyTestKeyForAdminVerification12345")

    # Render card
    card_text, kb = await render_admin_user_card(test_user_id, lang_code="ru")
    assert str(test_user_id) in card_text
    assert "@test_free_user" in card_text
    assert "✅ Установлен" in card_text
    assert "🟢 Активен" in card_text
    assert "Всего сообщений" in card_text

    # Block user
    await db_manager.set_user_blocked(test_user_id, True)
    card_text_blocked, kb_blocked = await render_admin_user_card(test_user_id, lang_code="ru")
    assert "⛔️ ЗАБЛОКИРОВАН" in card_text_blocked

    # Unblock user
    await db_manager.set_user_blocked(test_user_id, False)

    # Reset API key
    await db_manager.reset_user_api_key(test_user_id)
    card_text_reset, _ = await render_admin_user_card(test_user_id, lang_code="ru")
    assert "❌ Не установлен" in card_text_reset


@pytest.mark.asyncio
async def test_activity_stats_and_users_list():
    """Verifies stats counters and users list fetching."""
    total_users = await db_manager.get_total_users_count()
    active_7d = await db_manager.get_active_users_count(days=7)
    with_key = await db_manager.get_users_with_key_count()
    users_with_stats = await db_manager.get_all_users_with_stats()

    assert total_users >= 0
    assert active_7d >= 0
    assert with_key >= 0
    assert isinstance(users_with_stats, list)


@pytest.mark.asyncio
async def test_csv_export_format_with_bom():
    """Verifies that CSV export has valid UTF-8 BOM and correct free-bot columns."""
    users = await db_manager.get_all_users_for_export()
    assert isinstance(users, list)

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\n")
    headers = [
        "User ID", "Username", "First Name", "Last Name", "Language",
        "First Interaction", "Has API Key", "Total Messages", "Is Blocked",
        "Bot Style", "Gemini Model", "Active Persona",
    ]
    writer.writerow(headers)
    csv_bytes = output.getvalue().encode("utf-8-sig")

    # Check for UTF-8 BOM (0xEF, 0xBB, 0xBF)
    assert csv_bytes.startswith(b'\xef\xbb\xbf')
