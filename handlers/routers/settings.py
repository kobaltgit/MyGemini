"""
Settings router for MyGemini (aiogram 3.x).
Manages:
- Model selection
- Persona and style selection
- Header style (blockquote, expandable, hidden)
- Message format (rich, classic)
- Thinking budget (0, 1024, 4096)
- Python sandbox & Google search toggles
- API key input & validation
- Interface language selection (ru, en)
"""

from typing import Tuple
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config.settings import (
    DEFAULT_MODEL_ID, BOT_PERSONAS, BOT_STYLES,
    CALLBACK_SETTINGS_STYLE_PREFIX, CALLBACK_SETTINGS_LANG_PREFIX,
    CALLBACK_SETTINGS_MODEL_PREFIX, CALLBACK_SETTINGS_PERSONA_PREFIX,
    CALLBACK_SETTINGS_BACK_TO_MAIN
)
import time
from database import db_manager
from utils import localization as loc
from keyboards.aiogram_reply import create_main_keyboard
from keyboards.aiogram_inline import (
    get_settings_keyboard, get_header_style_keyboard,
    get_format_keyboard, get_thinking_budget_keyboard,
    get_language_keyboard, get_model_selection_keyboard
)
from services import gemini_service
from logger_config import get_logger

logger = get_logger(__name__)

router = Router(name="settings_router")


class SettingsStates(StatesGroup):
    waiting_for_api_key = State()


async def render_settings_view(user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
    """Builds and returns formatted settings message and inline keyboard."""
    settings = await db_manager.get_user_settings(user_id) or {}
    cur_model = settings.get("gemini_model") or DEFAULT_MODEL_ID
    cur_persona = settings.get("active_persona") or "default"
    cur_style = settings.get("bot_style") or "default"
    has_api_key = bool(settings.get("api_key"))
    lang_code = settings.get("language_code") or "ru"
    cur_format = settings.get("message_format") or "rich"
    cur_header = settings.get("header_style") or "blockquote"
    cur_budget = settings.get("thinking_budget", 1024)
    code_exec = bool(settings.get("enable_code_execution", 0))
    google_search = bool(settings.get("enable_google_search", 0))

    if lang_code == "ru":
        key_status = "✅ Установлен" if has_api_key else "❌ Не установлен"
        lang_str = "🇷🇺 Русский"
        fmt_str = "⚡ Rich Messages (10.1+)" if cur_format == "rich" else "📝 Классический (Markdown)"
        if cur_header == "expandable":
            hdr_str = "🔽 Под спойлером"
        elif cur_header == "hidden":
            hdr_str = "🚫 Скрыта"
        else:
            hdr_str = "▎ Открытая цитата"

        if cur_budget == 0:
            thinking_str = "⚡ Мгновенно (0)"
        elif cur_budget == 4096:
            thinking_str = "🔬 Глубокий анализ (4096)"
        else:
            thinking_str = "⚖️ Баланс (1024)"

        code_str = "🟢 Включена" if code_exec else "🔴 Выключена"
        search_str = "🟢 Включен" if google_search else "🔴 Выключен"
        persona_info = BOT_PERSONAS.get(cur_persona, BOT_PERSONAS.get("default", {}))
        persona_name = persona_info.get("name_ru", cur_persona)
        style_name = BOT_STYLES.get(cur_style, cur_style)

        text = (
            "⚙️ <b>Настройки MyGemini:</b>\n\n"
            f"• <b>Модель:</b> <code>{cur_model}</code>\n"
            f"• <b>Персона:</b> {persona_name}\n"
            f"• <b>Стиль:</b> {style_name}\n"
            f"• <b>Размышления:</b> {thinking_str}\n"
            f"• <b>Песочница Python:</b> {code_str}\n"
            f"• <b>Поиск Google:</b> {search_str}\n"
            f"• <b>Формат сообщений:</b> {fmt_str}\n"
            f"• <b>Шапка ответа:</b> {hdr_str}\n"
            f"• <b>Язык:</b> {lang_str}\n"
            f"• <b>API-ключ:</b> {key_status}\n\n"
            "Выберите пункт для изменения:"
        )
    else:
        key_status = "✅ Set" if has_api_key else "❌ Not set"
        lang_str = "🇬🇧 English"
        fmt_str = "⚡ Rich Messages (10.1+)" if cur_format == "rich" else "📝 Classic (Markdown)"
        if cur_header == "expandable":
            hdr_str = "🔽 Under spoiler"
        elif cur_header == "hidden":
            hdr_str = "🚫 Hidden"
        else:
            hdr_str = "▎ Standard quote"

        if cur_budget == 0:
            thinking_str = "⚡ Instant (0)"
        elif cur_budget == 4096:
            thinking_str = "🔬 Deep Analysis (4096)"
        else:
            thinking_str = "⚖️ Balanced (1024)"

        code_str = "🟢 Enabled" if code_exec else "🔴 Disabled"
        search_str = "🟢 Enabled" if google_search else "🔴 Disabled"
        persona_info = BOT_PERSONAS.get(cur_persona, BOT_PERSONAS.get("default", {}))
        persona_name = persona_info.get("name_en", cur_persona)
        style_name = BOT_STYLES.get(cur_style, cur_style)

        text = (
            "⚙️ <b>MyGemini Settings:</b>\n\n"
            f"• <b>Model:</b> <code>{cur_model}</code>\n"
            f"• <b>Persona:</b> {persona_name}\n"
            f"• <b>Style:</b> {style_name}\n"
            f"• <b>Thinking Budget:</b> {thinking_str}\n"
            f"• <b>Python Sandbox:</b> {code_str}\n"
            f"• <b>Google Search:</b> {search_str}\n"
            f"• <b>Message Format:</b> {fmt_str}\n"
            f"• <b>Header:</b> {hdr_str}\n"
            f"• <b>Language:</b> {lang_str}\n"
            f"• <b>API Key:</b> {key_status}\n\n"
            "Select setting to configure:"
        )

    keyboard = get_settings_keyboard(
        current_model=cur_model,
        current_style=cur_style,
        current_persona=cur_persona,
        has_api_key=has_api_key,
        lang_code=lang_code,
        current_format=cur_format,
        current_header_style=cur_header,
        current_thinking_budget=cur_budget,
        code_execution_enabled=code_exec,
        google_search_enabled=google_search,
    )
    return text, keyboard


@router.message(F.text.in_({"⚙️ Настройки", "⚙️ Settings", "/settings"}))
async def handle_settings_command(message: Message):
    """Opens settings view."""
    user_id = message.from_user.id
    text, keyboard = await render_settings_view(user_id)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.in_({"menu_settings", "settings_main", CALLBACK_SETTINGS_BACK_TO_MAIN}))
