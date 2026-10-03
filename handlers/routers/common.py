"""
Common handlers router for MyGemini (aiogram 3.x).
Handles:
- Commands: /start, /help, /donate, /feedback, /reset, /usage, /history, /translate, /dialogs, /settings, /account
- Main reply 3x3 keyboard text buttons (both Russian and English)
- Accidental API key interception (AIzaSy...)
- Feedback and translation text submission FSM flows
"""

import re
import html
import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config.settings import (
    ADMIN_USER_ID, DONATION_URL, DEFAULT_MODEL_ID, TOKEN_PRICING,
    CALLBACK_LANG_PREFIX, CALLBACK_CALENDAR_MONTH_PREFIX
)
from database import db_manager
from utils import localization as loc
from utils import guide_manager
from utils.text_helpers import split_text_by_chunks
from features import personal_account
from keyboards.aiogram_reply import create_main_keyboard
from keyboards.aiogram_inline import (
    get_translation_keyboard, create_calendar_keyboard,
    get_settings_keyboard, get_dialogs_keyboard
)
from services import gemini_service
from services import promo_service
from logger_config import get_logger

logger = get_logger(__name__)

router = Router(name="common_router")


class CommonStates(StatesGroup):
    waiting_for_api_key = State()
    waiting_for_feedback = State()
    waiting_for_translate_text = State()
    waiting_for_history_date = State()


# ===================================================================================
# --- ACCIDENTAL API KEY INTERCEPTION ---
# ===================================================================================

@router.message(F.text.regexp(r"^AIzaSy[A-Za-z0-9_-]{33}$"))
async def handle_accidental_api_key(message: Message, state: FSMContext):
    """
    Catches accidentally sent Gemini API keys in the chat,
    deletes the message immediately for security, encrypts and saves it.
    """
    user_id = message.from_user.id
    raw_key = message.text.strip()
    try:
        await message.delete()
    except Exception:
        pass

    lang_code = await db_manager.get_user_language(user_id)
    is_valid = await gemini_service.validate_api_key(raw_key)

    if is_valid:
        await db_manager.set_user_api_key(user_id, raw_key)
        active_dialog_id = await db_manager.get_active_dialog_id(user_id)
        if active_dialog_id:
            gemini_service.reset_dialog_chat(active_dialog_id)
        await state.clear()
        text = loc.get_text('api_key_success', lang_code)
        await message.answer(text, reply_markup=create_main_keyboard(lang_code, user_id))
    else:
        text = loc.get_text('api_key_invalid', lang_code)
        await message.answer(text)


# ===================================================================================
# --- COMMANDS: /start, /help, /donate, /feedback ---
# ===================================================================================

@router.message(CommandStart())
@router.message(Command("start"))
@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    """Handles /start command."""
    user = message.from_user
    user_id = user.id
    await db_manager.add_or_update_user(user.id, user.username, user.first_name, user.last_name)
    lang_code = await db_manager.get_user_language(user_id)
    await state.clear()

    active_dialog_id = await db_manager.get_active_dialog_id(user_id)
    if active_dialog_id:
        gemini_service.reset_dialog_chat(active_dialog_id)

    welcome_text = loc.get_text('welcome', lang_code).format(name=user.first_name or "User")
    promo_text = promo_service.get_flagship_promo(lang_code)
    full_text = f"{welcome_text}\n\n{promo_text}"

    await message.answer(
        full_text,
        reply_markup=create_main_keyboard(lang_code, user_id),
        parse_mode="HTML"
    )


@router.message(Command("help"))
@router.message(F.text == "/help")
async def cmd_help(message: Message):
    """Handles /help command."""
    user = message.from_user
    user_id = user.id
    await db_manager.add_or_update_user(user.id, user.username, user.first_name, user.last_name)
    lang_code = await db_manager.get_user_language(user_id)

    help_text = loc.get_text('cmd_help_text', lang_code)
    promo_text = promo_service.get_flagship_promo(lang_code)
    full_text = f"{help_text}\n\n{promo_text}"

    await message.answer(
        full_text,
        reply_markup=create_main_keyboard(lang_code, user_id),
        parse_mode="HTML"
    )


