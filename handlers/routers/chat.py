"""
Chat router for MyGemini (aiogram 3.x).
Handles:
- Text messages with real-time streaming via MessageStreamThrottler
- Multimodal inputs: Photos (PIL) and Voice notes (audio/ogg)
- Context headers (Dialog, Persona, Model, Python sandbox mode) with HUD and 3 styles
- Quick actions: [⏹️ Стоп], [🔄 Еще раз], [↩️ Откатить шаг], [📥 Экспорт в .md]
- Automatic 429 quota fallback to gemini-2.5-flash-lite
"""

import datetime
from io import BytesIO
from typing import Dict, Optional, List, Any
import PIL.Image
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from google.genai import types

from config.settings import DEFAULT_MODEL_ID, BOT_PERSONAS, BOT_STYLES, ADMIN_USER_ID
from database import db_manager
from utils import localization as loc
from keyboards.aiogram_inline import (
    get_chat_quick_actions_keyboard, get_streaming_stop_keyboard,
    get_sandbox_cancel_keyboard
)
from services.gemini_service import GeminiService, GeminiQuotaExceededException
from services.throttler import MessageStreamThrottler
from services import promo_service
from logger_config import get_logger

logger = get_logger(__name__)

router = Router(name="chat_router")


class SandboxStates(StatesGroup):
    waiting_for_sandbox_prompt = State()


# Active streams registry: chat_id -> MessageStreamThrottler
active_streams: Dict[int, MessageStreamThrottler] = {}


TELEGRAM_BASE_INSTRUCTION_RU = (
    "Ты — полезный интеллектуальный ассистент в мессенджере Telegram.\n"
    "Строгие правила разметки и форматирования текста для Telegram:\n"
    "1. Никогда не используй HTML-теги веб-страниц (<details>, <summary>, <span>, <div>, <script>, атрибуты style/class/onmouseover).\n"
    "2. Для спойлеров и скрытого текста используй нативный синтаксис Telegram: ||скрытый текст||.\n"
    "3. Для математических формул ВСЕГДА используй синтаксис LaTeX, обёрнутый в знаки доллара: $...$ для строчных формул (например, $E = mc^2$) или $$...$$ для отдельных выключных блоков формул.\n"
    "4. Для таблиц используй стандартный Markdown (| Заголовок 1 | Заголовок 2 |).\n"
    "5. Для блоков кода используй тройные кавычки с языком: ```python ... ```."
)

TELEGRAM_BASE_INSTRUCTION_EN = (
    "You are a helpful assistant in the Telegram messenger.\n"
    "Strict Telegram text formatting rules:\n"
    "1. Never use web-browser HTML tags (<details>, <summary>, <span>, <div>, <script>, or style/class/onmouseover attributes).\n"
    "2. For spoilers and hidden text, use native Telegram syntax: ||hidden text||.\n"
    "3. For mathematical formulas, ALWAYS use LaTeX wrapped in dollar signs: $...$ for inline (e.g. $E = mc^2$) or $$...$$ for block formulas.\n"
    "4. For tables, use standard Markdown (| Header 1 | Header 2 |).\n"
    "5. For code blocks, use triple backticks with language tag: ```python ... ```."
)


def build_system_instruction(persona_id: str, bot_style: str, lang_code: str) -> str:
    """Builds system prompt based on Telegram rules, persona and style."""
    base = TELEGRAM_BASE_INSTRUCTION_RU if lang_code == "ru" else TELEGRAM_BASE_INSTRUCTION_EN
    instructions = [base]
    if persona_id and persona_id != "default":
        pinfo = BOT_PERSONAS.get(persona_id, {})
        prompt = pinfo.get(f"prompt_{lang_code}", pinfo.get("prompt_ru", ""))
        if prompt:
            instructions.append(prompt)
    elif bot_style and bot_style != "default":
        s_instructions = {
            "concise": "Будь максимально кратким и лаконичным. Отвечай по существу.",
            "detailed": "Давай развернутые, подробные и исчерпывающие ответы с пояснениями.",
            "friendly": "Общайся тепло, дружелюбно и участливо, с легким юмором.",
            "professional": "Отвечай строго профессионально, в академическом или деловом тоне."
        }
        if bot_style in s_instructions:
            instructions.append(s_instructions[bot_style])

    return "\n\n".join(instructions)



