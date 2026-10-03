"""
Dialogs router for MyGemini (aiogram 3.x).
Handles:
- Viewing and switching between dialogs
- Creating, renaming, and deleting dialogs
- Exporting entire dialog transcript to GitHub-flavored Markdown (.md)
"""

import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config.settings import (
    CALLBACK_DIALOGS_MENU, CALLBACK_DIALOG_SWITCH_PREFIX,
    CALLBACK_DIALOG_RENAME_PREFIX, CALLBACK_DIALOG_DELETE_PREFIX,
    CALLBACK_DIALOG_CREATE, CALLBACK_DIALOG_CONFIRM_DELETE_PREFIX
)
from database import db_manager
from utils import localization as loc
from keyboards.aiogram_inline import get_dialogs_keyboard, get_confirm_delete_dialog_keyboard
from services import gemini_service
from services import promo_service
from logger_config import get_logger

logger = get_logger(__name__)

router = Router(name="dialogs_router")


class DialogStates(StatesGroup):
    waiting_for_new_name = State()
    waiting_for_rename = State()


@router.message(Command("dialogs"))
@router.message(F.text.in_({"🗂️ Диалоги", "🗂️ Dialogs", "/dialogs"}))
async def handle_dialogs_command(message: Message):
    """Renders dialogs menu."""
    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    dialogs = await db_manager.get_user_dialogs(user_id)
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)

    title = f"{loc.get_text('dialogs_menu_title', lang_code)}\n\n{loc.get_text('dialogs_menu_desc', lang_code)}"
    await message.answer(
        title,
        reply_markup=get_dialogs_keyboard(dialogs, active_dialog_id, lang_code),
        parse_mode="HTML"
    )


@router.callback_query(F.data == CALLBACK_DIALOGS_MENU)
async def handle_dialogs_menu_callback(callback: CallbackQuery):
    """Re-renders dialogs menu from callback."""
    await callback.answer()
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    dialogs = await db_manager.get_user_dialogs(user_id)
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)

    title = f"{loc.get_text('dialogs_menu_title', lang_code)}\n\n{loc.get_text('dialogs_menu_desc', lang_code)}"
    await callback.message.edit_text(
        title,
        reply_markup=get_dialogs_keyboard(dialogs, active_dialog_id, lang_code),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith(CALLBACK_DIALOG_SWITCH_PREFIX))
async def handle_switch_dialog(callback: CallbackQuery):
    """Switches active dialog."""
    dialog_id = int(callback.data.replace(CALLBACK_DIALOG_SWITCH_PREFIX, ""))
    user_id = callback.from_user.id
    await db_manager.set_active_dialog(user_id, dialog_id)
    gemini_service.reset_dialog_chat(dialog_id)
    lang_code = await db_manager.get_user_language(user_id)

    dialog_info = await db_manager.get_dialog_info(dialog_id)
    d_name = dialog_info.get("name", "") if dialog_info else ""
    await callback.answer(loc.get_text('dialog_switched_success', lang_code).format(name=d_name))

    dialogs = await db_manager.get_user_dialogs(user_id)
    title = f"{loc.get_text('dialogs_menu_title', lang_code)}\n\n{loc.get_text('dialogs_menu_desc', lang_code)}"
    await callback.message.edit_text(
        title,
        reply_markup=get_dialogs_keyboard(dialogs, dialog_id, lang_code),
        parse_mode="HTML"
    )


@router.callback_query(F.data == CALLBACK_DIALOG_CREATE)
async def handle_create_dialog_init(callback: CallbackQuery, state: FSMContext):
    """Initiates dialog creation flow."""
    await callback.answer()
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    await state.set_state(DialogStates.waiting_for_new_name)
    await callback.message.answer(loc.get_text('dialog_enter_new_name_prompt', lang_code))


@router.message(DialogStates.waiting_for_new_name)
async def process_create_dialog_name(message: Message, state: FSMContext):
    """Creates dialog with given name."""
    user_id = message.from_user.id
    name = message.text.strip()
    lang_code = await db_manager.get_user_language(user_id)
    if not name or len(name) > 50:
        await message.answer(loc.get_text('dialog_name_too_long' if len(name) > 50 else 'dialog_name_invalid', lang_code))
        return

    new_id = await db_manager.create_dialog(user_id, name, set_active=True)
    await state.clear()
    await message.answer(loc.get_text('dialog_created_success', lang_code).format(name=name))


@router.callback_query(F.data.startswith(CALLBACK_DIALOG_RENAME_PREFIX))
async def handle_rename_dialog_init(callback: CallbackQuery, state: FSMContext):
    """Initiates dialog rename flow."""
    dialog_id = int(callback.data.replace(CALLBACK_DIALOG_RENAME_PREFIX, ""))
    await callback.answer()
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    dialog_info = await db_manager.get_dialog_info(dialog_id)
    d_name = dialog_info.get("name", "") if dialog_info else ""

    await state.update_data(dialog_id_to_rename=dialog_id)
    await state.set_state(DialogStates.waiting_for_rename)
    await callback.message.answer(loc.get_text('dialog_enter_rename_prompt', lang_code).format(name=d_name))