async def handle_menu_settings(callback: CallbackQuery):
    """Refreshes settings view on back button."""
    await callback.answer()
    user_id = callback.from_user.id
    text, keyboard = await render_settings_view(user_id)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "back_to_main")
async def handle_back_to_main(callback: CallbackQuery):
    """Returns to main menu."""
    await callback.answer()
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    await callback.message.delete()
    text = loc.get_text('btn_back_to_main_menu', lang_code)
    await callback.message.answer(text, reply_markup=create_main_keyboard(lang_code, user_id))


# --- Header Style Switching ---

@router.callback_query(F.data == "settings_header")
async def handle_settings_header(callback: CallbackQuery):
    """Presents header style selector."""
    await callback.answer()
    user_id = callback.from_user.id
    settings = await db_manager.get_user_settings(user_id) or {}
    cur_style = settings.get("header_style", "blockquote")
    lang_code = settings.get("language_code", "ru")

    if lang_code == "ru":
        title = (
            "📌 <b>Отображение шапки контекста (диалог, персона, модель):</b>\n\n"
            "• <b>▎ Открытая цитата (Вариант 1):</b> Нативная вертикальная плашка Telegram со строками в аккуратный столбик.\n\n"
            "• <b>🔽 Сворачивать под спойлер:</b> Нативная сворачиваемая цитата (нажмите на стрелочку, чтобы развернуть инфо).\n\n"
            "• <b>🚫 Скрыть шапку:</b> Максимальный минимализм — вывод только ответа модели.\n\n"
            "Выберите желаемый вариант:"
        )
    else:
        title = (
            "📌 <b>Context Header Display:</b>\n\n"
            "• <b>▎ Standard Quote (Option 1):</b> Telegram native vertical quote bar with neat stacked lines.\n\n"
            "• <b>🔽 Collapse Under Spoiler:</b> Expandable blockquote (tap arrow to expand info).\n\n"
            "• <b>🚫 Hide Header:</b> Minimalist output — only model response is shown.\n\n"
            "Select desired option:"
        )

    await callback.message.edit_text(
        title,
        reply_markup=get_header_style_keyboard(current_style=cur_style, lang_code=lang_code),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("set_header_style:"))
