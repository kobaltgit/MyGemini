"""
Core aiogram 3 application factory and dispatcher runner for MyGemini.
Registers middleware, routers, and provides graceful shutdown.
"""

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import settings
from database import db_manager
from logger_config import get_logger
from middlewares.access import AccessMiddleware
from handlers.routers import common, settings as settings_router, dialogs, chat, admin

logger = get_logger("main")


def create_dispatcher() -> Dispatcher:
    """Builds and configures the aiogram Dispatcher with all routers and middlewares."""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register access middleware
    dp.message.middleware(AccessMiddleware())
    dp.callback_query.middleware(AccessMiddleware())

    # Register routers in priority order:
    # 1. Admin router (restricted to ADMIN_USER_ID)
    # 2. Settings router (settings views, header switcher, format switcher, budget, toggles)
    # 3. Dialogs router (dialog management, switches, exports)
    # 4. Common router (commands /start, /help, /usage, /history, /translate, /reset, reply keyboard buttons)
    # 5. Chat router (fall-through for user prompts, multimodal photo/voice, streaming)
    dp.include_router(admin.router)
    dp.include_router(settings_router.router)
    dp.include_router(dialogs.router)
    dp.include_router(common.router)
    dp.include_router(chat.router)

    return dp


async def start_bot():
    """Initializes database and runs polling loop."""
    logger.info("Initializing MyGemini v2 (aiogram 3.x)...")
    await db_manager.setup_database()

    default_props = DefaultBotProperties(parse_mode="HTML")
    bot = Bot(token=settings.BOT_TOKEN, default=default_props)
    from handlers import telegram_helpers
    telegram_helpers.register_bot_instance(bot)

    dp = create_dispatcher()

    try:
        logger.info("Bot is starting polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Bot session closed successfully.")


if __name__ == "__main__":
    asyncio.run(start_bot())