@router.message(DialogStates.waiting_for_rename)
async def process_rename_dialog_name(message: Message, state: FSMContext):
    """Renames dialog with given name."""
    user_id = message.from_user.id
    name = message.text.strip()
    lang_code = await db_manager.get_user_language(user_id)
    data = await state.get_data()
    dialog_id = data.get("dialog_id_to_rename")
    await state.clear()

    if not name or len(name) > 50:
        await message.answer(loc.get_text('dialog_name_too_long' if len(name) > 50 else 'dialog_name_invalid', lang_code))
        return

    if dialog_id:
        await db_manager.rename_dialog(dialog_id, name)
        await message.answer(loc.get_text('dialog_renamed_success', lang_code).format(new_name=name))


@router.callback_query(F.data.startswith(CALLBACK_DIALOG_DELETE_PREFIX))
async def handle_delete_dialog_confirm(callback: CallbackQuery):
    """Presents deletion confirmation."""
    dialog_id = int(callback.data.replace(CALLBACK_DIALOG_DELETE_PREFIX, ""))
    await callback.answer()
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    dialog_info = await db_manager.get_dialog_info(dialog_id)
    d_name = dialog_info.get("name", "") if dialog_info else ""

    title = loc.get_text('dialog_delete_confirmation', lang_code).format(name=d_name)
    await callback.message.edit_text(title, reply_markup=get_confirm_delete_dialog_keyboard(dialog_id, lang_code))


@router.callback_query(F.data.startswith(CALLBACK_DIALOG_CONFIRM_DELETE_PREFIX))
async def handle_delete_dialog_execute(callback: CallbackQuery):
    """Deletes dialog and refreshes menu."""
    dialog_id = int(callback.data.replace(CALLBACK_DIALOG_CONFIRM_DELETE_PREFIX, ""))
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    dialog_info = await db_manager.get_dialog_info(dialog_id)
    d_name = dialog_info.get("name", "") if dialog_info else ""

    await db_manager.delete_dialog(user_id, dialog_id)
    gemini_service.reset_dialog_chat(dialog_id)
    await callback.answer(loc.get_text('dialog_deleted_success', lang_code).format(name=d_name))

    dialogs = await db_manager.get_user_dialogs(user_id)
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)
    title = f"{loc.get_text('dialogs_menu_title', lang_code)}\n\n{loc.get_text('dialogs_menu_desc', lang_code)}"
    await callback.message.edit_text(
        title,
        reply_markup=get_dialogs_keyboard(dialogs, active_dialog_id, lang_code),
        parse_mode="HTML"
    )


# --- EXPORT DIALOG TO MARKDOWN ---

@router.callback_query(F.data.startswith("dialog_export:"))
async def handle_dialog_export(callback: CallbackQuery):
    """Generates and sends clean Markdown transcript of the dialog."""
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    dialog_id = int(callback.data.split("dialog_export:")[1])

    dialog_info = await db_manager.get_dialog_info(dialog_id)
    dialog_title = dialog_info.get("name", f"Dialog {dialog_id}") if dialog_info else f"Dialog {dialog_id}"

    messages = await db_manager.get_dialog_all_messages(dialog_id)
    if not messages:
        await callback.answer("Диалог пуст" if lang_code == "ru" else "Dialog is empty", show_alert=True)
        return

    await callback.answer("Формирую файл экспорта..." if lang_code == "ru" else "Generating export...")

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_label = "*Дата экспорта:*" if lang_code == "ru" else "*Export date:*"
    msgs_label = "*Всего сообщений:*" if lang_code == "ru" else "*Total messages:*"

    md_lines = [
        f"# 🗂️ {dialog_title}",
        f"{date_label} {now_str}",
        f"{msgs_label} {len(messages)}\n",
        "---\n",
    ]

    for m in messages:
        ts = m.get('timestamp') or ""
        if lang_code == "ru":
            role_title = "👤 Пользователь" if m['role'] == 'user' else "🤖 Ассистент Gemini"
            tokens_info = f"*(Токенов: {m['total_tokens']})*" if m.get('total_tokens') else ""
        else:
            role_title = "👤 User" if m['role'] == 'user' else "🤖 Gemini Assistant"
            tokens_info = f"*(Tokens: {m['total_tokens']})*" if m.get('total_tokens') else ""
        header = f"### {role_title} [{ts}] {tokens_info}".strip()
        body = m.get('message_text') or ""
        md_lines.append(f"{header}\n\n{body}\n\n---\n")

    md_lines.append(promo_service.get_export_footer(lang_code))
    md_content = "\n".join(md_lines)
    file_bytes = md_content.encode('utf-8')

    clean_filename = f"dialog_{dialog_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    doc = BufferedInputFile(file_bytes, filename=clean_filename)

    caption = (
        f"📥 Экспорт диалога <b>{dialog_title}</b> готов!"
        if lang_code == "ru" else
        f"📥 Export for dialogue <b>{dialog_title}</b> is ready!"
    )
    await callback.message.answer_document(doc, caption=caption, parse_mode="HTML")