async def handle_set_header_style(callback: CallbackQuery):
    """Saves new header style and refreshes settings."""
    user_id = callback.from_user.id
    new_style = callback.data.split("set_header_style:")[1]
    await db_manager.set_user_header_style(user_id, new_style)
    ans_text = "Стиль шапки обновлен" if (await db_manager.get_user_language(user_id)) == "ru" else "Header style updated"
    await callback.answer(ans_text)
    text, keyboard = await render_settings_view(user_id)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# --- Format Switching ---

@router.callback_query(F.data == "settings_format")
async def handle_settings_format(callback: CallbackQuery):
    """Presents format selector."""
    await callback.answer()
    user_id = callback.from_user.id
    settings = await db_manager.get_user_settings(user_id) or {}
    cur_fmt = settings.get("message_format", "rich")
    lang_code = settings.get("language_code", "ru")

    title = (
        "⚡ <b>Формат отображения сообщений:</b>\n\n"
        "• <b>Rich Messages (10.1+):</b> Продвинутый режим (формулы KaTeX в Unicode, моноширинные таблицы, сворачивание размышлений).\n\n"
        "• <b>Классический (Markdown):</b> Стандартный режим Telegram."
        if lang_code == "ru" else
        "⚡ <b>Message Display Format:</b>\n\n"
        "• <b>Rich Messages (10.1+):</b> Advanced mode (KaTeX math in Unicode, neat tables, spoiler thoughts).\n\n"
        "• <b>Classic (Markdown):</b> Standard Telegram format."
    )
    await callback.message.edit_text(
        title,
        reply_markup=get_format_keyboard(current_format=cur_fmt, lang_code=lang_code),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("set_format:"))
async def handle_set_format(callback: CallbackQuery):
    """Saves new format and refreshes settings."""
    user_id = callback.from_user.id
    new_fmt = callback.data.split("set_format:")[1]
    await db_manager.set_user_message_format(user_id, new_fmt)
    await callback.answer("Формат обновлен" if (await db_manager.get_user_language(user_id)) == "ru" else "Format updated")
    text, keyboard = await render_settings_view(user_id)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# --- Thinking Budget Switching ---

@router.callback_query(F.data == "settings_thinking")
async def handle_settings_thinking(callback: CallbackQuery):
    """Presents thinking budget selector."""
    await callback.answer()
    user_id = callback.from_user.id
    settings = await db_manager.get_user_settings(user_id) or {}
    cur_budget = settings.get("thinking_budget", 1024)
    lang_code = settings.get("language_code", "ru")

    title = (
        "🧠 <b>Глубина размышлений модели (Thinking Budget):</b>\n\n"
        "• <b>0:</b> ⚡ Мгновенно — без фазы размышлений.\n"
        "• <b>1024:</b> ⚖️ Баланс — оптимально для большинства задач.\n"
        "• <b>4096:</b> 🔬 Глубокий анализ — для сложной математики, логики и кода."
        if lang_code == "ru" else
        "🧠 <b>Thinking Budget Depth:</b>\n\n"
        "• <b>0:</b> ⚡ Instant — without thinking phase.\n"
        "• <b>1024:</b> ⚖️ Balanced — optimal for general queries.\n"
        "• <b>4096:</b> 🔬 Deep Analysis — for complex math, logic and coding."
    )
    await callback.message.edit_text(
        title,
        reply_markup=get_thinking_budget_keyboard(current_budget=cur_budget, lang_code=lang_code),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("set_thinking:"))
async def handle_set_thinking(callback: CallbackQuery):
    """Saves thinking budget and refreshes settings."""
    user_id = callback.from_user.id
    budget = int(callback.data.split("set_thinking:")[1])
    await db_manager.set_user_thinking_budget(user_id, budget)
    await callback.answer("Бюджет размышлений обновлен" if (await db_manager.get_user_language(user_id)) == "ru" else "Budget updated")
    text, keyboard = await render_settings_view(user_id)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# --- Python Sandbox & Google Search Toggles ---

@router.callback_query(F.data == "settings_toggle_code_exec")
async def handle_toggle_code_exec(callback: CallbackQuery):
    """Toggles python sandbox tool."""
    user_id = callback.from_user.id
    new_state = await db_manager.toggle_user_code_execution(user_id)
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)
    if active_dialog_id:
        gemini_service.reset_dialog_chat(active_dialog_id)
    lang_code = await db_manager.get_user_language(user_id)
    if lang_code == "ru":
        ans = "Песочница Python включена" if new_state else "Песочница Python выключена"
    else:
        ans = "Python Sandbox enabled" if new_state else "Python Sandbox disabled"
    await callback.answer(ans)
    text, keyboard = await render_settings_view(user_id)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "settings_toggle_search")
