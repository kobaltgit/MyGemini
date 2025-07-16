# --- START OF FILE handlers/command_handlers.py ---
import datetime
import asyncio
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from telebot import apihelper
# from utils.text_helpers import escape_markdown_v2, sanitize_text_for_telegram
from utils import text_helpers
from utils import markup_helpers as mk

# Импорты из проекта
from config.settings import (
    ADMIN_USER_ID, LANGUAGE_FLAGS, CALLBACK_LANG_PREFIX,
    STATE_WAITING_FOR_TRANSLATE_TEXT, STATE_WAITING_FOR_SUMMARIZE_INPUT,
    STATE_WAITING_FOR_INCOME_SKILLS, STATE_WAITING_FOR_HISTORY_DATE,
    MAX_SUMMARIZE_CHARS
)
from database import db_manager
from services import gemini_service
from features import personal_account, reminders
from logger_config import get_logger

# Словарь для хранения состояний пользователей
user_states = {}

logger = get_logger(__name__)

# --- Вспомогательные функции для отправки сообщений ---

# Эти функции остаются для использования там, где НУЖНА обработка ошибок Markdown

async def send_message(bot: AsyncTeleBot, chat_id: int, text: str, reply_markup=None, parse_mode='None'): # Установили parse_mode='None' по умолчанию и убрали force_plain_text
    """
    Отправляет сообщение пользователю как plain text (без форматирования Markdown).
    Параметр parse_mode принудительно установлен в 'None'.
    """
    # Принудительная отправка как plain text (без разметки)
    try:
        logger.debug(f"[Plain Text Only] Попытка отправки сообщения user_id {chat_id} как plain text.", extra={'user_id': str(chat_id)})
        await bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode='None') # parse_mode='None' (строка)
        logger.debug(f"[Plain Text Only] Сообщение user_id {chat_id} как plain text успешно отправлено.", extra={'user_id': str(chat_id)})
    except Exception as e:
        logger.error(f"[Plain Text Only] Ошибка при отправке сообщения user_id {chat_id} как plain text: {e}", exc_info=True, extra={'user_id': str(chat_id)})


async def reply_to_message(bot: AsyncTeleBot, message: types.Message, text: str, reply_markup=None, parse_mode='None'): # Установили parse_mode='None' по умолчанию
    """
    Отвечает на сообщение пользователя как plain text (без форматирования Markdown).
    Параметр parse_mode принудительно установлен в 'None'.
    """
    chat_id = message.chat.id
    # Отправка как plain text (без разметки)
    try:
        logger.debug(f"[Plain Text Reply] Попытка ответа user_id {chat_id} как plain text.", extra={'user_id': str(chat_id)})
        await bot.reply_to(message, text, reply_markup=reply_markup, parse_mode='None') # parse_mode='None'
        logger.debug(f"[Plain Text Reply] Ответ user_id {chat_id} как plain text успешно отправлен.", extra={'user_id': str(chat_id)})
    except Exception as e:
         logger.error(f"[Plain Text Reply] Ошибка при ответе user_id {chat_id} как plain text: {e}", exc_info=True, extra={'user_id': str(chat_id)})


# --- Обработчики команд ---