# ===================================================================================
# --- QUICK ACTION CALLBACKS ---
# ===================================================================================

@router.callback_query(F.data == "chat_action:stop")
async def handle_stop_action(callback: CallbackQuery):
    """Aborts running generation stream."""
    chat_id = callback.message.chat.id
    throttler = active_streams.get(chat_id)
    if throttler:
        throttler.abort()
        await callback.answer("Генерация остановлена" if (callback.from_user.language_code or "ru") == "ru" else "Generation stopped")
    else:
        await callback.answer("Стрим уже завершен" if (callback.from_user.language_code or "ru") == "ru" else "Stream already finished")


@router.callback_query(F.data == "chat_action:undo")
async def handle_undo_action(callback: CallbackQuery):
    """Deletes the last conversation turn (bot answer + user prompt)."""
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)

    if not active_dialog_id:
        await callback.answer("Нет активного диалога", show_alert=True)
        return

    success = await db_manager.delete_last_conversation_turn(active_dialog_id)
    if success:
        notice = "↩️ Последний шаг отменен. Контекст очищен." if lang_code == "ru" else "↩️ Last step undone. Context cleared."
        await callback.answer(notice, show_alert=True)
        try:
            await callback.message.edit_text(f"<i>{notice}</i>", parse_mode="HTML")
        except Exception:
            pass
    else:
        await callback.answer("Нечего отменять" if lang_code == "ru" else "Nothing to undo", show_alert=True)


@router.callback_query(F.data == "chat_action:regen")
async def handle_regen_action(callback: CallbackQuery, bot: Bot):
    """Re-generates the last assistant response."""
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)

    if not active_dialog_id:
        await callback.answer("Нет активного диалога", show_alert=True)
        return

    # Delete last assistant message
    deleted = await db_manager.delete_last_assistant_message(active_dialog_id)
    if not deleted:
        await callback.answer("Нет ответа для регенерации" if lang_code == "ru" else "No response to regenerate", show_alert=True)
        return

    # Fetch last user message in dialog
    history = await db_manager.get_conversation_history(active_dialog_id, limit=2)
    last_user_msg = next((m['message_text'] for m in reversed(history) if m['role'] == 'user'), None)
    if not last_user_msg:
        await callback.answer("Не найден исходный вопрос" if lang_code == "ru" else "Original question not found", show_alert=True)
        return

    await callback.answer("Регенерирую ответ..." if lang_code == "ru" else "Regenerating response...")
    await generate_and_stream_response(
        bot=bot,
        chat_id=callback.message.chat.id,
        user_id=user_id,
        prompt_text=last_user_msg,
        reply_to_msg=callback.message,
        is_regen=True
    )