async def handle_toggle_search(callback: CallbackQuery):
    """Toggles Google search tool."""
    user_id = callback.from_user.id
    new_state = await db_manager.toggle_user_google_search(user_id)
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)
    if active_dialog_id:
        gemini_service.reset_dialog_chat(active_dialog_id)
    lang_code = await db_manager.get_user_language(user_id)
    if lang_code == "ru":
        ans = "Поиск Google включен" if new_state else "Поиск Google выключен"
    else:
        ans = "Google Search enabled" if new_state else "Google Search disabled"
    await callback.answer(ans)
    text, keyboard = await render_settings_view(user_id)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# --- Personas, Styles, Language & Models ---

@router.callback_query(F.data == "settings_personas")
async def handle_settings_personas(callback: CallbackQuery):
    """Presents personas selector."""
    await callback.answer()
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    cur_persona = await db_manager.get_user_persona(user_id)

    buttons = []
    for pid, pdata in BOT_PERSONAS.items():
        name = pdata.get(f"name_{lang_code}", pdata.get("name_ru", pid))
        check = "✅ " if pid == cur_persona else ""
        buttons.append([InlineKeyboardButton(text=f"{check}{name}", callback_data=f"{CALLBACK_SETTINGS_PERSONA_PREFIX}{pid}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад в настройки" if lang_code == "ru" else "⬅️ Back", callback_data="menu_settings")])

    title = loc.get_text('persona_selection_title', lang_code) + "\n\n" + loc.get_text('persona_selection_desc', lang_code)
    await callback.message.edit_text(title, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data.startswith(CALLBACK_SETTINGS_PERSONA_PREFIX))
async def handle_set_persona(callback: CallbackQuery):
    """Saves persona in DB."""
    user_id = callback.from_user.id
    persona_id = callback.data.replace(CALLBACK_SETTINGS_PERSONA_PREFIX, "")
    await db_manager.set_user_persona(user_id, persona_id)
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)
    if active_dialog_id:
        gemini_service.reset_dialog_chat(active_dialog_id)
    lang_code = await db_manager.get_user_language(user_id)
    await callback.answer("Персона сохранена" if lang_code == "ru" else "Persona saved")
    text, keyboard = await render_settings_view(user_id)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "settings_styles")
async def handle_settings_styles(callback: CallbackQuery):
    """Presents style selector."""
    await callback.answer()
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    cur_style = await db_manager.get_user_bot_style(user_id)

    buttons = []
    for scode, sname in BOT_STYLES.items():
        check = "✅ " if scode == cur_style else ""
        buttons.append([InlineKeyboardButton(text=f"{check}{sname}", callback_data=f"{CALLBACK_SETTINGS_STYLE_PREFIX}{scode}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад в настройки" if lang_code == "ru" else "⬅️ Back", callback_data="menu_settings")])

    title = "🎨 <b>Выберите стиль общения:</b>" if lang_code == "ru" else "🎨 <b>Choose Communication Style:</b>"
    await callback.message.edit_text(title, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data.startswith(CALLBACK_SETTINGS_STYLE_PREFIX))
async def handle_set_style(callback: CallbackQuery):
    """Saves style in DB."""
    user_id = callback.from_user.id
    style_code = callback.data.replace(CALLBACK_SETTINGS_STYLE_PREFIX, "")
    await db_manager.set_user_bot_style(user_id, style_code)
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)
    if active_dialog_id:
        gemini_service.reset_dialog_chat(active_dialog_id)
    lang_code = await db_manager.get_user_language(user_id)
    await callback.answer("Стиль сохранен" if lang_code == "ru" else "Style saved")
    text, keyboard = await render_settings_view(user_id)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# Cache for models list to provide instant pagination without hammering Google API: user_id -> (timestamp, models)
_models_cache: dict = {}

async def _get_models_for_user(user_id: int):
    api_key = await db_manager.get_user_api_key(user_id)
    if not api_key:
        return [], "no_key"

    now = time.time()
    if user_id in _models_cache:
        cached_time, cached_models = _models_cache[user_id]
        if now - cached_time < 300: # 5 minutes cache
            return cached_models, None

    try:
        models_service = gemini_service.GeminiService(api_key=api_key)
        models = await models_service.get_available_models()
        if models:
            _models_cache[user_id] = (now, models)
            return models, None
        return [], "empty"
    except Exception as e:
        logger.error(f"Error fetching models from API for user {user_id}: {e}")
        return [], "error"


