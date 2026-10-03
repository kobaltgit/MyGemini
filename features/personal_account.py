# File: features/personal_account.py
import html
from datetime import datetime
from typing import Optional, List, Dict, Any

from database import db_manager
from config.settings import BOT_PERSONAS
from utils.analysis_helpers import extract_frequent_topics
from services.gemini_service import generate_content_simple
from logger_config import get_logger

logger = get_logger(__name__, user_id='System')

USER_TITLES_RU: Dict[int, str] = {
    0: "Новичок", 100: "Активный пользователь", 500: "Ветеран чата",
    1000: "Мастер общения", 5000: "Легенда",
}

USER_TITLES_EN: Dict[int, str] = {
    0: "Newcomer", 100: "Active User", 500: "Chat Veteran",
    1000: "Master of Conversation", 5000: "Legend",
}

def _get_user_title(message_count: int, lang_code: str = 'ru') -> str:
    titles = USER_TITLES_RU if lang_code == 'ru' else USER_TITLES_EN
    title: str = titles[0]
    for messages, current_title in sorted(titles.items(), reverse=True):
        if message_count >= messages:
            title = current_title
            break
    return title

def _get_days_since_start(first_interaction_date_str: Optional[str], lang_code: str = 'ru') -> str:
    if not first_interaction_date_str:
        return "Неизвестно" if lang_code == 'ru' else "Unknown"
    try:
        first_interaction_date = datetime.strptime(first_interaction_date_str, '%Y-%m-%d').date()
        days: int = (datetime.now().date() - first_interaction_date).days
        return str(max(0, days))
    except ValueError:
        return "Ошибка" if lang_code == 'ru' else "Error"

async def _get_topic_description(user_id: int, api_key: str, active_dialog_id: int, lang_code: str = 'ru') -> str:
    try:
        conversation_history_raw = await db_manager.get_conversation_history(active_dialog_id, limit=50)
        if not conversation_history_raw:
             return "Пока недостаточно данных для анализа в этом диалоге." if lang_code == 'ru' else "Not enough data for topic analysis yet."

        frequent_topics = extract_frequent_topics(conversation_history_raw, top_n=7)
        if not frequent_topics:
            return "Пока недостаточно данных для анализа в этом диалоге." if lang_code == 'ru' else "Not enough data for topic analysis yet."

        topics_str = ', '.join(frequent_topics)
        if lang_code == 'ru':
            prompt = f"""Analyze the following keywords from a user's conversation with a chatbot: {topics_str}.
Briefly (in 1-2 sentences in Russian) describe the main topics the user discusses. Make the description generalized and positive.
Start the response with 'Чаще всего в этом диалоге вы обсуждаете' or a similar phrase."""
        else:
            prompt = f"""Analyze the following keywords from a user's conversation with a chatbot: {topics_str}.
Briefly (in 1-2 sentences in English) describe the main topics the user discusses. Make the description generalized and positive.
Start the response with 'Most often in this dialog you discuss' or a similar phrase."""

        ai_description = await generate_content_simple(api_key, prompt)
        return ai_description.strip() if ai_description else (f"Ключевые слова: {topics_str}" if lang_code == 'ru' else f"Keywords: {topics_str}")

    except Exception as e:
        logger.exception(f"Ошибка при получении описания тем для user_id {user_id}: {e}", extra={'user_id': str(user_id)})
        return "Не удалось определить темы (ошибка)." if lang_code == 'ru' else "Could not determine topics (error)."

async def get_personal_account_info(user_id: int) -> str:
    """Собирает и форматирует информацию для личного кабинета пользователя в структурированном HTML."""
    user_lang = await db_manager.get_user_language(user_id) or 'ru'
    user_api_key = await db_manager.get_user_api_key(user_id)
    persona_id = await db_manager.get_user_persona(user_id)
    first_interaction_date_str = await db_manager.get_first_interaction_date(user_id)

    active_dialog_id = await db_manager.get_active_dialog_id(user_id)
    conversation_count = await db_manager.get_total_user_message_count(user_id)

    title: str = _get_user_title(conversation_count, user_lang)
    days_active: str = _get_days_since_start(first_interaction_date_str, user_lang)

    persona_info = BOT_PERSONAS.get(persona_id, BOT_PERSONAS['default'])
    persona_name = persona_info.get(f"name_{user_lang}", persona_info['name_ru'])

    if user_lang == 'ru':
        api_key_status = "🟢 <b>Подключен</b>" if user_api_key else "🔴 <b>Не установлен</b>"
        lang_name = "Русский"
        topics_description = "Для анализа нужен API-ключ."
        if user_api_key and active_dialog_id:
            topics_description = await _get_topic_description(user_id, user_api_key, active_dialog_id, user_lang)

        days_str = f"{days_active} дн." if days_active.isdigit() else days_active

        info_text = f"""👤 <b>Личный кабинет</b>

🏆 <b>Звание:</b> {title}
💬 <b>Всего сообщений:</b> {conversation_count}
🗓️ <b>Вы с нами:</b> {days_str}

<blockquote>⚙️ <b>Параметры профиля</b>
🎭 Персона: <b>{persona_name}</b>
🌐 Язык: <b>{lang_name}</b>
🔑 API-ключ: {api_key_status}</blockquote>

<blockquote>💡 <b>Темы текущего диалога</b>
🗣️ {html.escape(topics_description)}</blockquote>"""
    else:
        api_key_status = "🟢 <b>Connected</b>" if user_api_key else "🔴 <b>Not set</b>"
        lang_name = "English"
        topics_description = "API key required for topic analysis."
        if user_api_key and active_dialog_id:
            topics_description = await _get_topic_description(user_id, user_api_key, active_dialog_id, user_lang)

        days_str = f"{days_active} days" if days_active.isdigit() else days_active

        info_text = f"""👤 <b>My Account</b>

🏆 <b>Title:</b> {title}
💬 <b>Total messages:</b> {conversation_count}
🗓️ <b>Member for:</b> {days_str}

<blockquote>⚙️ <b>Profile Settings</b>
🎭 Persona: <b>{persona_name}</b>
🌐 Language: <b>{lang_name}</b>
🔑 API Key: {api_key_status}</blockquote>

<blockquote>💡 <b>Current Dialog Topics</b>
🗣️ {html.escape(topics_description)}</blockquote>"""

    return info_text