@router.message(Command("help_guide", "guide"))
async def cmd_help_guide(message: Message):
    """Handles /help_guide and /guide commands, sending full user manual."""
    user = message.from_user
    user_id = user.id
    await db_manager.add_or_update_user(user.id, user.username, user.first_name, user.last_name)
    lang_code = await db_manager.get_user_language(user_id)

    guide_text = guide_manager.get_full_guide(lang_code)
    chunks = split_text_by_chunks(guide_text, max_chars=3500)
    for chunk in chunks:
        try:
            await message.answer(chunk, parse_mode="Markdown")
        except Exception:
            await message.answer(chunk)


@router.message(Command("apikey_info", "key_info"))
async def cmd_apikey_info(message: Message):
    """Handles /apikey_info and /key_info commands, sending Google API key instructions."""
    user = message.from_user
    user_id = user.id
    await db_manager.add_or_update_user(user.id, user.username, user.first_name, user.last_name)
    lang_code = await db_manager.get_user_language(user_id)

    guide_text = guide_manager.get_guide_section('API_KEY', lang_code)
    chunks = split_text_by_chunks(guide_text, max_chars=3500)
    for chunk in chunks:
        try:
            await message.answer(chunk, parse_mode="Markdown")
        except Exception:
            await message.answer(chunk)


@router.message(Command("set_api_key", "setapikey"))
async def cmd_set_api_key(message: Message, state: FSMContext):
    """Prompts user to send a new Gemini API key."""
    user_id = message.from_user.id
    await db_manager.add_or_update_user(message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    lang_code = await db_manager.get_user_language(user_id)
    await state.set_state(CommonStates.waiting_for_api_key)
    prompt = loc.get_text('set_api_key_prompt', lang_code)
    await message.answer(prompt)


@router.message(CommonStates.waiting_for_api_key)
async def process_command_api_key(message: Message, state: FSMContext):
    """Processes API key sent after /set_api_key command."""
    user_id = message.from_user.id
    raw_key = message.text.strip() if message.text else ""
    try:
        await message.delete()
    except Exception:
        pass

    lang_code = await db_manager.get_user_language(user_id)
    status_msg = await message.answer(loc.get_text('api_key_verifying', lang_code))

    is_valid = await gemini_service.validate_api_key(raw_key)
    try:
        await status_msg.delete()
    except Exception:
        pass

    if is_valid:
        await db_manager.set_user_api_key(user_id, raw_key)
        active_dialog_id = await db_manager.get_active_dialog_id(user_id)
        if active_dialog_id:
            gemini_service.reset_dialog_chat(active_dialog_id)
        await state.clear()
        text = loc.get_text('api_key_success', lang_code)
        await message.answer(text, reply_markup=create_main_keyboard(lang_code, user_id))
    else:
        text = loc.get_text('api_key_invalid', lang_code)
        await message.answer(text)


@router.message(Command("donate"))
async def cmd_donate(message: Message):
    """Sends project support donation link if configured."""
    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    if DONATION_URL:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        support_label = "☕ Поддержать проект" if lang_code == "ru" else "☕ Support project"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=support_label, url=DONATION_URL)]
        ])
        await message.answer(loc.get_text('support_prompt', lang_code), reply_markup=kb)


@router.message(Command("feedback"))
@router.message(F.text == "/feedback")
async def cmd_feedback(message: Message, state: FSMContext):
    """Initiates user feedback submission."""
    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    prompt = loc.get_text('feedback_prompt', lang_code)
    await state.set_state(CommonStates.waiting_for_feedback)
    await message.answer(prompt)