async def handle_start(message: types.Message, bot: AsyncTeleBot):
    """Обработчик команды /start."""
    user_id = message.chat.id
    # Получаем "сырые" данные пользователя
    raw_first_name = message.from_user.first_name if message.from_user else None
    raw_username = message.from_user.username if message.from_user else None
    logger.info(f"Команда /start от user_id: {user_id} (@{raw_username}, {raw_first_name})", extra={'user_id': str(user_id)})

    db_manager.add_or_update_user(user_id)
    if user_id in user_states:
        user_states.pop(user_id, None)
        logger.debug(f"Состояние user_id {user_id} сброшено при /start.", extra={'user_id': str(user_id)})
    gemini_service.reset_user_chat(user_id)

    # Определяем имя для приветствия и экранируем его
    greeting_name_to_use = raw_first_name or raw_username or "Незнакомец"
    # escaped_greeting_name = escape_markdown_v2(greeting_name_to_use)

    welcome_message = f"""
👋 Привет, {greeting_name_to_use}! Я твой многофункциональный ассистент на базе Gemini.

Что я умею:

🧠 Отвечать на вопросы и генерировать тексты.
🖼️ Анализировать изображения (просто отправь картинку).
🇷🇺 Переводить текст (кнопка 'Перевести').
📝 Делать краткое изложение текстов, веб-страниц и документов (кнопка 'Изложить').
💰 Создавать план дохода (кнопка 'План дохода').
⏰ Устанавливать напоминания (кнопка 'Напоминания').
📜 Смотреть историю диалога (кнопка 'История').
👤 Просматривать личный кабинет (кнопка 'Личный кабинет').
⚙️ Настраивать стиль моего общения и *часовой пояс* (кнопка 'Настройки').

👇 Используй кнопки ниже или просто напиши свой вопрос!
Для сброса контекста разговора нажми '🔄 Сброс'.
Для помощи нажми '❓ Помощь' или введи /help.
"""

    # # Уведомление админу (parse_mode='None')
    # if ADMIN_USER_ID and ADMIN_USER_ID != user_id:
    #     try:
    #         admin_notify_text = f"Пользователь запустил бота!\nID: {user_id}"
    #         # Используем sanitize для максимальной очистки
    #         if raw_first_name: admin_notify_text += f"\nИмя: {sanitize_text_for_telegram(raw_first_name)}"
    #         if raw_username: admin_notify_text += f"\nUsername: {sanitize_text_for_telegram(raw_username)}" # @ будет заменен
    #         # --- ИЗМЕНЕНИЕ: Прямой вызов bot.send_message ---
    #         logger.debug(f"Попытка прямого вызова bot.send_message для ADMIN_USER_ID {ADMIN_USER_ID} с parse_mode='None'", extra={'user_id': str(user_id)})
    #         await bot.send_message(ADMIN_USER_ID, admin_notify_text, parse_mode='None')
    #         logger.info(f"Уведомление администратору {ADMIN_USER_ID} о запуске от {user_id} отправлено.", extra={'user_id': str(user_id)})
    #     except Exception as admin_err:
    #          # Ловим и логируем ошибку прямого вызова
    #          logger.error(f"Ошибка при прямой отправке уведомления админу {ADMIN_USER_ID}: {admin_err}", exc_info=True, extra={'user_id': str(user_id)})

    # Уведомление админу (parse_mode='None' — как строка, чтобы Telegram НЕ парсил Markdown/HTML)
    if ADMIN_USER_ID and ADMIN_USER_ID != user_id:
        try:
            admin_notify_text = f"🔔 Пользователь запустил бота!\nID: {user_id}"
            if raw_first_name:
                admin_notify_text += f"\nИмя: {raw_first_name}"
            if raw_username:
                admin_notify_text += f"\nUsername: @{raw_username}"

            logger.debug(
                f"Попытка прямого вызова bot.send_message для ADMIN_USER_ID {ADMIN_USER_ID} с parse_mode='None'",
                extra={'user_id': str(user_id)}
            )

            await bot.send_message(
                ADMIN_USER_ID,
                admin_notify_text,
                parse_mode='None'  # передаём строкой, чтобы отключить разметку
            )

            logger.info(
                f"Уведомление администратору {ADMIN_USER_ID} о запуске от {user_id} отправлено.",
                extra={'user_id': str(user_id)}
            )

        except Exception as admin_err:
            logger.error(
                f"Ошибка при прямой отправке уведомления админу {ADMIN_USER_ID}: {admin_err}",
                exc_info=True,
                extra={'user_id': str(user_id)}
            )


    # Отправляем приветственное сообщение пользователю без Markdown
    await reply_to_message(bot, message, welcome_message, reply_markup=mk.create_main_keyboard(), parse_mode='None')

# ... (остальной код без изменений) ...
async def handle_help(message: types.Message, bot: AsyncTeleBot):
    user_id = message.chat.id
    logger.info(f"Команда /help от user_id: {user_id}", extra={'user_id': str(user_id)})
    help_message = """
🆘 *Справка по боту* 🆘

Я - чат-бот на базе Google Gemini. Вот список доступных команд и функций:

*Основные команды:*
/start - Начало работы, приветствие.
/help - Эта справка.
/reset - **Полный сброс** контекста разговора (начинаем с чистого листа).
/myid - Показать ваш Telegram User ID.

*Функции через кнопки:*
🇷🇺 *Перевести:* Запускает пошаговый перевод текста на выбранный язык.
📝 *Изложить:* Позволяет получить краткое содержание текста, веб-страницы (отправьте URL) или документа (DOCX, PDF, TXT).
💰 *План дохода:* Помогает составить пошаговый план для достижения финансовой цели, основываясь на ваших данных.
⏰ *Напоминания:* Управление вашими личными напоминаниями (установка, просмотр, удаление).
📜 *История:* Просмотр истории ваших диалогов с ботом за выбранную дату (используйте календарь).
👤 *Личный кабинет:* Статистика вашего общения с ботом, ваше звание и текущие настройки.
⚙️ *Настройки:* Изменение стиля общения бота и установка вашего *часового пояса*.
❓ *Помощь:* Показать эту справку.
🔄 *Сброс:* Аналог команды /reset.

*Другие возможности:*
🖼️ *Анализ изображений:* Просто отправьте изображение в чат, и я опишу его или отвечу на вопросы по нему.
🗣️ *Свободное общение:* Задавайте любые вопросы текстом.

*Советы:*
- Задавайте чёткие вопросы для лучших ответов.
- Если ответ не устроил, попробуйте переформулировать.
- Используйте /reset, если разговор зашёл в тупик.
- Установите свой часовой пояс в /settings для корректной работы напоминаний.
"""
    await reply_to_message(bot, message, help_message, reply_markup=mk.create_main_keyboard())