@router.callback_query(F.data == "chat_action:sandbox")
async def handle_sandbox_action(callback: CallbackQuery, state: FSMContext):
    """Enters dedicated isolated Python sandbox computation mode."""
    user_id = callback.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    api_key = await db_manager.get_user_api_key(user_id)
    if not api_key:
        await callback.answer(loc.get_text('api_key_needed_for_chat', lang_code), show_alert=True)
        return

    active_dialog_id = await db_manager.get_active_dialog_id(user_id)
    if not active_dialog_id:
        active_dialog_id = await db_manager.create_dialog(user_id, "Основной диалог" if lang_code == "ru" else "Main Dialogue", set_active=True)

    await state.set_state(SandboxStates.waiting_for_sandbox_prompt)
    await state.update_data(active_dialog_id=active_dialog_id)

    if lang_code == "ru":
        intro_text = (
            "🐍 <b>Песочница Python (Изолированные вычисления)</b>\n\n"
            "В этом режиме вы можете решать любые задачи, требующие абсолютной точности расчётов, без риска фантазий и галлюцинаций модели:\n\n"
            "• ⚙️ <b>Настоящий интерпретатор:</b> Модель пишет скрипт, а код физически выполняется на серверах Google в безопасной облачной среде Python.\n"
            "• 🎯 <b>Чистый лист:</b> Запрос выполняется изолированно — предыдущая переписка не передаётся, что исключает ошибки контекста.\n"
            "• 💾 <b>Сквозная история:</b> Как только расчёт завершится, ваш вопрос и проверенный результат автоматически сохранятся в текущий диалог.\n\n"
            "<b>Что здесь можно делать:</b>\n"
            "1. <b>Математика:</b> простые числа, факториалы, уравнения, матрицы, интегралы.\n"
            "2. <b>Анализ текста:</b> точный подсчёт символов, частотности букв, слов, поиск паттернов.\n"
            "3. <b>Статистика и логика:</b> комбинаторика, вероятности, симуляции, алгоритмы.\n"
            "4. <b>Таблицы и списки:</b> сортировка, группировка, сложные фильтрации данных.\n\n"
            "✍️ <i>Введите задачу, формулу или код для расчёта:</i>"
        )
    else:
        intro_text = (
            "🐍 <b>Python Sandbox (Isolated Computation)</b>\n\n"
            "In this mode, you can solve any tasks requiring absolute computational accuracy without hallucinations:\n\n"
            "• ⚙️ <b>Real Interpreter:</b> Code runs physically in a secure cloud Python sandbox on Google servers.\n"
            "• 🎯 <b>Clean Slate:</b> The prompt is processed in complete isolation — past dialogue history is not sent.\n"
            "• 💾 <b>Seamless History:</b> Once computation finishes, both your query and the verified result are saved to the active dialogue.\n\n"
            "<b>What you can calculate here:</b>\n"
            "1. <b>Mathematics:</b> prime numbers, factorials, equations, matrices, integrals.\n"
            "2. <b>Text Analysis:</b> exact character counts, letter/word frequencies, pattern matching.\n"
            "3. <b>Statistics & Logic:</b> combinatorics, probability, simulations, sorting.\n"
            "4. <b>Data & Lists:</b> complex filtering, aggregation, transforms.\n\n"
            "✍️ <i>Enter your problem, formula, or code to compute:</i>"
        )

    await callback.answer()
    await callback.message.answer(
        intro_text,
        reply_markup=get_sandbox_cancel_keyboard(lang_code),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "chat_action:sandbox_cancel")
