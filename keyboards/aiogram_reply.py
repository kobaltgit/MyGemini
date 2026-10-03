"""
Main reply keyboard for MyGemini (aiogram 3.x).
Maintains the exact 3x3 (9 buttons for admin, 8 for regular user) layout.
"""

from typing import Optional
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from utils import localization as loc
from config.settings import ADMIN_USER_ID


def create_main_keyboard(lang_code: str = "ru", user_id: Optional[int] = None) -> ReplyKeyboardMarkup:
    """
    Creates the main Telegram reply keyboard in strict 3x3 layout:
    Row 1: [👑 Админ-панель] [🗂️ Диалоги] [👤 Личный кабинет] (8 buttons if non-admin)
    Row 2: [📊 Расходы] [⚙️ Настройки] [🇷🇺 Перевести]
    Row 3: [📜 История] [❓ Помощь] [🔄 Сброс]
    """
    is_admin = bool(user_id is not None and ADMIN_USER_ID is not None and user_id == ADMIN_USER_ID)

    row1 = []
    if is_admin:
        row1.append(KeyboardButton(text=loc.get_text('btn_admin_panel', lang_code)))
    row1.append(KeyboardButton(text=loc.get_text('btn_dialogs', lang_code)))
    row1.append(KeyboardButton(text=loc.get_text('btn_account', lang_code)))

    row2 = [
        KeyboardButton(text=loc.get_text('btn_usage', lang_code)),
        KeyboardButton(text=loc.get_text('btn_settings', lang_code)),
        KeyboardButton(text=loc.get_text('btn_translate', lang_code)),
    ]

    row3 = [
        KeyboardButton(text=loc.get_text('btn_history', lang_code)),
        KeyboardButton(text=loc.get_text('btn_help', lang_code)),
        KeyboardButton(text=loc.get_text('btn_reset', lang_code)),
    ]

    keyboard = [row1, row2, row3]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
