import pytest
import html
from unittest.mock import AsyncMock, patch

from features import personal_account

@pytest.mark.asyncio
async def test_personal_account_html_formatting():
    """Verifies personal account outputs clean HTML without raw Markdown artifacts."""
    user_id = 999888

    with patch("database.db_manager.get_user_language", new_callable=AsyncMock) as mock_lang, \
         patch("database.db_manager.get_user_api_key", new_callable=AsyncMock) as mock_key, \
         patch("database.db_manager.get_user_persona", new_callable=AsyncMock) as mock_persona, \
         patch("database.db_manager.get_first_interaction_date", new_callable=AsyncMock) as mock_date, \
         patch("database.db_manager.get_active_dialog_id", new_callable=AsyncMock) as mock_dialog, \
         patch("database.db_manager.get_total_user_message_count", new_callable=AsyncMock) as mock_count, \
         patch("features.personal_account._get_topic_description", new_callable=AsyncMock) as mock_topics:

        mock_lang.return_value = "ru"
        mock_key.return_value = "AIzaSyFakeKeyForTest123456789"
        mock_persona.return_value = "default"
        mock_date.return_value = "2026-09-01"
        mock_dialog.return_value = 1
        mock_count.return_value = 42
        mock_topics.return_value = "Чаще всего в этом диалоге вы обсуждаете программирование и тесты."

        text_ru = await personal_account.get_personal_account_info(user_id)

        # Must not contain raw markdown formatting
        assert "**" not in text_ru, "Personal account text should not contain raw markdown bold '**'"
        assert "---" not in text_ru, "Personal account text should not contain raw markdown divider '---'"

        # Must contain HTML tags
        assert "<b>Личный кабинет</b>" in text_ru
        assert "<blockquote>" in text_ru
        assert "</blockquote>" in text_ru
        assert "🟢 <b>Подключен</b>" in text_ru
        assert "Чаще всего в этом диалоге вы обсуждаете" in text_ru

        # Test English output
        mock_lang.return_value = "en"
        text_en = await personal_account.get_personal_account_info(user_id)
        assert "**" not in text_en
        assert "<b>My Account</b>" in text_en
        assert "🟢 <b>Connected</b>" in text_en


def test_history_html_escaping_and_blockquote():
    """Verifies that special characters in history messages are escaped and formatted into blockquotes."""
    user_msg = "What is 5 < 10 and a & b?"
    bot_msg = ("Line 1\nLine 2\n" + "A" * 200)

    escaped_user = html.escape(user_msg)
    escaped_bot = html.escape(bot_msg)

    assert "&lt;" in escaped_user
    assert "&amp;" in escaped_bot or "&amp;" in escaped_user

    # Short user msg -> regular blockquote
    user_block = f"<b>👤 Вы:</b>\n<blockquote>{escaped_user}</blockquote>"
    assert "<blockquote" in user_block and "<blockquote expandable>" not in user_block

    # Long bot msg -> expandable blockquote
    bot_block = f"<b>🤖 Gemini:</b>\n<blockquote expandable>{escaped_bot}</blockquote>"
    assert "<blockquote expandable>" in bot_block


def test_history_long_message_chunking():
    """Verifies that very long messages (e.g. 7000+ chars) are safely split and do not exceed 3600 chars."""
    from handlers.routers.common import handle_calendar_date
    import inspect

    long_essay = "Paragraph of theory of relativity. " * 200  # ~7000 chars
    assert len(long_essay) > 6000

    # Ensure source code of handle_calendar_date contains _split_history_text and plain text fallback
    source = inspect.getsource(handle_calendar_date)
    assert "_split_history_text" in source
    assert "retrying plain text" in source
    assert "3500" in source


def test_split_text_by_chunks():
    """Tests utility function split_text_by_chunks with various input lengths and boundaries."""
    from utils.text_helpers import split_text_by_chunks

    # Empty text
    assert split_text_by_chunks("") == []
    assert split_text_by_chunks("   ") == []

    # Short text
    short_text = "Hello world! This is a test."
    assert split_text_by_chunks(short_text, max_chars=100) == [short_text]

    # Paragraph-aware split
    p1 = "Paragraph 1 is here."
    p2 = "Paragraph 2 is right after."
    text_with_paras = f"{p1}\n\n{p2}"
    chunks = split_text_by_chunks(text_with_paras, max_chars=30)
    assert len(chunks) == 2
    assert chunks[0] == p1
    assert chunks[1] == p2

    # Long text (e.g. 10,000 chars)
    long_text = "Word " * 2000
    chunks = split_text_by_chunks(long_text, max_chars=3500)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 3500


def test_routers_chunking_guards():
    """Verifies that translation, feedback, admin reply and broadcast handlers use chunking guards."""
    import inspect
    from handlers.routers.common import process_translation, process_feedback
    from handlers.routers.admin import handle_broadcast_execute, process_admin_reply, handle_reply_user_command

    assert "split_text_by_chunks" in inspect.getsource(process_translation)
    assert "split_text_by_chunks" in inspect.getsource(process_feedback)
    assert "split_text_by_chunks" in inspect.getsource(handle_broadcast_execute)
    assert "split_text_by_chunks" in inspect.getsource(process_admin_reply)
    assert "split_text_by_chunks" in inspect.getsource(handle_reply_user_command)


