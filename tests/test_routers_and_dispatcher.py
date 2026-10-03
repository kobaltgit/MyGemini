import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, User, Chat
from bot_app import create_dispatcher
from handlers.routers.settings import render_settings_view
from handlers.routers import common, settings as settings_router, dialogs, chat, admin
from database import db_manager


def test_dispatcher_router_registration():
    """Verify that Dispatcher properly includes all 5 routers."""
    dp = create_dispatcher()
    assert len(dp.sub_routers) == 5
    router_names = [r.name for r in dp.sub_routers]
    assert "admin_router" in router_names
    assert "settings_router" in router_names
    assert "dialogs_router" in router_names
    assert "common_router" in router_names
    assert "chat_router" in router_names


@pytest.mark.asyncio
async def test_settings_view_rendering():
    """Verify render_settings_view fetches user info and builds view with header style."""
    user_ids = await db_manager.get_all_user_ids()
    assert len(user_ids) > 0
    test_user_id = user_ids[0]

    text, keyboard = await render_settings_view(test_user_id)
    assert "Настройки MyGemini:" in text or "MyGemini Settings:" in text
    assert "Шапка ответа:" in text or "Header:" in text
    assert keyboard is not None
    assert len(keyboard.inline_keyboard) > 5


@pytest.mark.asyncio
async def test_accidental_api_key_regex():
    """Verify accidental API key regex catches standard Google AI Studio keys."""
    pattern = r"^AIzaSy[A-Za-z0-9_-]{33}$"
    import re
    valid_key = "AIzaSy" + ("A" * 33)
    assert len(valid_key) == 39
    assert re.match(pattern, valid_key) is not None

    invalid_key = "AIzaSyShort"
    assert re.match(pattern, invalid_key) is None


@pytest.mark.asyncio
async def test_sandbox_state_and_keyboard():
    """Verify sandbox cancel keyboard and state existence."""
    from keyboards.aiogram_inline import get_sandbox_cancel_keyboard, get_chat_quick_actions_keyboard
    from handlers.routers.chat import SandboxStates

    kb = get_sandbox_cancel_keyboard("ru")
    assert len(kb.inline_keyboard) == 1
    assert kb.inline_keyboard[0][0].callback_data == "chat_action:sandbox_cancel"

    quick_kb = get_chat_quick_actions_keyboard("ru", dialog_id=1, enable_code_execution=True)
    all_callbacks = [btn.callback_data for row in quick_kb.inline_keyboard for btn in row]
    assert "chat_action:sandbox" in all_callbacks
    assert "dialog_export:1" in all_callbacks

    assert hasattr(SandboxStates, "waiting_for_sandbox_prompt")


@pytest.mark.asyncio
async def test_notify_admin_of_new_user_aiogram():
    """Verify that notify_admin_of_new_user formats and dispatches message via aiogram Bot."""
    from handlers import telegram_helpers
    from unittest.mock import AsyncMock, MagicMock

    mock_bot = MagicMock()
    mock_bot.token = "123:ABC"
    mock_bot.session = MagicMock()
    mock_bot.send_message = AsyncMock()

    telegram_helpers.register_bot_instance(mock_bot)
    await telegram_helpers.notify_admin_of_new_user(
        user_id=111222333,
        username="john_doe",
        first_name="John",
        last_name="Doe"
    )

    assert mock_bot.send_message.called
    call_args = mock_bot.send_message.call_args
    assert call_args.args[0] == telegram_helpers.ADMIN_USER_ID or call_args.kwargs.get("chat_id") == telegram_helpers.ADMIN_USER_ID
    msg_text = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("text")
    assert "111222333" in msg_text
    assert "@john_doe" in msg_text
    assert "John" in msg_text


@pytest.mark.asyncio
async def test_guides_content_and_commands():
    """Verify that full guides and sections load properly and commands send them."""
    from utils import guide_manager
    from handlers.routers.common import cmd_help_guide, cmd_apikey_info

    # Test guide loading
    ru_guide = guide_manager.get_full_guide("ru")
    en_guide = guide_manager.get_full_guide("en")
    assert len(ru_guide) > 500
    assert len(en_guide) > 500
    assert "gemini-2.5-flash" in ru_guide
    assert "gemini-2.5-flash" in en_guide

    ru_key_section = guide_manager.get_guide_section("API_KEY", "ru")
    en_key_section = guide_manager.get_guide_section("API_KEY", "en")
    assert "aistudio.google.com" in ru_key_section
    assert "aistudio.google.com" in en_key_section

    # Test /help_guide handler
    mock_msg = MagicMock()
    mock_msg.from_user = User(id=12345, is_bot=False, first_name="Tester", username="tester")
    mock_msg.chat = Chat(id=12345, type="private")
    mock_msg.answer = AsyncMock()

    await cmd_help_guide(mock_msg)
    assert mock_msg.answer.called
    for call in mock_msg.answer.call_args_list:
        text_arg = call.args[0] if call.args else call.kwargs.get("text", "")
        # Must not contain raw markdown headers or section tags
        assert "###" not in text_arg
        assert "# [НАЧАЛО" not in text_arg
        assert "# [КОНЕЦ" not in text_arg
        assert "<b>" in text_arg

    # Test /apikey_info handler
    mock_msg.answer.reset_mock()
    await cmd_apikey_info(mock_msg)
    assert mock_msg.answer.called
    for call in mock_msg.answer.call_args_list:
        text_arg = call.args[0] if call.args else call.kwargs.get("text", "")
        assert "###" not in text_arg
        assert "<b>" in text_arg
        assert "<a href=" in text_arg


def test_markdown_to_telegram_html():
    """Verify markdown to telegram HTML converter handles all elements cleanly."""
    from utils.text_helpers import markdown_to_telegram_html

    sample_md = (
        "# [НАЧАЛО РАЗДЕЛА: TEST]\n\n"
        "### 🚀 Заголовок 1\n\n"
        "Обычный текст с **жирным шрифтом** и *курсивом*, а также `кодом`.\n\n"
        "* Пункт 1\n"
        "* Пункт 2 с **акцентом**\n\n"
        "Ссылка: [Google](https://google.com)\n"
        "Картинка: ![Скриншот](https://example.com/pic.png)\n\n"
        "```python\nprint('hello')\n```\n\n"
        "# [КОНЕЦ РАЗДЕЛА: TEST]"
    )

    html_out = markdown_to_telegram_html(sample_md)
    assert "# [НАЧАЛО" not in html_out
    assert "# [КОНЕЦ" not in html_out
    assert "###" not in html_out
    assert "<b>🚀 Заголовок 1</b>" in html_out
    assert "<b>жирным шрифтом</b>" in html_out
    assert "<i>курсивом</i>" in html_out
    assert "<code>кодом</code>" in html_out
    assert "• Пункт 1" in html_out
    assert "• Пункт 2 с <b>акцентом</b>" in html_out
    assert '<a href="https://google.com">Google</a>' in html_out
    assert '🖼 <a href="https://example.com/pic.png">Скриншот</a>' in html_out
    assert "<pre><code>print('hello')</code></pre>" in html_out




