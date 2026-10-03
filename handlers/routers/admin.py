"""
Admin router for MyGemini (aiogram 3.x).
Restricted strictly to ADMIN_USER_ID.
Focused 100% on free-bot management:
- Main dashboard (/admin, 👑 Админ-панель)
- Activity statistics (total users, active 7d, new 7d, with API key, blocked)
- Users list with status indicators (🟢 with key, ⚪ no key, ⛔️ blocked)
- CSV export with UTF-8 BOM encoding for Microsoft Excel
- User search & card management by ID (/user <id> or interactive search)
- Block/Unblock toggle and API key reset
- Direct admin reply to user (/reply <id> <text> or button)
- Broadcast messaging with confirmation
- Maintenance mode toggle (live 🟢/🔴 status)
"""

import io
import csv
import re
import html
import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.text_helpers import split_text_by_chunks

from config.settings import (
    ADMIN_USER_ID, CALLBACK_ADMIN_MAIN_MENU, CALLBACK_ADMIN_STATS_MENU,
    CALLBACK_ADMIN_COMMUNICATION_MENU, CALLBACK_ADMIN_USER_MANAGEMENT_MENU,
    CALLBACK_ADMIN_MAINTENANCE_MENU, CALLBACK_ADMIN_TOGGLE_MAINTENANCE,
    CALLBACK_ADMIN_BROADCAST, CALLBACK_ADMIN_CONFIRM_BROADCAST,
    CALLBACK_ADMIN_CANCEL_BROADCAST, CALLBACK_ADMIN_EXPORT_USERS
)
from database import db_manager
from keyboards.aiogram_inline import (
    get_admin_keyboard,
    get_admin_user_actions_keyboard,
    get_cancel_keyboard,
    get_close_button,
)
from logger_config import get_logger

logger = get_logger(__name__)

router = Router(name="admin_router")


class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_user_id = State()
    waiting_for_admin_reply = State()


def admin_filter(event: Message | CallbackQuery) -> bool:
    """Filter ensuring user is ADMIN_USER_ID."""
    user_id = event.from_user.id
    return bool(ADMIN_USER_ID and user_id == ADMIN_USER_ID)


router.message.filter(admin_filter)
router.callback_query.filter(admin_filter)


async def safe_edit_text(message: Message, text: str, reply_markup=None, parse_mode: str = "HTML"):
    """Safely edits message text with fallback if parse_mode entity parsing fails."""
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.warning(f"Failed to edit message text with {parse_mode}: {e}. Retrying without parse_mode...")
        try:
            import re
            plain = re.sub(r'<[^>]+>', '', text)
            await message.edit_text(plain, reply_markup=reply_markup, parse_mode=None)
        except Exception as e2:
            logger.error(f"Failed fallback edit: {e2}")


async def safe_answer_cb(callback: CallbackQuery, text: str | None = None, show_alert: bool = False):
    """Safely answers callback query."""
    try:
        await callback.answer(text=text, show_alert=show_alert)
    except Exception as e:
        logger.debug(f"Failed to answer callback query: {e}")


# ===================================================================================
# --- DASHBOARD & CLOSE ---
# ===================================================================================

@router.message(Command("admin"))
@router.message(F.text.in_({"👑 Админ-панель", "👑 Admin Panel", "/admin"}))
@router.callback_query(F.data.in_({"menu_admin", CALLBACK_ADMIN_MAIN_MENU}))
async def handle_admin_panel(event: Message | CallbackQuery, state: FSMContext | None = None):
    """Entry point for the admin control dashboard."""
    if state:
        await state.clear()

    user_id = event.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    is_maintenance = (await db_manager.get_app_setting("maintenance_mode")) == "true"

    text = (
        "👑 <b>Панель администратора MyGemini</b>\n\n"
        "Здесь вы можете просматривать статистику активности, "
        "список пользователей, управлять блокировкой и API-ключами, "
        "выгружать базу данных в CSV и переключать режим обслуживания."
        if lang_code == "ru"
        else "👑 <b>MyGemini Administrator Panel</b>\n\n"
        "View activity stats, user list, manage user blocks & API keys, "
        "export CSV reports, and toggle maintenance mode."
    )

    kb = get_admin_keyboard(is_maintenance, lang_code=lang_code)

    if isinstance(event, CallbackQuery):
        await safe_answer_cb(event)
        await safe_edit_text(event.message, text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.in_({"close_menu", "menu_admin_close"}))