async def handle_reset(message: types.Message, bot: AsyncTeleBot):
    user_id = message.chat.id
    logger.info(f"Команда /reset (или кнопка) от user_id: {user_id}", extra={'user_id': str(user_id)})
    if user_id in user_states:
        user_states.pop(user_id, None)
        keys_to_remove = [key for key in list(user_states.keys()) if key.startswith(f"{user_id}_")]
        for key in keys_to_remove:
            user_states.pop(key, None)
        logger.info(f"Состояние и временные данные user_id {user_id} сброшены.", extra={'user_id': str(user_id)})
    gemini_service.reset_user_chat(user_id)
    await reply_to_message(bot, message, "✅ Контекст разговора и ваше текущее состояние сброшены. Начинаем с чистого листа!", reply_markup=mk.create_main_keyboard())

async def handle_myid(message: types.Message, bot: AsyncTeleBot):
    user_id = message.chat.id
    logger.info(f"Команда /myid от user_id: {user_id}", extra={'user_id': str(user_id)})
    await reply_to_message(bot, message, f"Ваш Telegram User ID: `{user_id}`", reply_markup=mk.create_main_keyboard())

async def handle_history(message: types.Message, bot: AsyncTeleBot):
    user_id = message.chat.id
    logger.info(f"Команда /history (или кнопка) от user_id: {user_id}", extra={'user_id': str(user_id)})
    db_manager.add_or_update_user(user_id)
    calendar_markup = mk.create_calendar_keyboard(disable_past=False)
    await send_message(bot, user_id, "🗓️ Выберите дату для просмотра истории:", reply_markup=calendar_markup)
    user_states[user_id] = STATE_WAITING_FOR_HISTORY_DATE
    logger.debug(f"Установлено состояние {STATE_WAITING_FOR_HISTORY_DATE} для user_id {user_id}", extra={'user_id': str(user_id)})

async def handle_settings(message: types.Message, bot: AsyncTeleBot):
    user_id = message.chat.id
    logger.info(f"Запрос настроек от user_id: {user_id}", extra={'user_id': str(user_id)})
    db_manager.add_or_update_user(user_id)
    settings_markup = mk.create_settings_keyboard(user_id)
    await send_message(bot, user_id, "⚙️ **Настройки бота**\nВыберите параметр для изменения:", reply_markup=settings_markup, parse_mode='None') # Изменено на parse_mode='None'

async def handle_translate(message: types.Message, bot: AsyncTeleBot):
    user_id = message.chat.id
    logger.info(f"Запрос на перевод от user_id: {user_id}", extra={'user_id': str(user_id)})
    db_manager.add_or_update_user(user_id)
    if user_id in user_states: user_states.pop(user_id, None)
    lang_markup = mk.create_language_selection_keyboard()
    await send_message(bot, user_id, "🇷🇺 Выберите язык, на который нужно перевести текст:", reply_markup=lang_markup, parse_mode='None') # Изменено на parse_mode='None'

async def handle_summarize(message: types.Message, bot: AsyncTeleBot):
    user_id = message.chat.id
    logger.info(f"Запрос на изложение от user_id: {user_id}", extra={'user_id': str(user_id)})
    db_manager.add_or_update_user(user_id)
    if user_id in user_states: user_states.pop(user_id, None)
    user_states.pop(f"{user_id}_summarize_parts", None)
    await reply_to_message(bot, message,
        f"📝 Отправьте текст, ссылку на веб-страницу или документ (DOCX, PDF, TXT) для краткого изложения.\n\n"
        f"Максимальный объем обрабатываемого текста: ~{MAX_SUMMARIZE_CHARS // 1000} тыс. символов.",
        reply_markup=mk.create_main_keyboard(), parse_mode='None' # Изменено на parse_mode='None'
    )
    user_states[user_id] = STATE_WAITING_FOR_SUMMARIZE_INPUT
    logger.debug(f"Установлено состояние {STATE_WAITING_FOR_SUMMARIZE_INPUT} для user_id {user_id}", extra={'user_id': str(user_id)})

