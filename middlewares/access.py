"""
Access control middleware for MyGemini (aiogram 3.x).
Checks:
1. Blocked status (is_blocked).
2. Maintenance mode (app_settings.maintenance_mode) - restricts access for all users except ADMIN_USER_ID.
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from config.settings import ADMIN_USER_ID
from database import db_manager
from utils import localization as loc


class AccessMiddleware(BaseMiddleware):
    """Verifies that user is not blocked and bot is not in maintenance mode."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        user_id = user.id

        # 1. Check if user is blocked
        if await db_manager.is_user_blocked(user_id):
            lang_code = await db_manager.get_user_language(user_id)
            if isinstance(event, Message):
                await event.answer(loc.get_text('user_is_blocked', lang_code))
            elif isinstance(event, CallbackQuery):
                await event.answer(loc.get_text('user_is_blocked', lang_code), show_alert=True)
            return None

        # 2. Check maintenance mode
        maintenance = await db_manager.get_app_setting("maintenance_mode")
        if maintenance == "true" and user_id != ADMIN_USER_ID:
            lang_code = await db_manager.get_user_language(user_id)
            notice = loc.get_text('maintenance_mode_on', lang_code)
            if isinstance(event, Message):
                await event.answer(notice)
            elif isinstance(event, CallbackQuery):
                await event.answer(notice, show_alert=True)
            return None

        return await handler(event, data)