async def handle_admin_close(callback: CallbackQuery):
    """Closes admin panel or submenus."""
    await safe_answer_cb(callback)
    try:
        await callback.message.delete()
    except Exception:
        pass


# ===================================================================================
# --- ACTIVITY STATISTICS ---
# ===================================================================================

@router.callback_query(F.data.in_({"admin_stats", CALLBACK_ADMIN_STATS_MENU}))
async def handle_admin_stats(callback: CallbackQuery):
    """Displays operational & activity metrics."""
    await safe_answer_cb(callback)

    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    is_maintenance = (await db_manager.get_app_setting("maintenance_mode")) == "true"

    total_users = await db_manager.get_total_users_count()
    active_7d = await db_manager.get_active_users_count(days=7)
    new_7d = await db_manager.get_new_users_count(days=7)
    with_key = await db_manager.get_users_with_key_count()
    blocked_count = await db_manager.get_blocked_users_count()

    if lang_code == "ru":
        text = (
            "📊 <b>Статистика активности бота:</b>\n\n"
            f"• <b>Всего пользователей:</b> {total_users}\n"
            f"• <b>Активных за 7 дней:</b> {active_7d}\n"
            f"• <b>Новых за 7 дней:</b> {new_7d}\n"
            f"• <b>С установленным API-ключом:</b> {with_key}\n"
            f"• <b>Заблокированных:</b> {blocked_count}\n"
        )
    else:
        text = (
            "📊 <b>Bot Activity Statistics:</b>\n\n"
            f"• <b>Total Users:</b> {total_users}\n"
            f"• <b>Active (7 days):</b> {active_7d}\n"
            f"• <b>New (7 days):</b> {new_7d}\n"
            f"• <b>With API Key:</b> {with_key}\n"
            f"• <b>Blocked Users:</b> {blocked_count}\n"
        )

    await safe_edit_text(
        callback.message,
        text,
        reply_markup=get_admin_keyboard(is_maintenance, lang_code=lang_code),
        parse_mode="HTML",
    )


# ===================================================================================
# --- USERS LIST ---
# ===================================================================================

@router.callback_query(F.data.in_({"admin_users_list", "admin_subscribers"}))
async def handle_admin_users_list(callback: CallbackQuery):
    """Displays registered bot users with activity and status."""
    await safe_answer_cb(callback)

    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    is_maintenance = (await db_manager.get_app_setting("maintenance_mode")) == "true"

    users = await db_manager.get_all_users_with_stats()

    if not users:
        no_users = "👥 <b>Пользователей пока нет.</b>" if lang_code == "ru" else "👥 <b>No users registered yet.</b>"
        await safe_edit_text(
            callback.message,
            no_users,
            reply_markup=get_admin_keyboard(is_maintenance, lang_code=lang_code),
            parse_mode="HTML",
        )
        return

    header = "👥 <b>Список пользователей:</b>\n" if lang_code == "ru" else "👥 <b>Bot Users List:</b>\n"
    lines = [header]
    total_len = len(header)
    shown_count = 0

    for i, u in enumerate(users, 1):
        uname = f"@{html.escape(u['username'])}" if u.get("username") else "без username"
        full_name = html.escape(f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip() or "Аноним")
        uid = u["user_id"]
        is_blocked = bool(u.get("is_blocked"))
        has_key = bool(u.get("has_api_key"))
        msg_count = u.get("message_count", 0)
        reg_date = u.get("first_interaction_date") or "—"

        if uid == ADMIN_USER_ID:
            marker = "👑"
            role_desc = "Администратор" if lang_code == "ru" else "Administrator"
        elif is_blocked:
            marker = "⛔️"
            role_desc = "Заблокирован" if lang_code == "ru" else "Blocked"
        elif has_key:
            marker = "🟢"
            role_desc = "Активен (ключ есть)" if lang_code == "ru" else "Active (key set)"
        else:
            marker = "⚪"
            role_desc = "Без ключа" if lang_code == "ru" else "No key"

        block = (
            f"{marker} <b>{i}. {full_name}</b> ({uname})\n"
            f"   • <b>ID:</b> <code>{uid}</code> | {role_desc}\n"
            f"   • Рег: {reg_date} | Сообщений: {msg_count}\n"
        )
        # Leave 150 chars margin for footer note and Telegram 4096 limit
        if total_len + len(block) + 150 > 3800:
            break
        lines.append(block)
        total_len += len(block)
        shown_count += 1

    if len(users) > shown_count:
        footer = (
            f"\n<i>... показано {shown_count} из {len(users)} пользователей. Полная база в CSV.</i>"
            if lang_code == "ru"
            else f"\n<i>... showing {shown_count} of {len(users)} users. Full report in CSV.</i>"
        )
        lines.append(footer)

    text = "\n".join(lines)

    await safe_edit_text(
        callback.message,
        text,
        reply_markup=get_admin_keyboard(is_maintenance, lang_code=lang_code),
        parse_mode="HTML",
    )