@router.message(CommonStates.waiting_for_feedback)
async def process_feedback(message: Message, state: FSMContext, bot: Bot):
    """Sends user feedback to admin with safe chunking and HTML escaping."""
    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    await state.clear()
    await message.answer(loc.get_text('feedback_sent', lang_code))

    if ADMIN_USER_ID:
        try:
            uname = html.escape(message.from_user.username or "N/A")
            fname = html.escape(message.from_user.first_name or "N/A")
            raw_feedback = message.text or message.caption or ""
            feedback_chunks = split_text_by_chunks(raw_feedback, max_chars=3000)
            total_chunks = len(feedback_chunks)

            for idx, f_chunk in enumerate(feedback_chunks, 1):
                part_suffix = f" ({idx}/{total_chunks})" if total_chunks > 1 else ""
                escaped_text = html.escape(f_chunk)
                admin_note = (
                    f"⚠️ <b>Новое сообщение от пользователя{part_suffix}:</b>\n"
                    f"<b>ID:</b> <code>{user_id}</code> (@{uname})\n"
                    f"<b>Имя:</b> {fname}\n\n"
                    f"<blockquote>{escaped_text}</blockquote>\n\n"
                    f"Ответить: <code>/reply {user_id}</code>"
                )
                try:
                    await bot.send_message(ADMIN_USER_ID, admin_note, parse_mode="HTML")
                except Exception:
                    # Fallback plain text if HTML parsing fails
                    fallback_text = (
                        f"⚠️ Новое сообщение от пользователя{part_suffix}:\n"
                        f"ID: {user_id} (@{uname})\n"
                        f"Имя: {fname}\n\n"
                        f"{f_chunk}\n\n"
                        f"Ответить: /reply {user_id}"
                    )
                    await bot.send_message(ADMIN_USER_ID, fallback_text)
        except Exception as e:
            logger.error(f"Error sending feedback to admin: {e}")


# ===================================================================================
# --- 3x3 MAIN MENU BUTTON DISPATCHERS ---
# ===================================================================================