async def handle_income_plan(message: types.Message, bot: AsyncTeleBot):
    user_id = message.chat.id
    logger.info(f"Запрос плана дохода от user_id: {user_id}", extra={'user_id': str(user_id)})
    db_manager.add_or_update_user(user_id)
    if user_id in user_states: user_states.pop(user_id, None)
    for key_suffix in ['skills', 'term', 'resources', 'interests']:
        user_states.pop(f"{user_id}_income_{key_suffix}", None)
    await reply_to_message(bot, message,
        "💰 Давайте составим план дохода! Чтобы начать, опишите, пожалуйста, ваши *основные навыки и компетенции*:",
        reply_markup=mk.create_main_keyboard(), parse_mode='None' # Изменено на parse_mode='None'
    )
    user_states[user_id] = STATE_WAITING_FOR_INCOME_SKILLS
    logger.debug(f"Установлено состояние {STATE_WAITING_FOR_INCOME_SKILLS} для user_id {user_id}", extra={'user_id': str(user_id)})

async def handle_broadcast(message: types.Message, bot: AsyncTeleBot):
    user_id = message.chat.id
    logger.info(f"Попытка вызова /broadcast от user_id: {user_id}", extra={'user_id': str(user_id)})
    if user_id != ADMIN_USER_ID:
        logger.warning(f"Несанкционированный доступ к /broadcast от user_id: {user_id}", extra={'user_id': str(user_id)})
        await reply_to_message(bot, message, "⛔ У вас нет прав на выполнение этой команды.", reply_markup=mk.create_main_keyboard(), parse_mode='None') # Изменено на parse_mode='None'
        return

    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2 or not command_parts[1].strip():
        await reply_to_message(bot, message, "⚠️ Использование: `/broadcast <текст сообщения>`", reply_markup=mk.create_main_keyboard(), parse_mode='None') # Изменено на parse_mode='None'
        return

    broadcast_text = command_parts[1].strip()
    from config.settings import CALLBACK_CONFIRM_BROADCAST, CALLBACK_CANCEL_BROADCAST
    confirm_markup = types.InlineKeyboardMarkup(row_width=1)
    confirm_markup.add(types.InlineKeyboardButton("✅ Да, отправить", callback_data=CALLBACK_CONFIRM_BROADCAST))
    confirm_markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data=CALLBACK_CANCEL_BROADCAST))
    user_states[f"{ADMIN_USER_ID}_broadcast_text"] = broadcast_text
    active_user_count = len(db_manager.get_active_users())
    await reply_to_message(bot, message,
                           f"Вы уверены, что хотите отправить следующее сообщение {active_user_count} пользователям?\n\n---\n{broadcast_text}\n---",
                           reply_markup=confirm_markup, parse_mode='None')

def register_command_handlers(bot: AsyncTeleBot):
    """Регистрирует все обработчики команд и кнопок-синонимов."""
    bot.register_message_handler(handle_start, commands=['start'], pass_bot=True)
    bot.register_message_handler(handle_help, commands=['help'], pass_bot=True)
    bot.register_message_handler(handle_reset, commands=['reset'], pass_bot=True)
    bot.register_message_handler(handle_myid, commands=['myid'], pass_bot=True)
    bot.register_message_handler(handle_settings, commands=['settings'], pass_bot=True)
    bot.register_message_handler(handle_history, commands=['history'], pass_bot=True)
    bot.register_message_handler(handle_translate, commands=['translate'], pass_bot=True)
    bot.register_message_handler(handle_summarize, commands=['summarize'], pass_bot=True)
    bot.register_message_handler(handle_income_plan, commands=['incomeplan'], pass_bot=True)
    bot.register_message_handler(handle_broadcast, commands=['broadcast'], pass_bot=True)
    bot.register_message_handler(handle_reset, regexp=r'^🔄 Сброс$', pass_bot=True)
    bot.register_message_handler(handle_help, regexp=r'^❓ Помощь$', pass_bot=True)
    bot.register_message_handler(handle_translate, regexp=r'^🇷🇺 Перевести$', pass_bot=True)
    bot.register_message_handler(handle_summarize, regexp=r'^📝 Изложить$', pass_bot=True)
    bot.register_message_handler(handle_income_plan, regexp=r'^💰 План дохода$', pass_bot=True)
    bot.register_message_handler(handle_history, regexp=r'^📜 История$', pass_bot=True)
    bot.register_message_handler(handle_settings, regexp=r'^⚙️ Настройки$', pass_bot=True)
    logger.info("Обработчики команд и кнопок-синонимов зарегистрированы.")
# --- END OF FILE handlers/command_handlers.py ---