# ===================================================================================
# --- CSV EXPORT WITH UTF-8 BOM ---
# ===================================================================================

@router.callback_query(F.data.in_({"admin_export_csv", CALLBACK_ADMIN_EXPORT_USERS}))
async def handle_admin_export_csv(callback: CallbackQuery, bot: Bot):
    """Exports all users and metrics into a CSV file with UTF-8 BOM."""
    await safe_answer_cb(callback, "Генерация CSV отчёта...")

    users = await db_manager.get_all_users_for_export()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\n")

    writer.writerow([
        "User ID", "Username", "First Name", "Last Name", "Language",
        "First Interaction", "Has API Key", "Total Messages", "Is Blocked",
        "Bot Style", "Gemini Model", "Active Persona",
    ])

    for u in users:
        writer.writerow([
            u["user_id"], u.get("username") or "", u.get("first_name") or "", u.get("last_name") or "",
            u.get("language_code") or "ru", u.get("first_interaction_date") or "",
            "ДА" if u.get("has_api_key") else "НЕТ",
            u.get("message_count", 0),
            "ДА" if u.get("is_blocked") else "НЕТ",
            u.get("bot_style") or "", u.get("gemini_model") or "", u.get("active_persona") or "",
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    doc_file = BufferedInputFile(csv_bytes, filename=f"users_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

    await bot.send_document(
        chat_id=callback.from_user.id,
        document=doc_file,
        caption="📊 Выгрузка базы данных пользователей (UTF-8 BOM).",
    )


# ===================================================================================
# --- USER MANAGEMENT BY ID & USER CARDS ---
# ===================================================================================

async def render_admin_user_card(target_user_id: int, lang_code: str = "ru") -> tuple[str, InlineKeyboardMarkup]:
    """Renders user info card and management keyboard for admin."""
    target = await db_manager.get_user_by_id(target_user_id)
    if not target:
        not_found = (
            f"❌ Пользователь с ID <code>{target_user_id}</code> не найден."
            if lang_code == "ru"
            else f"❌ User with ID <code>{target_user_id}</code> not found."
        )
        return not_found, InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_admin")]]
        )

    msg_count = await db_manager.get_user_message_count(target_user_id)

    if lang_code == "ru":
        full_name = html.escape(f"{target.get('first_name') or ''} {target.get('last_name') or ''}".strip() or "Аноним")
        uname = f"@{html.escape(target['username'])}" if target.get("username") else "без username"
        has_key = "✅ Установлен" if target.get("api_key") else "❌ Не установлен"
        blocked_str = "⛔️ ЗАБЛОКИРОВАН" if target.get("is_blocked") else "🟢 Активен"

        card_text = (
            f"👤 <b>Карточка пользователя:</b>\n\n"
            f"• <b>Имя:</b> {full_name} ({uname})\n"
            f"• <b>ID:</b> <code>{target['user_id']}</code>\n"
            f"• <b>Доступ:</b> {blocked_str}\n"
            f"• <b>Дата регистрации:</b> {target.get('first_interaction_date') or '—'}\n"
            f"• <b>Язык:</b> {target.get('language_code') or 'ru'}\n"
            f"• <b>API-ключ:</b> {has_key}\n"
            f"• <b>Модель:</b> {target.get('gemini_model') or 'default'}\n"
            f"• <b>Стиль / Роль:</b> {target.get('bot_style') or 'default'} / {target.get('active_persona') or 'default'}\n"
            f"• <b>Всего сообщений:</b> {msg_count}\n"
        )
    else:
        full_name = html.escape(f"{target.get('first_name') or ''} {target.get('last_name') or ''}".strip() or "Anonymous")
        uname = f"@{html.escape(target['username'])}" if target.get("username") else "no username"
        has_key = "✅ Set" if target.get("api_key") else "❌ Not set"
        blocked_str = "⛔️ BLOCKED" if target.get("is_blocked") else "🟢 Active"

        card_text = (
            f"👤 <b>User Profile Card:</b>\n\n"
            f"• <b>Name:</b> {full_name} ({uname})\n"
            f"• <b>ID:</b> <code>{target['user_id']}</code>\n"
            f"• <b>Access:</b> {blocked_str}\n"
            f"• <b>Registration Date:</b> {target.get('first_interaction_date') or '—'}\n"
            f"• <b>Language:</b> {target.get('language_code') or 'ru'}\n"
            f"• <b>API Key:</b> {has_key}\n"
            f"• <b>Model:</b> {target.get('gemini_model') or 'default'}\n"
            f"• <b>Style / Persona:</b> {target.get('bot_style') or 'default'} / {target.get('active_persona') or 'default'}\n"
            f"• <b>Total Messages:</b> {msg_count}\n"
        )

    kb = get_admin_user_actions_keyboard(
        target["user_id"], is_blocked=bool(target.get("is_blocked")), lang_code=lang_code
    )
    return card_text, kb


@router.callback_query(F.data == "admin_user_search")
async def handle_admin_user_search_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompts admin to enter user ID."""
    await safe_answer_cb(callback)
    await state.set_state(AdminStates.waiting_for_user_id)
    lang_code = await db_manager.get_user_language(callback.from_user.id)

    prompt = (
        "🔍 <b>Введите Telegram ID пользователя в чат:</b>\n(Например: <code>123456789</code>)"
        if lang_code == "ru"
        else "🔍 <b>Enter user's Telegram ID in chat:</b>\n(e.g.: <code>123456789</code>)"
    )
    await safe_edit_text(
        callback.message,
        prompt,
        reply_markup=get_cancel_keyboard(callback_data="menu_admin", lang_code=lang_code),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_user_id)
async def process_admin_user_search(message: Message, state: FSMContext):
    """Receives target user ID and displays their card."""
    await state.clear()
    lang_code = await db_manager.get_user_language(message.from_user.id)
    raw_id = message.text.strip() if message.text else ""

    try:
        target_id = int(raw_id)
    except ValueError:
        err_msg = "⚠️ Некорректный ID. Введите число." if lang_code == "ru" else "⚠️ Invalid ID. Enter numbers only."
        back_label = "⬅️ Назад" if lang_code == "ru" else "⬅️ Back"
        await message.answer(
            err_msg,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=back_label, callback_data="menu_admin")]])
        )
        return

    text, kb = await render_admin_user_card(target_id, lang_code=lang_code)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("user"))
async def handle_user_command(message: Message, command: CommandObject):
    """Quick command: /user <id>."""
    lang_code = await db_manager.get_user_language(message.from_user.id)
    arg = command.args.strip() if command.args else ""
    if not arg or not arg.isdigit():
        usage = "Использование: <code>/user 123456789</code>" if lang_code == "ru" else "Usage: <code>/user 123456789</code>"
        await message.answer(usage, parse_mode="HTML")
        return

    text, kb = await render_admin_user_card(int(arg), lang_code=lang_code)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text.startswith("/user "))
async def handle_inspect_user_text(message: Message):
    """Quick text command fallback: /user <id>."""
    lang_code = await db_manager.get_user_language(message.from_user.id)
    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        usage = "Использование: <code>/user &lt;id&gt;</code>" if lang_code == "ru" else "Usage: <code>/user &lt;id&gt;</code>"
        await message.answer(usage, parse_mode="HTML")
        return

    text, kb = await render_admin_user_card(int(parts[1]), lang_code=lang_code)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_user_card:"))
async def handle_admin_user_card_cb(callback: CallbackQuery):
    """Refreshes user card."""
    await safe_answer_cb(callback)
    uid = int(callback.data.split(":")[1])
    lang_code = await db_manager.get_user_language(callback.from_user.id)
    text, kb = await render_admin_user_card(uid, lang_code=lang_code)
    await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_toggle_block:"))
async def handle_admin_toggle_block(callback: CallbackQuery):
    """Toggles user block status."""
    uid = int(callback.data.split(":")[1])
    target = await db_manager.get_user_by_id(uid)
    new_state = not bool(target.get("is_blocked")) if target else True
    await db_manager.set_user_blocked(uid, new_state)

    lang_code = await db_manager.get_user_language(callback.from_user.id)
    if lang_code == "ru":
        status_msg = "Пользователь заблокирован." if new_state else "Пользователь разблокирован."
    else:
        status_msg = "User blocked." if new_state else "User unblocked."
    await safe_answer_cb(callback, status_msg, show_alert=True)
    text, kb = await render_admin_user_card(uid, lang_code=lang_code)
    await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_reset_key:"))
async def handle_admin_reset_key(callback: CallbackQuery):
    """Resets user API key."""
    uid = int(callback.data.split(":")[1])
    await db_manager.reset_user_api_key(uid)
    lang_code = await db_manager.get_user_language(callback.from_user.id)
    status_msg = f"API-ключ пользователя {uid} сброшен." if lang_code == "ru" else f"API key for user {uid} reset."
    await safe_answer_cb(callback, status_msg, show_alert=True)
    text, kb = await render_admin_user_card(uid, lang_code=lang_code)
    await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode="HTML")


# ===================================================================================
# --- DIRECT ADMIN REPLY TO USER ---
# ===================================================================================

@router.callback_query(F.data.startswith("admin_reply_user:"))
async def handle_admin_reply_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompts admin for text to send to user."""
    await safe_answer_cb(callback)
    uid = int(callback.data.split(":")[1])

    await state.update_data(reply_target_user_id=uid)
    await state.set_state(AdminStates.waiting_for_admin_reply)

    prompt = f"✉️ <b>Введите текст сообщения для пользователя <code>{uid}</code>:</b>"
    await safe_edit_text(
        callback.message,
        prompt,
        reply_markup=get_cancel_keyboard(callback_data=f"admin_user_card:{uid}"),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_admin_reply)
async def process_admin_reply(message: Message, state: FSMContext, bot: Bot):
    """Sends admin reply to user."""
    data = await state.get_data()
    target_id = data.get("reply_target_user_id")
    await state.clear()
    reply_text = message.text.strip() if message.text else ""

    if not target_id or not reply_text:
        await message.answer("⚠️ Пустое сообщение или пользователь не указан.")
        return

    target = await db_manager.get_user_by_id(target_id)
    user_lang = target.get("language_code") if target and target.get("language_code") else "ru"

    header = "✉️ <b>Сообщение от службы поддержки / администратора:</b>\n\n" if user_lang == "ru" else "✉️ <b>Message from support / administrator:</b>\n\n"
    user_notification = f"{header}{reply_text}"
    chunks = split_text_by_chunks(user_notification, max_chars=3500)

    try:
        for c in chunks:
            try:
                await bot.send_message(chat_id=target_id, text=c, parse_mode="HTML")
            except Exception:
                await bot.send_message(chat_id=target_id, text=re.sub(r'<[^>]+>', '', c))
        await message.answer(f"✅ Сообщение успешно доставлено пользователю <code>{target_id}</code>!", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to deliver admin reply to {target_id}: {e}")
        await message.answer(f"❌ Ошибка отправки пользователю {target_id}: {e}")


@router.message(F.text.startswith("/reply "))
async def handle_reply_user_command(message: Message, bot: Bot):
    """Direct reply command: /reply <id> <text>."""
    parts = message.text.strip().split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await message.answer("Использование: <code>/reply &lt;user_id&gt; &lt;текст&gt;</code>", parse_mode="HTML")
        return

    target_id = int(parts[1])
    reply_text = parts[2]
    try:
        target = await db_manager.get_user_by_id(target_id)
        user_lang = target.get("language_code") if target and target.get("language_code") else "ru"
        header = "✉️ <b>Сообщение от службы поддержки / администратора:</b>\n\n" if user_lang == "ru" else "✉️ <b>Message from support / administrator:</b>\n\n"
        user_notification = f"{header}{reply_text}"
        chunks = split_text_by_chunks(user_notification, max_chars=3500)

        for c in chunks:
            try:
                await bot.send_message(target_id, c, parse_mode="HTML")
            except Exception:
                await bot.send_message(target_id, re.sub(r'<[^>]+>', '', c))
        await message.answer(f"✅ Сообщение отправлено пользователю {target_id}.")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки пользователю {target_id}: {e}")


# ===================================================================================
# --- BROADCAST FLOW ---
# ===================================================================================

@router.callback_query(F.data == "admin_broadcast")
async def handle_broadcast_init(callback: CallbackQuery, state: FSMContext):
    """Prompts for broadcast message."""
    await safe_answer_cb(callback)
    await state.set_state(AdminStates.waiting_for_broadcast)
    lang_code = await db_manager.get_user_language(callback.from_user.id)
    text = (
        "📢 <b>Рассылка сообщений всем пользователям:</b>\n\n"
        "Отправьте текст сообщения для массовой рассылки.\n"
        "<i>Поддерживается форматирование Telegram HTML.</i>"
        if lang_code == "ru"
        else "📢 <b>Broadcast to all users:</b>\n\n"
        "Send the message text for broadcast.\n"
        "<i>Telegram HTML formatting is supported.</i>"
    )
    await safe_edit_text(
        callback.message,
        text,
        reply_markup=get_cancel_keyboard(callback_data="menu_admin", lang_code=lang_code),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_broadcast)
async def process_broadcast_input(message: Message, state: FSMContext):
    """Shows confirmation before broadcast."""
    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    broadcast_text = message.text or message.caption or ""
    if not broadcast_text:
        err_msg = "⚠️ Пустой текст рассылки. Отменено." if lang_code == "ru" else "⚠️ Empty broadcast text. Cancelled."
        await message.answer(err_msg)
        await state.clear()
        return

    await state.update_data(broadcast_text=broadcast_text)
    total_users = await db_manager.get_total_users_count()

    confirm_btn = "✅ Подтвердить и отправить" if lang_code == "ru" else "✅ Confirm & Send"
    cancel_btn = "❌ Отмена" if lang_code == "ru" else "❌ Cancel"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=confirm_btn, callback_data=CALLBACK_ADMIN_CONFIRM_BROADCAST),
            InlineKeyboardButton(text=cancel_btn, callback_data=CALLBACK_ADMIN_CANCEL_BROADCAST),
        ]
    ])
    
    # Safe preview: truncate if text is too long to prevent 4096 char limit
    if len(broadcast_text) > 2000:
        preview_body = broadcast_text[:2000] + (
            f"\n\n<i>[... показаны первые 2000 символов из {len(broadcast_text)}]</i>"
            if lang_code == "ru"
            else f"\n\n<i>[... showing first 2000 of {len(broadcast_text)} chars]</i>"
        )
    else:
        preview_body = broadcast_text

    text = (
        f"⚠️ <b>Подтверждение рассылки:</b>\n\n"
        f"Получателей: ~{total_users}\n"
        f"Текст:\n<blockquote>{preview_body}</blockquote>"
        if lang_code == "ru"
        else f"⚠️ <b>Broadcast Confirmation:</b>\n\n"
        f"Recipients: ~{total_users}\n"
        f"Text:\n<blockquote>{preview_body}</blockquote>"
    )
    try:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        fallback_preview = re.sub(r'<[^>]+>', '', text)
        await message.answer(fallback_preview, reply_markup=kb)