# 1. Личный кабинет (User Profile)
@router.message(Command("account", "profile"))
@router.message(F.text.in_({"👤 Личный кабинет", "👤 My Account", "/account", "/profile"}))
async def handle_account(message: Message):
    """Renders user account info with topic analysis."""
    user_id = message.from_user.id
    await db_manager.add_or_update_user(message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    info_text = await personal_account.get_personal_account_info(user_id)
    lang_code = await db_manager.get_user_language(user_id)
    await message.answer(info_text, reply_markup=create_main_keyboard(lang_code, user_id))


# 2. Расходы (Usage)
@router.message(Command("usage"))
@router.message(F.text.in_({"📊 Расходы", "📊 Usage", "/usage"}))
async def handle_usage(message: Message):
    """Calculates and displays token expenses in USD."""
    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    api_key_exists = await db_manager.get_user_api_key(user_id)
    if not api_key_exists:
        await message.answer(loc.get_text('api_key_needed_for_feature', lang_code))
        return

    usage_today = await db_manager.get_token_usage_by_period(user_id, 'today')
    usage_month = await db_manager.get_token_usage_by_period(user_id, 'month')
    user_model = await db_manager.get_user_gemini_model(user_id) or DEFAULT_MODEL_ID
    pricing = TOKEN_PRICING.get(user_model, TOKEN_PRICING['default'])

    def calculate_cost(usage_data):
        input_cost = (usage_data['prompt_tokens'] / 1_000_000) * pricing['input_usd_per_million']
        output_cost = (usage_data['completion_tokens'] / 1_000_000) * pricing['output_usd_per_million']
        return input_cost + output_cost

    cost_today = calculate_cost(usage_today)
    cost_month = calculate_cost(usage_month)

    lines = [
        f"📊 <b>{loc.get_text('usage_title', lang_code).replace('*', '')}</b>\n",
        f"<b>{loc.get_text('usage_today_header', lang_code).replace('*', '')}</b>",
        f"• {loc.get_text('usage_prompt_tokens', lang_code)}: {usage_today['prompt_tokens']:,}",
        f"• {loc.get_text('usage_completion_tokens', lang_code)}: {usage_today['completion_tokens']:,}",
        f"• {loc.get_text('usage_total_tokens', lang_code)}: {usage_today['total_tokens']:,}",
        f"• {loc.get_text('usage_estimated_cost', lang_code)}: ${cost_today:.4f}\n",
        f"<b>{loc.get_text('usage_month_header', lang_code).replace('*', '')}</b>",
        f"• {loc.get_text('usage_prompt_tokens', lang_code)}: {usage_month['prompt_tokens']:,}",
        f"• {loc.get_text('usage_completion_tokens', lang_code)}: {usage_month['completion_tokens']:,}",
        f"• {loc.get_text('usage_total_tokens', lang_code)}: {usage_month['total_tokens']:,}",
        f"• {loc.get_text('usage_estimated_cost', lang_code)}: ${cost_month:.4f}",
        f"\n<i>{loc.get_text('usage_cost_notice', lang_code).replace('_', '')}</i>"
    ]
    await message.answer("\n".join(lines), parse_mode="HTML")


# 3. Перевести (Translate)
@router.message(Command("translate"))
@router.message(F.text.in_({"🇷🇺 Перевести", "🇬🇧 Translate", "/translate"}))
async def handle_translate(message: Message):
    """Presents translation target language keyboard."""
    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    text = loc.get_text('translate_prompt', lang_code)
    await message.answer(text, reply_markup=get_translation_keyboard())


@router.callback_query(F.data.startswith(CALLBACK_LANG_PREFIX))
async def handle_translate_lang_selected(callback: CallbackQuery, state: FSMContext):
    """Handles target language selection and waits for text to translate."""
    target_lang = callback.data.replace(CALLBACK_LANG_PREFIX, "")
    await callback.answer()
    await state.update_data(target_lang=target_lang)
    await state.set_state(CommonStates.waiting_for_translate_text)
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    prompt = loc.get_text('send_text_to_translate_prompt', lang_code).format(lang_name=target_lang)
    await callback.message.answer(prompt)


@router.message(CommonStates.waiting_for_translate_text)
async def process_translation(message: Message, state: FSMContext):
    """Translates user text via Gemini."""
    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    api_key = await db_manager.get_user_api_key(user_id)
    data = await state.get_data()
    target_lang = data.get("target_lang", "English")
    await state.clear()

    if not api_key:
        await message.answer(loc.get_text('api_key_needed_for_feature', lang_code))
        return

    try:
        translated = await gemini_service.generate_content_simple(
            api_key, f"Translate the following text into {target_lang}. Return only translation:\n\n{message.text}"
        )
        if not translated:
            await message.answer(loc.get_text('translation_error_generic', lang_code))
            return

        translation_chunks = split_text_by_chunks(translated, max_chars=3500)
        for t_chunk in translation_chunks:
            await message.answer(t_chunk)
    except Exception as e:
        logger.error(f"Translation error: {e}")
        await message.answer(loc.get_text('translation_error_generic', lang_code))


# 4. История (History calendar)
@router.message(Command("history"))
@router.message(F.text.in_({"📜 История", "📜 History", "/history"}))
async def handle_history(message: Message, state: FSMContext):
    """Displays calendar keyboard to pick date."""
    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    text = loc.get_text('history_prompt', lang_code)
    await state.set_state(CommonStates.waiting_for_history_date)
    await message.answer(text, reply_markup=create_calendar_keyboard(lang_code=lang_code))


@router.callback_query(F.data.startswith("calendar_month:"))
async def handle_calendar_month_navigation(callback: CallbackQuery):
    """Navigates to previous/next month in history calendar."""
    await callback.answer()
    raw = callback.data.replace("calendar_month:", "")
    try:
        y_str, m_str = raw.split("-")
        year = int(y_str)
        month = int(m_str)
    except ValueError:
        return
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    new_kb = create_calendar_keyboard(year=year, month=month, lang_code=lang_code)
    try:
        await callback.message.edit_reply_markup(reply_markup=new_kb)
    except Exception:
        pass


@router.callback_query(F.data == "calendar_cancel")
async def handle_calendar_cancel(callback: CallbackQuery, state: FSMContext):
    """Closes history calendar."""
    await state.clear()
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.callback_query(F.data.startswith("calendar_date:"))
async def handle_calendar_date(callback: CallbackQuery, state: FSMContext):
    """Fetches messages for chosen date with elegant blockquote formatting."""
    date_str = callback.data.replace("calendar_date:", "")
    await callback.answer()
    await state.clear()
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)

    if not active_dialog_id:
        await callback.message.answer(loc.get_text('history_no_messages', lang_code))
        return

    try:
        chosen_date = datetime.date.fromisoformat(date_str)
        msgs = await db_manager.get_conversation_history_by_date(active_dialog_id, chosen_date)
        if not msgs:
            await callback.message.answer(f"{loc.get_text('history_for_date', lang_code)} {date_str}:\n{loc.get_text('history_no_messages', lang_code)}")
            return

        date_formatted = chosen_date.strftime("%d.%m.%Y")
        header_text = f"📜 <b>{loc.get_text('history_for_date', lang_code)} {date_formatted}</b>\n"

        chunks = []
        current_chunk = header_text

        def _split_history_text(text: str, max_chars: int = 2800) -> list[str]:
            text = text.strip()
            if not text:
                return []
            if len(text) <= max_chars:
                return [text]
            parts = []
            while text:
                if len(text) <= max_chars:
                    parts.append(text)
                    break
                split_idx = text.rfind("\n\n", 0, max_chars)
                if split_idx == -1 or split_idx < max_chars // 2:
                    split_idx = text.rfind("\n", 0, max_chars)
                if split_idx == -1 or split_idx < max_chars // 2:
                    split_idx = text.rfind(" ", 0, max_chars)
                if split_idx == -1:
                    split_idx = max_chars
                parts.append(text[:split_idx].strip())
                text = text[split_idx:].strip()
            return [p for p in parts if p]

        for m in msgs:
            is_user = m['role'] == 'user'
            time_str = ""
            if 'timestamp' in m and m['timestamp']:
                try:
                    dt = datetime.datetime.fromisoformat(m['timestamp'])
                    time_str = f" ({dt.strftime('%H:%M')})"
                except Exception:
                    pass

            base_label = ("👤 " + loc.get_text('history_role_user', lang_code) + time_str) if is_user else ("🤖 " + loc.get_text('history_role_bot', lang_code))
            raw_text = (m.get('message_text') or '').strip()

            text_parts = _split_history_text(raw_text, max_chars=2800)
            total_parts = len(text_parts)

            for part_idx, part_text in enumerate(text_parts, 1):
                if total_parts > 1:
                    role_label = f"{base_label} ({part_idx}/{total_parts})"
                else:
                    role_label = base_label

                escaped_body = html.escape(part_text)
                if not is_user and len(escaped_body) > 150:
                    block = f"<b>{role_label}:</b>\n<blockquote expandable>{escaped_body}</blockquote>"
                else:
                    block = f"<b>{role_label}:</b>\n<blockquote>{escaped_body}</blockquote>"

                if len(current_chunk) + len(block) + 2 > 3500:
                    chunks.append(current_chunk.strip())
                    current_chunk = block
                else:
                    current_chunk += "\n\n" + block

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        for chunk in chunks:
            try:
                await callback.message.answer(chunk, parse_mode="HTML")
            except Exception as e_send:
                logger.warning(f"Failed to send history chunk with HTML ({e_send}), retrying plain text")
                plain_chunk = re.sub(r'<[^>]+>', '', chunk)
                await callback.message.answer(plain_chunk)
    except Exception as e:
        logger.error(f"Error reading history: {e}")
        await callback.message.answer(loc.get_text('history_date_error', lang_code))


# 5. Сброс (Reset context)
@router.message(Command("reset"))
@router.message(F.text.in_({"🔄 Сброс", "🔄 Reset", "/reset"}))
async def handle_reset(message: Message, state: FSMContext):
    """Clears context history for active dialog."""
    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    await state.clear()

    active_dialog_id = await db_manager.get_active_dialog_id(user_id)
    if active_dialog_id:
        gemini_service.reset_dialog_chat(active_dialog_id)
        await db_manager.clear_dialog_history(active_dialog_id)

    reset_text = loc.get_text('cmd_reset_success', lang_code)
    await message.answer(reset_text, reply_markup=create_main_keyboard(lang_code, user_id))


# 6. Помощь (Help button)
@router.message(F.text.in_({"❓ Помощь", "❓ Help"}))
async def handle_help_button(message: Message):
    """Processes Help button press."""
    await cmd_help(message)
