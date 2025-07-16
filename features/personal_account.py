# File: features/personal_account.py
from datetime import datetime
from typing import Optional, List, Dict, Any

from database.db_manager import (
    get_user_bot_style,
    get_conversation_count,
    get_first_interaction_date,
    get_conversation_history,
    get_user_language,
    get_user_api_key,
    get_user_persona # <-- Импортируем новую функцию
)
from config.settings import BOT_STYLES, BOT_PERSONAS # <-- Импортируем персоны
from utils.analysis_helpers import extract_frequent_topics
from services.gemini_service import generate_content_simple
from logger_config import get_logger

logger = get_logger(__name__, user_id='System')

USER_TITLES: Dict[int, str] = {
    0: "Новичок / Newcomer", 100: "Активный пользователь / Active User", 500: "Ветеран чата / Chat Veteran",
    1000: "Мастер общения / Master of Conversation", 5000: "Легенда / Legend",
}

def _get_user_title(message_count: int) -> str:
    title: str = USER_TITLES[0]
    for messages, current_title in sorted(USER_TITLES.items(), reverse=True):
        if message_count >= messages:
            title = current_title
            break
    return title

def _get_days_since_start(first_interaction_date_str: Optional[str]) -> str:
    if not first_interaction_date_str:
        return "Неизвестно / Unknown"
    try:
        first_interaction_date = datetime.strptime(first_interaction_date_str, '%Y-%m-%d').date()
        days: int = (datetime.now().date() - first_interaction_date).days
        return str(max(0, days))
    except ValueError:
        return "Ошибка / Error"

async def _get_topic_description(user_id: int, api_key: str) -> str:
    try:
        conversation_history_raw = get_conversation_history(user_id, limit=50)
        if not conversation_history_raw:
             return "Пока недостаточно данных для анализа. / Not enough data for analysis yet."
        frequent_topics = extract_frequent_topics(conversation_history_raw, top_n=7)
        if not frequent_topics:
            return "Пока недостаточно данных для анализа. / Not enough data for analysis yet."

        topics_str = ', '.join(frequent_topics)
        prompt = f"""Analyze the following keywords from a user's conversation with a chatbot: {topics_str}.
Briefly (in 1-2 sentences in Russian) describe the main topics the user discusses. Make the description generalized and positive.
Start the response with 'Чаще всего вы обсуждаете' or a similar phrase."""

        ai_description = await generate_content_simple(api_key, prompt)

        if ai_description:
            return ai_description.strip()
        else:
            return f"Ключевые слова в запросах: {topics_str} / Keywords in your queries: {topics_str}"

    except Exception as e:
        logger.exception(f"Ошибка при получении описания тем для user_id {user_id}: {e}", extra={'user_id': str(user_id)})
        return "Не удалось определить темы (ошибка). / Could not determine topics (error)."

async def get_personal_account_info(user_id: int) -> str:
    """Собирает и форматирует информацию для личного кабинета пользователя."""
    # Получаем данные из БД
    bot_style_code = get_user_bot_style(user_id)
    conversation_count = get_conversation_count(user_id)
    first_interaction_date_str = get_first_interaction_date(user_id)
    user_lang = get_user_language(user_id)
    user_api_key = get_user_api_key(user_id)
    persona_id = get_user_persona(user_id) # <-- Получаем ID персоны

    # Рассчитываем производные данные
    title: str = _get_user_title(conversation_count)
    days_active: str = _get_days_since_start(first_interaction_date_str)
    style_name: str = BOT_STYLES.get(bot_style_code, BOT_STYLES['default'])

    # НОВОЕ: Получаем имя персоны на нужном языке
    persona_info = BOT_PERSONAS.get(persona_id, BOT_PERSONAS['default'])
    persona_name = persona_info.get(f"name_{user_lang}", persona_info['name_ru'])

    api_key_status = "✅ Установлен / Set" if user_api_key else "❌ Не установлен / Not Set"

    topics_description = "Для анализа нужен API ключ / API key required for analysis"
    if user_api_key:
        topics_description = await _get_topic_description(user_id, user_api_key)

    # ИЗМЕНЕНО: Формируем текст ответа с учетом персоны
    info_text = f"""
👤 *Личный кабинет / My Account* 👤

🏆 *Звание / Title:* {title}
💬 *Всего сообщений / Total messages:* {conversation_count}
🗓️ *Вы с нами (дней) / You are with us (days):* {days_active}

--- *Настройки / Settings* ---
🎭 *Текущая персона / Persona:* {persona_name}
🎨 *Стиль общения / Bot Style:* {style_name}
🌐 *Язык / Language:* {"Русский" if user_lang == 'ru' else "English"}
🔑 *API Ключ / API Key:* {api_key_status}

--- *Анализ разговоров / Conversation Analysis* ---
🗣️ {topics_description}
"""
    return "\n".join(line.strip() for line in info_text.strip().splitlines())
