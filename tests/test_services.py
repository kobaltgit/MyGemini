import pytest
from unittest.mock import AsyncMock, MagicMock
from services import promo_service
from services import throttler
from services import gemini_service


def test_promo_service():
    """Verify promo service text outputs for ru and en."""
    promo_ru = promo_service.get_flagship_promo("ru")
    assert "@mgemz_bot" in promo_ru
    assert "MyGemini Zero" in promo_ru

    footer_ru = promo_service.get_export_footer("ru")
    assert "mgemz_bot" in footer_ru

    overview = promo_service.get_projects_overview("ru")
    assert "MyGemini" in overview
    assert "MyGemini Zero" in overview


def test_throttler_helpers():
    """Verify markdown safe formatting and throttler token handling."""
    plain = "Hello world!"
    formatted, mode = throttler.format_markdown_safe(plain)
    assert mode in ("MarkdownV2", None)

    bot_mock = MagicMock()
    msg_mock = MagicMock()
    msg_mock.message_id = 123
    stream_throttler = throttler.MessageStreamThrottler(
        bot=bot_mock,
        chat_id=456,
        initial_message=msg_mock,
        header_text="> 💬 Test\n\n",
        header_style="expandable",
        message_format="rich",
    )
    assert stream_throttler.header_style == "expandable"
    assert stream_throttler.message_format == "rich"

    # Test usage metadata
    stream_throttler.set_usage_metadata(prompt_tokens=100, candidates_tokens=50, total_tokens=150)
    assert stream_throttler.prompt_tokens == 100
    assert stream_throttler.candidates_tokens == 50
    assert stream_throttler.total_tokens == 150

    # Test abort
    assert not stream_throttler.is_aborted
    stream_throttler.abort()
    assert stream_throttler.is_aborted


def test_gemini_service_model_support():
    """Verify search support checker and service instantiation."""
    assert gemini_service.model_supports_search("gemini-2.5-flash") is True
    assert gemini_service.model_supports_search("gemma-2-9b") is False
    assert gemini_service.model_supports_search("gemini-2.5-flash-preview-tts") is False

    service = gemini_service.GeminiService(api_key="AIzaSyTestFakeKey")
    assert service.api_key == "AIzaSyTestFakeKey"
    assert hasattr(service, "generate_stream")
    assert hasattr(service, "count_tokens")