async def handle_sandbox_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancels dedicated sandbox prompt mode and returns to normal chat."""
    await state.clear()
    lang_code = await db_manager.get_user_language(callback.from_user.id)
    cancel_text = (
        "❌ <b>Режим песочницы отменён.</b>\nВы вернулись в обычный диалог."
        if lang_code == "ru"
        else "❌ <b>Sandbox mode cancelled.</b>\nYou returned to normal chat."
    )
    await callback.answer()
    try:
        await callback.message.edit_text(cancel_text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(cancel_text, parse_mode="HTML")


@router.message(SandboxStates.waiting_for_sandbox_prompt)
async def handle_sandbox_prompt(message: Message, bot: Bot, state: FSMContext):
    """Executes prompt in dedicated isolated sandbox mode."""
    user_text = message.text or ""
    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)

    if not message.text:
        err_text = (
            "⚠️ Пожалуйста, отправьте текстовую задачу, формулу или код для расчёта в песочнице:"
            if lang_code == "ru"
            else "⚠️ Please send a text task, formula, or code to compute in the sandbox:"
        )
        await message.answer(err_text, reply_markup=get_sandbox_cancel_keyboard(lang_code))
        return

    if user_text.strip().lower() in ["/cancel", "отмена", "cancel"]:
        await state.clear()
        cancel_text = (
            "❌ <b>Режим песочницы отменён.</b>\nВы вернулись в обычный диалог."
            if lang_code == "ru"
            else "❌ <b>Sandbox mode cancelled.</b>\nYou returned to normal chat."
        )
        await message.answer(cancel_text, parse_mode="HTML")
        return

    await state.clear()
    await generate_and_stream_response(
        bot=bot,
        chat_id=message.chat.id,
        user_id=user_id,
        prompt_text=user_text,
        reply_to_msg=message,
        is_sandbox_isolated=True
    )


# ===================================================================================
# --- MESSAGE HANDLERS: TEXT, PHOTO, VOICE ---
# ===================================================================================

@router.message(F.text)
async def handle_text_message(message: Message, bot: Bot, state: FSMContext):
    """Handles standard user text prompt."""
    # Ignore commands or FSM states handled elsewhere
    if message.text.startswith("/"):
        return
    current_state = await state.get_state()
    if current_state is not None:
        return

    await generate_and_stream_response(
        bot=bot,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        prompt_text=message.text,
        reply_to_msg=message
    )


@router.message(F.photo)
async def handle_photo_message(message: Message, bot: Bot, state: FSMContext):
    """Handles multimodal image prompt."""
    current_state = await state.get_state()
    if current_state is not None:
        return

    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    api_key = await db_manager.get_user_api_key(user_id)
    if not api_key:
        await message.answer(loc.get_text('api_key_needed_for_vision', lang_code))
        return

    # Download image bytes
    photo = message.photo[-1]
    file_io = BytesIO()
    await bot.download(photo, destination=file_io)
    file_io.seek(0)
    image = PIL.Image.open(file_io)

    caption = message.caption or ("Опиши это изображение подробно." if lang_code == "ru" else "Describe this image in detail.")
    await generate_and_stream_response(
        bot=bot,
        chat_id=message.chat.id,
        user_id=user_id,
        prompt_text=caption,
        image_input=image,
        reply_to_msg=message
    )


@router.message(F.voice)
async def handle_voice_message(message: Message, bot: Bot, state: FSMContext):
    """Handles voice note input."""
    current_state = await state.get_state()
    if current_state is not None:
        return

    user_id = message.from_user.id
    lang_code = await db_manager.get_user_language(user_id)
    api_key = await db_manager.get_user_api_key(user_id)
    if not api_key:
        await message.answer(loc.get_text('api_key_needed_for_chat', lang_code))
        return

    # Download voice bytes
    voice_io = BytesIO()
    await bot.download(message.voice, destination=voice_io)
    voice_bytes = voice_io.getvalue()

    prompt_voice = "Расшифруй это аудиосообщение и ответь на него." if lang_code == "ru" else "Transcribe and answer this voice message."
    await generate_and_stream_response(
        bot=bot,
        chat_id=message.chat.id,
        user_id=user_id,
        prompt_text=prompt_voice,
        voice_bytes=voice_bytes,
        reply_to_msg=message
    )


# ===================================================================================
# --- CORE GENERATION & STREAMING ENGINE ---
# ===================================================================================

async def generate_and_stream_response(
    bot: Bot,
    chat_id: int,
    user_id: int,
    prompt_text: str,
    reply_to_msg: Message,
    image_input: Optional[PIL.Image.Image] = None,
    voice_bytes: Optional[bytes] = None,
    is_regen: bool = False,
    is_sandbox_isolated: bool = False
):
    """Main generation pipeline coordinating context headers, tools, and streaming throttler."""
    lang_code = await db_manager.get_user_language(user_id)
    api_key = await db_manager.get_user_api_key(user_id)

    if not api_key:
        await reply_to_msg.answer(loc.get_text('api_key_needed_for_chat', lang_code))
        return

    # Ensure active dialog
    active_dialog_id = await db_manager.get_active_dialog_id(user_id)
    if not active_dialog_id:
        active_dialog_id = await db_manager.create_dialog(user_id, "Основной диалог" if lang_code == "ru" else "Main Dialogue", set_active=True)

    dialog_info = await db_manager.get_dialog_info(active_dialog_id)
    dialog_title = dialog_info.get("name", "Основной диалог") if dialog_info else "Основной диалог"

    # Fetch user configuration
    settings = await db_manager.get_user_settings(user_id) or {}
    model_id = settings.get("gemini_model") or DEFAULT_MODEL_ID
    persona_id = settings.get("active_persona") or "default"
    bot_style = settings.get("bot_style") or "default"
    header_style = settings.get("header_style") or "blockquote"
    message_format = settings.get("message_format") or "rich"
    thinking_budget = settings.get("thinking_budget", 1024)
    code_execution = bool(settings.get("enable_code_execution", 0)) or is_sandbox_isolated
    google_search = bool(settings.get("enable_google_search", 0)) and not is_sandbox_isolated

    # Build context header
    persona_info = BOT_PERSONAS.get(persona_id, BOT_PERSONAS.get("default", {}))
    persona_name = persona_info.get("name_ru" if lang_code == "ru" else "name_en", persona_id)

    if header_style == "hidden":
        context_header = ""
        header_summary = ""
    elif is_sandbox_isolated:
        header_summary = f"💬 {dialog_title} • 🐍 Sandbox • ⚡ {model_id}"
        context_header = (
            f"> 💬 **Диалог:** {dialog_title}\n"
            f"> 🐍 **Режим:** Изолированная песочница Python\n"
            f"> ⚡ **Модель:** {model_id}\n\n"
        ) if lang_code == "ru" else (
            f"> 💬 **Dialogue:** {dialog_title}\n"
            f"> 🐍 **Mode:** Isolated Python Sandbox\n"
            f"> ⚡ **Model:** {model_id}\n\n"
        )
    else:
        header_summary = f"💬 {dialog_title} • ⚡ {model_id}"
        context_header = (
            f"> 💬 **Диалог:** {dialog_title}\n"
            f"> 🎭 **Персона:** {persona_name}\n"
            f"> ⚡ **Модель:** {model_id}\n\n"
        ) if lang_code == "ru" else (
            f"> 💬 **Dialogue:** {dialog_title}\n"
            f"> 🎭 **Persona:** {persona_name}\n"
            f"> ⚡ **Model:** {model_id}\n\n"
        )

    # Placeholder message
    if is_sandbox_isolated:
        placeholder_text = "🐍 <i>Запускаю песочницу Python...</i>" if lang_code == "ru" else "🐍 <i>Launching Python sandbox...</i>"
    else:
        placeholder_text = "💭 <i>Думаю...</i>" if lang_code == "ru" else "💭 <i>Thinking...</i>"

    placeholder_msg = await reply_to_msg.answer(placeholder_text, parse_mode="HTML")

    throttler = MessageStreamThrottler(
        bot=bot,
        chat_id=chat_id,
        initial_message=placeholder_msg,
        header_text=context_header,
        header_summary=header_summary,
        message_format=message_format,
        header_style=header_style,
        thinking_summary="Размышления" if lang_code == "ru" else "Thinking",
        stop_keyboard=get_streaming_stop_keyboard(lang_code),
        quick_actions_keyboard=get_chat_quick_actions_keyboard(lang_code, dialog_id=active_dialog_id, enable_code_execution=True),
    )
    active_streams[chat_id] = throttler

    # Save user message in DB if not regenerating
    if not is_regen:
        await db_manager.store_message(
            user_id=user_id,
            dialog_id=active_dialog_id,
            role="user",
            message_text=prompt_text,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0
        )

    # Build contents with context history (only when not isolated)
    contents: List[types.Content] = []
    if not is_sandbox_isolated:
        history_records = await db_manager.get_conversation_history(active_dialog_id, limit=12)
        # Exclude the very last user message if we just stored it (to avoid duplication with prompt)
        if not is_regen and history_records and history_records[-1]['message_text'] == prompt_text:
            history_records = history_records[:-1]

        for h in history_records:
            role = "user" if h['role'] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=h['message_text'])]))

    # Add active prompt parts
    prompt_parts = []
    if image_input:
        img_byte_arr = BytesIO()
        image_input.save(img_byte_arr, format='JPEG')
        prompt_parts.append(types.Part.from_bytes(data=img_byte_arr.getvalue(), mime_type="image/jpeg"))
    elif voice_bytes:
        prompt_parts.append(types.Part.from_bytes(data=voice_bytes, mime_type="audio/ogg"))

    prompt_parts.append(types.Part.from_text(text=prompt_text))
    contents.append(types.Content(role="user", parts=prompt_parts))

    if is_sandbox_isolated:
        system_instruction = (
            "Ты — специализированный вычислительный движок на базе Python. Твоя единственная цель — "
            "предоставить математически, алгоритмически и фактически точный результат. "
            "Для любых расчетов, подсчета символов, слов, частотности, сортировки, обработки списков или математических операций "
            "ты ОБЯЗАН написать и запустить исполняемый код с помощью встроенного инструмента code_execution. "
            "НИКОГДА не угадывай, не выдумывай и не симулируй вывод в тексте без фактического запуска в песочнице. "
            "Свои выводы и объяснения строй строго на базе реального вывода выполнения кода."
            if lang_code == "ru" else
            "You are a specialized Python computation engine. Your sole objective is to provide mathematically, "
            "algorithmically, and computationally accurate results. "
            "You MUST ALWAYS generate and execute Python code using your code_execution tool for any calculations, "
            "counting, string parsing, sorting, or data analysis. "
            "NEVER guess, estimate, or simulate results in plain text without running the code. "
            "Base your final explanation strictly on the actual execution output."
        )
    else:
        system_instruction = build_system_instruction(persona_id, bot_style, lang_code)
        if code_execution:
            code_exec_guidance = (
                "\n\n[ВАЖНО: Доступен инструмент code_execution. При математических расчетах, "
                "моделировании, подсчетах или анализе данных используй исполняемый код Python.]"
                if lang_code == "ru" else
                "\n\n[IMPORTANT: code_execution tool is available. For mathematical calculations, "
                "simulations, counting, or data analysis, use executable Python code.]"
            )
            if system_instruction:
                system_instruction += code_exec_guidance
            else:
                system_instruction = code_exec_guidance.strip()

    gemini_client = GeminiService(api_key=api_key)

    try:
        stream = gemini_client.generate_stream(
            model_id=model_id,
            contents=contents,
            system_instruction=system_instruction,
            enable_search=google_search,
            enable_code_execution=code_execution,
            thinking_budget=thinking_budget,
        )

        async for chunk in stream:
            if throttler.is_aborted:
                break
            throttler.update_usage_from_chunk(chunk)
            await throttler.handle_chunk(str(chunk))

        if gemini_client.fallback_model:
            notice = (
                f"*⚠️ Квота основной модели исчерпана. Ответ сгенерирован {gemini_client.fallback_model}.*"
                if lang_code == "ru" else
                f"*⚠️ Primary model quota exceeded. Answer generated by {gemini_client.fallback_model}.*"
            )
            throttler.set_fallback_notice(notice)
            throttler.set_fallback_model(gemini_client.fallback_model, lang_code=lang_code)

    except GeminiQuotaExceededException:
        quota_err = (
            "⏳ **Превышена квота запросов (429).**\n"
            "Пожалуйста, подождите 1–2 минуты или выберите другую модель через ⚙️ Настройки."
            if lang_code == "ru" else
            "⏳ **Quota Exceeded (429).**\nPlease wait 1-2 minutes or switch models via ⚙️ Settings."
        )
        await throttler.handle_chunk(f"\n\n{quota_err}")
    except Exception as e:
        logger.exception(f"Error during chat generation: {e}")
        err_text = (
            f"\n\n⚠️ *Произошла ошибка при генерации ответа: {e}*"
            if lang_code == "ru" else
            f"\n\n⚠️ *Generation error occurred: {e}*"
        )
        await throttler.handle_chunk(err_text)
    finally:
        full_response = await throttler.finalize()
        active_streams.pop(chat_id, None)

        # Store response in DB
        p_tok = throttler.prompt_tokens or 0
        c_tok = throttler.candidates_tokens or 0
        t_tok = throttler.total_tokens or (p_tok + c_tok)

        await db_manager.store_message(
            user_id=user_id,
            dialog_id=active_dialog_id,
            role="bot",
            message_text=full_response,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=t_tok
        )