@router.callback_query(F.data == "settings_models")
async def handle_settings_models(callback: CallbackQuery):
    """Fetches and displays available Gemini models from API with pagination."""
    await callback.answer()
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    cur_model = await db_manager.get_user_gemini_model(user_id) or DEFAULT_MODEL_ID

    models, err = await _get_models_for_user(user_id)
    if err == "no_key":
        alert_text = loc.get_text('api_key_needed_for_feature', lang_code)
        await callback.message.answer(alert_text)
        return
    if not models:
        err_text = loc.get_text('model_selection_error', lang_code)
        await callback.message.answer(err_text)
        return

    keyboard = get_model_selection_keyboard(
        models=models,
        current_model=cur_model,
        page=0,
        page_size=8,
        lang_code=lang_code
    )
    title = "🤖 <b>Выберите модель Gemini:</b>" if lang_code == "ru" else "🤖 <b>Choose Gemini Model:</b>"
    await callback.message.edit_text(title, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("models_page:"))
async def handle_models_page(callback: CallbackQuery):
    """Handles pagination arrows for model selection."""
    await callback.answer()
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    cur_model = await db_manager.get_user_gemini_model(user_id) or DEFAULT_MODEL_ID
    page = int(callback.data.split("models_page:")[1])

    models, _ = await _get_models_for_user(user_id)
    if not models:
        return

    keyboard = get_model_selection_keyboard(
        models=models,
        current_model=cur_model,
        page=page,
        page_size=8,
        lang_code=lang_code
    )
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        title = "🤖 <b>Выберите модель Gemini:</b>" if lang_code == "ru" else "🤖 <b>Choose Gemini Model:</b>"
        await callback.message.edit_text(title, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith(CALLBACK_SETTINGS_MODEL_PREFIX))
async def handle_set_model(callback: CallbackQuery):
    """Saves chosen model in DB."""
    user_id = callback.from_user.id
    model_id = callback.data.replace(CALLBACK_SETTINGS_MODEL_PREFIX, "")
    await db_manager.set_user_gemini_model(user_id, model_id)
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)
    if active_dialog_id:
        gemini_service.reset_dialog_chat(active_dialog_id)
    lang_code = await db_manager.get_user_language(user_id)
    await callback.answer("Модель изменена" if lang_code == "ru" else "Model changed")
    text, keyboard = await render_settings_view(user_id)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "settings_language")
async def handle_settings_language(callback: CallbackQuery):
    """Presents interface language selector."""
    await callback.answer()
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    title = "🌐 <b>Выберите язык интерфейса:</b>" if lang_code == "ru" else "🌐 <b>Select Interface Language:</b>"
    await callback.message.edit_text(title, reply_markup=get_language_keyboard(lang_code, lang_code), parse_mode="HTML")


@router.callback_query(F.data.startswith(CALLBACK_SETTINGS_LANG_PREFIX))
async def handle_set_language(callback: CallbackQuery):
    """Saves interface language in DB and refreshes both inline view and bottom reply keyboard."""
    user_id = callback.from_user.id
    new_lang = callback.data.replace(CALLBACK_SETTINGS_LANG_PREFIX, "")
    await db_manager.set_user_language(user_id, new_lang)
    ans = "Язык сохранен" if new_lang == "ru" else "Language saved"
    await callback.answer(ans)
    text, keyboard = await render_settings_view(user_id)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

    notice = (
        "🌐 Язык интерфейса изменен на Русский."
        if new_lang == "ru"
        else "🌐 Interface language changed to English."
    )
    await callback.message.answer(notice, reply_markup=create_main_keyboard(new_lang, user_id))


@router.callback_query(F.data == "settings_api_key")
async def handle_settings_api_key(callback: CallbackQuery, state: FSMContext):
    """Prompts for new API key."""
    await callback.answer()
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    await state.set_state(SettingsStates.waiting_for_api_key)
    prompt = loc.get_text('set_api_key_prompt', lang_code)
    await callback.message.answer(prompt)


@router.message(SettingsStates.waiting_for_api_key)
async def process_new_api_key(message: Message, state: FSMContext):
    """Validates and saves new API key."""
    user_id = message.from_user.id
    raw_key = message.text.strip()
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