@router.callback_query(F.data == CALLBACK_ADMIN_CANCEL_BROADCAST)
async def handle_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancels broadcast."""
    await state.clear()
    lang_code = await db_manager.get_user_language(callback.from_user.id)
    ans = "Рассылка отменена" if lang_code == "ru" else "Broadcast cancelled"
    await safe_answer_cb(callback, ans)
    is_maintenance = (await db_manager.get_app_setting("maintenance_mode")) == "true"
    cancel_msg = "❌ Рассылка отменена." if lang_code == "ru" else "❌ Broadcast cancelled."
    await safe_edit_text(callback.message, cancel_msg, reply_markup=get_admin_keyboard(is_maintenance, lang_code=lang_code))


@router.callback_query(F.data == CALLBACK_ADMIN_CONFIRM_BROADCAST)
async def handle_broadcast_execute(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Executes broadcast across all users with safe chunking."""
    data = await state.get_data()
    broadcast_text = data.get("broadcast_text")
    await state.clear()
    lang_code = await db_manager.get_user_language(callback.from_user.id)

    if not broadcast_text:
        err_msg = "Ошибка: нет текста для рассылки" if lang_code == "ru" else "Error: no text to broadcast"
        await safe_answer_cb(callback, err_msg, show_alert=True)
        return

    wait_cb = "Рассылка запущена..." if lang_code == "ru" else "Broadcast started..."
    await safe_answer_cb(callback, wait_cb)
    users = await db_manager.get_all_users()
    wait_msg = "⏳ <i>Начинаю рассылку сообщений...</i>" if lang_code == "ru" else "⏳ <i>Starting broadcast...</i>"
    status_msg = await callback.message.answer(wait_msg, parse_mode="HTML")

    broadcast_chunks = split_text_by_chunks(broadcast_text, max_chars=3500)
    sent = 0
    failed = 0
    for u in users:
        if u.get("is_blocked"):
            continue
        try:
            for b_chunk in broadcast_chunks:
                try:
                    await bot.send_message(u["user_id"], b_chunk, parse_mode="HTML")
                except Exception:
                    await bot.send_message(u["user_id"], re.sub(r'<[^>]+>', '', b_chunk))
            sent += 1
        except Exception:
            failed += 1

    report = (
        f"📢 <b>Рассылка завершена!</b>\n\n"
        f"• <b>Успешно доставлено:</b> {sent}\n"
        f"• <b>Не удалось отправить:</b> {failed}\n"
        if lang_code == "ru"
        else f"📢 <b>Broadcast finished!</b>\n\n"
        f"• <b>Delivered successfully:</b> {sent}\n"
        f"• <b>Failed to deliver:</b> {failed}\n"
    )
    is_maintenance = (await db_manager.get_app_setting("maintenance_mode")) == "true"
    await status_msg.edit_text(report, reply_markup=get_admin_keyboard(is_maintenance, lang_code=lang_code), parse_mode="HTML")


# ===================================================================================
# --- MAINTENANCE MODE TOGGLE ---
# ===================================================================================

@router.callback_query(F.data.in_({"admin_toggle_maintenance", CALLBACK_ADMIN_TOGGLE_MAINTENANCE}))
async def handle_toggle_maintenance(callback: CallbackQuery):
    """Toggles maintenance mode status in app_settings."""
    lang_code = await db_manager.get_user_language(callback.from_user.id)
    current_val = await db_manager.get_app_setting("maintenance_mode")
    new_val = "false" if current_val == "true" else "true"
    await db_manager.set_app_setting("maintenance_mode", new_val)
    if lang_code == "ru":
        status_str = "включен" if new_val == "true" else "выключен"
        msg = f"Режим обслуживания {status_str}!"
    else:
        status_str = "enabled" if new_val == "true" else "disabled"
        msg = f"Maintenance mode {status_str}!"
    await safe_answer_cb(callback, msg, show_alert=True)
    await handle_admin_panel(callback)
