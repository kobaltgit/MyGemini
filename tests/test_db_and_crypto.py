import pytest
import sqlite3
import os
from config.settings import DATABASE_NAME
from utils import crypto_helpers
from database import db_manager


def test_crypto_helpers():
    """Verify encryption and decryption round-trip."""
    test_key = "AIzaSyFakeKeyForTesting1234567890"
    encrypted = crypto_helpers.encrypt_data(test_key)
    assert encrypted != test_key
    assert isinstance(encrypted, str)
    decrypted = crypto_helpers.decrypt_data(encrypted)
    assert decrypted == test_key


def test_db_migration_and_structure():
    """Verify database migration adds new columns safely without deleting users."""
    # Run sync setup
    db_manager.setup_database_sync()

    # Verify columns in users table
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    cols = {row['name'] for row in cursor.fetchall()}

    expected_cols = {
        'user_id', 'username', 'first_name', 'last_name',
        'bot_style', 'first_interaction_date', 'api_key',
        'language_code', 'gemini_model', 'active_persona',
        'active_dialog_id', 'is_blocked',
        'thinking_budget', 'enable_code_execution',
        'enable_google_search', 'header_style', 'message_format'
    }
    for col in expected_cols:
        assert col in cols, f"Missing column {col} in users table"

    # Verify user count
    cursor.execute("SELECT count(*) FROM users")
    user_count = cursor.fetchone()[0]
    assert user_count >= 1000, f"Expected at least 1000 users, found {user_count}"
    conn.close()


@pytest.mark.asyncio
async def test_db_user_settings_and_helpers():
    """Verify new async db helper methods."""
    # Fetch first user from DB
    users = await db_manager.get_all_user_ids()
    assert len(users) > 0
    test_uid = users[0]

    # Test settings read
    settings = await db_manager.get_user_settings(test_uid)
    assert settings is not None
    assert 'header_style' in settings
    assert 'message_format' in settings
    assert 'thinking_budget' in settings

    # Test header style update
    original_style = await db_manager.get_user_header_style(test_uid)
    await db_manager.set_user_header_style(test_uid, 'expandable')
    assert await db_manager.get_user_header_style(test_uid) == 'expandable'
    # Restore
    await db_manager.set_user_header_style(test_uid, original_style)

    # Test message format update
    original_fmt = await db_manager.get_user_message_format(test_uid)
    await db_manager.set_user_message_format(test_uid, 'classic')
    assert await db_manager.get_user_message_format(test_uid) == 'classic'
    # Restore
    await db_manager.set_user_message_format(test_uid, original_fmt)

    # Test thinking budget update
    original_budget = await db_manager.get_user_thinking_budget(test_uid)
    await db_manager.set_user_thinking_budget(test_uid, 4096)
    assert await db_manager.get_user_thinking_budget(test_uid) == 4096
    # Restore
    await db_manager.set_user_thinking_budget(test_uid, original_budget)
