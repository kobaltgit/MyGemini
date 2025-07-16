# --- START OF FILE features/personal_account.py ---
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any


# Импортируем функции базы данных НАПРЯМУЮ
from database.db_manager import (
    get_user_bot_style,
    get_conversation_count,
    get_first_interaction_date,
    get_conversation_history,
    get_user_reminders
)
# Импортируем настройки
from config.settings import BOT_STYLES
# Импортируем хелперы
from utils.analysis_helpers import extract_frequent_topics
# Импортируем сервис Gemini
from services.gemini_service import generate_content_simple
# Импортируем логгер
from logger_config import get_logger

from database import db_manager

from features.reminders import format_reminders_list

logger = get_logger(__name__, user_id='System')

USER_TITLES: Dict[int, str] = {
    0: "Новичок", 100: "Активный пользователь", 500: "Ветеран чата",
    1000: "Мастер общения", 5000: "Легенда Беседы",
}

def _get_user_title(message_count: int) -> str:
    """Определяет звание пользователя на основе количества сообщений."""
    title: str = USER_TITLES[0]
    for messages, current_title in sorted(USER_TITLES.items(), reverse=True):
        if message_count >= messages:
            title = current_title
            break
    return title

def _get_days_since_start(first_interaction_date_str: Optional[str]) -> str:
    """Рассчитывает количество дней с начала общения."""
    if not first_interaction_date_str or not first_interaction_date_str.strip():
        return "Неизвестно"
    try:
        first_interaction_date = datetime.strptime(first_interaction_date_str, '%Y-%m-%d').date()
        days: int = (datetime.now().date() - first_interaction_date).days
        days = max(0, days)

        if 11 <= days % 100 <= 19: days_str = "дней"
        elif days % 10 == 1: days_str = "день"
        elif 2 <= days % 10 <= 4: days_str = "дня"
        else: days_str = "дней"
        return f"{days} {days_str}"
    except ValueError:
        logger.error(f"Ошибка парсинга даты первого взаимодействия: {first_interaction_date_str}")
        return "Ошибка даты"

def _get_topic_description(user_id: int) -> str:
    """Получает описание тем разговоров от Gemini."""
    user_id_str = str(user_id)
    print(f"DEBUG: -> Вызвана функция _get_topic_description для user_id: {user_id}") # Замените logger.debug на print
    # logger.debug(f"-> Вызвана функция _get_topic_description для user_id: {user_id}", extra={'user_id': user_id_str}) # Закомментируйте logger.debug
    try:
        # Получаем историю как список словарей
        conversation_history_raw: List[Dict[str, Any]] = get_conversation_history(user_id, limit=50)
        print(f"DEBUG: История разговоров, полученная из БД для user_id {user_id}: {conversation_history_raw}") # Замените logger.debug на print
        # logger.debug(f"История разговоров, полученная из БД для user_id {user_id}: {conversation_history_raw}", extra={'user_id': user_id_str}) # Закомментируйте logger.debug

        if not conversation_history_raw:
             print(f"DEBUG: История для анализа тем пользователя {user_id} пуста.") # Замените logger.debug на print
             # logger.debug(f"История для анализа тем пользователя {user_id} пуста.", extra={'user_id': user_id_str}) # Закомментируйте logger.debug
             return "Пока недостаточно данных для анализа тем."

        # Передаем список словарей напрямую
        frequent_topics: List[str] = extract_frequent_topics(conversation_history_raw, top_n=7)
        print(f"DEBUG: Извлеченные темы для user_id {user_id}: {frequent_topics}") # Замените logger.debug на print
        # logger.debug(f"Извлеченные темы для user_id {user_id}: {frequent_topics}", extra={'user_id': user_id_str}) # Закомментируйте logger.debug

        if not frequent_topics:
            return "Пока недостаточно данных для анализа тем."

        topics_str = ', '.join(frequent_topics)
        prompt = f"""Проанализируй следующие ключевые слова из разговора пользователя с чат-ботом: {topics_str}.
Кратко (в 1-2 предложениях) опиши на русском языке основные темы, которые пользователь обсуждает с ботом.
Сделай описание обобщенным и позитивным. Начни ответ со слов 'Чаще всего вы обсуждаете со мной' или 'Основные темы ваших разговоров со мной касаются'."""
        print(f"DEBUG: Промпт для Gemini для user_id {user_id}: {prompt}") # Замените logger.debug на print
        # logger.debug(f"Промпт для Gemini для user_id {user_id}: {prompt}", extra={'user_id': user_id_str}) # Закомментируйте logger.debug

        ai_description: Optional[str] = generate_content_simple(prompt)

        if ai_description:
            return ai_description.strip()
        else:
            logger.warning(f"Не удалось сгенерировать описание тем для {user_id} (Gemini вернул пустой ответ).", extra={'user_id': user_id_str})
            return f"Ключевые слова в ваших запросах: {topics_str}"

    except Exception as e:
        logger.exception(f"Ошибка при получении описания тем для user_id {user_id}: {e}", extra={'user_id': user_id_str})
        return "Не удалось определить темы (ошибка анализа)."

def get_personal_account_info(user_id: int) -> str:
    """
    Собирает и форматирует информацию для личного кабинета пользователя.
    """
    user_id_str = str(user_id)
    print(f"DEBUG: Собираемся вызвать _get_topic_description для user_id: {user_id}")

    try:
        # --- Получаем данные из БД ---
        bot_style_code = 'default'
        try:
            # --- ИЗМЕНЕНИЕ: Убираем префикс db_manager. ---
            bot_style_code = get_user_bot_style(user_id)
        except Exception as db_err:
            logger.error(f"Ошибка получения bot_style для {user_id}: {db_err}", extra={'user_id': user_id_str})

        conversation_count = 0
        try:
            # --- ИЗМЕНЕНИЕ: Убираем префикс db_manager. ---
            conversation_count = get_conversation_count(user_id)
        except Exception as db_err:
            logger.error(f"Ошибка получения conversation_count для {user_id}: {db_err}", extra={'user_id': user_id_str})

        first_interaction_date_str: Optional[str] = None
        try:
            # --- ИЗМЕНЕНИЕ: Убираем префикс db_manager. ---
            first_interaction_date_str = get_first_interaction_date(user_id)
        except Exception as db_err:
             logger.error(f"Ошибка получения first_interaction_date для {user_id}: {db_err}", extra={'user_id': user_id_str})

        # --- Рассчитываем производные данные ---
        title: str = _get_user_title(conversation_count)
        days_active: str = _get_days_since_start(first_interaction_date_str)
        style_name: str = BOT_STYLES.get(bot_style_code, BOT_STYLES['default'])

        # --- Получаем описание тем от ИИ ---
        print(f"DEBUG: Собираемся вызвать _get_topic_description для user_id: {user_id}")
        topics_description: str = _get_topic_description(user_id)

        # --- Получаем часовой пояс пользователя ---
        current_timezone = db_manager.get_user_timezone(user_id)

         # --- Получаем напоминания пользователя --- <--- Добавляем получение напоминаний
        user_reminders: List[Dict[str, Any]] = []
        try:
            user_reminders = get_user_reminders(user_id) # Предполагаем, что функция называется так
        except Exception as db_err:
            logger.error(f"Ошибка получения напоминаний для {user_id}: {db_err}", extra={'user_id': user_id_str})

        # --- Форматируем напоминания в текст --- <--- Форматируем напоминания
        reminders_text: str = format_reminders_list(user_reminders)

        # --- Формируем текст ответа ---
        info_text: str = f"""
👤 Личный кабинет 👤

🏆 Звание: {title}
💬 Всего сообщений: {conversation_count}
🗓️ Вы с нами: {days_active}

--- Настройки ---
🎨 Стиль общения бота: {style_name}
⏰ Напоминания:
{reminders_text} 
---
🔧 Управлять напоминаниями вы можете в разделе 'Напоминания'
---
🕓 Часовой пояс: {current_timezone} (Устанавливается в разделе 'Настройки')

--- Анализ разговоров ---
🗣️ {topics_description}

--- Примечание ---
ℹ️ Данные могут обновляться с небольшой задержкой.*
        """

        logger.info(f"Информация для личного кабинета user_id: {user_id} успешно сформирована.", extra={'user_id': user_id_str})
        return "\n".join(line.strip() for line in info_text.strip().splitlines())

    except Exception as e:
        logger.exception(f"Неожиданная ошибка при формировании личного кабинета для user_id: {user_id}: {e}", extra={'user_id': user_id_str})
        return "Произошла ошибка при загрузке данных вашего личного кабинета. Попробуйте позже."

# --- END OF FILE features/personal_account.py ---