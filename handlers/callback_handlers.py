# --- START OF FILE handlers/callback_handlers.py ---
import datetime
import pytz
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from typing import Optional, Dict, Any, List # <-- Добавил List

# Импорты из проекта
from config.settings import (
    ADMIN_USER_ID, BOT_STYLES, LANGUAGE_FLAGS,
    CALLBACK_LANG_PREFIX, STATE_WAITING_FOR_TRANSLATE_TEXT,
    CALLBACK_CALENDAR_DATE_PREFIX, CALLBACK_CALENDAR_MONTH_PREFIX, STATE_WAITING_FOR_HISTORY_DATE,
    CALLBACK_SETTINGS_STYLE_PREFIX,
    CALLBACK_SET_REMINDER_PREFIX, STATE_WAITING_FOR_REMINDER_TEXT,
    STATE_WAITING_FOR_REMINDER_DATE, STATE_WAITING_FOR_REMINDER_TIME,
    CALLBACK_DELETE_REMINDER_PREFIX,
    CALLBACK_REPORT_ERROR, CALLBACK_IGNORE,
    # --- Префиксы и состояние для таймзоны ---
    CALLBACK_SETTINGS_SET_TIMEZONE_PREFIX,
    CALLBACK_SETTINGS_DETECT_TIMEZONE,
    STATE_WAITING_FOR_TIMEZONE,
    # --- Callbacks для подтверждения рассылки ---
    CALLBACK_CONFIRM_BROADCAST,
    CALLBACK_CANCEL_BROADCAST
)
from database import db_manager
from services import gemini_service
from features import reminders
from utils import markup_helpers as mk
from utils import text_helpers
from logger_config import get_logger
# Импортируем все необходимое из command_handlers (включая user_states)
from .command_handlers import user_states, send_message, reply_to_message

logger = get_logger(__name__)

# --- Вспомогательные функции ---
async def answer_callback_query(bot: AsyncTeleBot, call: types.CallbackQuery, text: Optional[str] = None, show_alert: bool = False, cache_time: int = 0):
    """Отвечает на callback query."""
    try:
        await bot.answer_callback_query(call.id, text=text, show_alert=show_alert, cache_time=cache_time)
    except Exception as e:
        logger.debug(f"Ошибка при ответе на callback query {call.id}: {e}", extra={'user_id': call.from_user.id})

async def edit_message_text(bot: AsyncTeleBot, chat_id: int, message_id: int, text: str, reply_markup=None, parse_mode='Markdown'):
    """Редактирует текст сообщения."""
    try:
        await bot.edit_message_text(text, chat_id, message_id, reply_markup=reply_markup, parse_mode=parse_mode)
        logger.debug(f"Сообщение {message_id} в чате {chat_id} отредактировано.", extra={'user_id': chat_id})
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            logger.error(f"Ошибка редактирования сообщения {message_id} в чате {chat_id}: {e}", extra={'user_id': chat_id})
        else:
            logger.debug(f"Сообщение {message_id} в чате {chat_id} не изменено.", extra={'user_id': chat_id})

async def edit_message_reply_markup(bot: AsyncTeleBot, chat_id: int, message_id: int, reply_markup=None):
    """Редактирует только клавиатуру сообщения."""
    logger.debug(f"Попытка редактирования клавиатуры сообщения {message_id} в чате {chat_id}")
    try:
        await bot.edit_message_reply_markup(chat_id, message_id, reply_markup=reply_markup)
        logger.debug(f"Клавиатура сообщения {message_id} в чате {chat_id} отредактирована.", extra={'user_id': chat_id})
    except Exception as e:
         if "message is not modified" not in str(e).lower():
            logger.error(f"Ошибка редактирования клавиатуры сообщения {message_id} в чате {chat_id}: {e}", extra={'user_id': chat_id})
         else:
            logger.debug(f"Клавиатура сообщения {message_id} в чате {chat_id} не изменена.", extra={'user_id': chat_id})


# --- Основной обработчик Callback Query ---
async def handle_callback_query(call: types.CallbackQuery, bot: AsyncTeleBot):
    """Обрабатывает все callback запросы."""
    user_id = call.from_user.id
    data = call.data
    message = call.message

    if not message:
        logger.warning(f"Получен callback query без объекта message от user_id: {user_id}. Data: '{data}'", extra={'user_id': str(user_id)})
        await answer_callback_query(bot, call)
        return

    logger.debug(f"Получен callback query от user_id: {user_id}. Data: '{data}'. Message ID: {message.message_id}", extra={'user_id': str(user_id)})
    db_manager.add_or_update_user(user_id)

    try:
        # --- Базовые Callbacks ---
        if data == CALLBACK_IGNORE:
            await answer_callback_query(bot, call)

        elif data == CALLBACK_REPORT_ERROR:
            await handle_error_report(bot, call)

        # --- Выбор языка ---
        elif data.startswith(CALLBACK_LANG_PREFIX):
            await handle_language_selection(bot, call)

        # --- Настройки: Стиль ---
        elif data.startswith(CALLBACK_SETTINGS_STYLE_PREFIX):
            await handle_style_setting(bot, call)

        # --- Настройки: Установка/Изменение Таймзоны (кнопка) ---
        elif data == CALLBACK_SETTINGS_SET_TIMEZONE_PREFIX:
             await handle_settings_set_timezone(bot, call)

        # --- Настройки: Определение Таймзоны по геолокации (кнопка) ---
        elif data == CALLBACK_SETTINGS_DETECT_TIMEZONE:
             await handle_settings_detect_timezone(bot, call)

        # --- Календарь: Выбор даты ---
        elif data.startswith(CALLBACK_CALENDAR_DATE_PREFIX):
            await handle_calendar_date_selection(bot, call)

        # --- Календарь: Навигация ---
        elif data.startswith(CALLBACK_CALENDAR_MONTH_PREFIX):
            await handle_calendar_month_navigation(bot, call)

        # --- Напоминания: Добавить ---
        elif data.startswith(CALLBACK_SET_REMINDER_PREFIX):
             logger.info(f"Пользователь {user_id} нажал 'Добавить напоминание'", extra={'user_id': str(user_id)})
             # Сбрасываем другие состояния, если были
             if user_id in user_states: user_states.pop(user_id, None)
             user_states[user_id] = STATE_WAITING_FOR_REMINDER_TEXT
             logger.debug(f"Установлено состояние {STATE_WAITING_FOR_REMINDER_TEXT} для user_id {user_id}", extra={'user_id': str(user_id)})
             await edit_message_text(bot, message.chat.id, message.message_id, "✍️ Введите текст для вашего напоминания:", reply_markup=None, parse_mode='None')
             await answer_callback_query(bot, call, text="Введите текст напоминания")

        # --- Напоминания: Удалить ---
        elif data.startswith(CALLBACK_DELETE_REMINDER_PREFIX):
             await handle_delete_reminder(bot, call)

        # --- Админ: Подтверждение рассылки ---
        elif data == CALLBACK_CONFIRM_BROADCAST:
             await handle_confirm_broadcast(bot, call)

        # --- Админ: Отмена рассылки ---
        elif data == CALLBACK_CANCEL_BROADCAST:
             await handle_cancel_broadcast(bot, call)

        else:
            logger.warning(f"Неизвестный callback data от user_id {user_id}: {data}", extra={'user_id': str(user_id)})
            await answer_callback_query(bot, call, text="Неизвестное действие", show_alert=True)

    except Exception as e:
        logger.exception(f"Критическая ошибка обработки callback query от user_id {user_id} (data: {data}): {e}", extra={'user_id': str(user_id)})
        try:
            await answer_callback_query(bot, call, text="Произошла внутренняя ошибка.", show_alert=True)
            if message:
                await edit_message_reply_markup(bot, message.chat.id, message.message_id, reply_markup=None)
        except Exception as inner_e:
            logger.error(f"Дополнительная ошибка при обработке исключения в callback_handler для user_id {user_id}: {inner_e}", extra={'user_id': str(user_id)})


# --- Обработчики конкретных Callback ---

async def handle_language_selection(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает выбор языка для перевода."""
    user_id = call.from_user.id
    data = call.data
    message = call.message
    lang_code = data[len(CALLBACK_LANG_PREFIX):]
    lang_name = LANGUAGE_FLAGS.get(lang_code, lang_code)

    logger.info(f"Пользователь {user_id} выбрал язык перевода: {lang_code} ({lang_name})", extra={'user_id': str(user_id)})

    # Устанавливаем состояние ожидания текста и сохраняем выбранный язык
    user_states[user_id] = STATE_WAITING_FOR_TRANSLATE_TEXT
    user_states[f"{user_id}_target_lang"] = lang_code
    logger.debug(f"Установлено состояние {STATE_WAITING_FOR_TRANSLATE_TEXT} и язык {lang_code} для user_id {user_id}", extra={'user_id': str(user_id)})


    await answer_callback_query(bot, call, text=f"Выбран язык: {lang_name}")
    await edit_message_text(bot, message.chat.id, message.message_id,
                            f"🇷🇺 Выбран язык: **{lang_name}**.\n\nТеперь отправьте текст, который нужно перевести.",
                            reply_markup=None, parse_mode='Markdown')

async def handle_style_setting(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает выбор стиля общения бота."""
    user_id = call.from_user.id
    data = call.data
    message = call.message
    style_code = data[len(CALLBACK_SETTINGS_STYLE_PREFIX):]

    if style_code in BOT_STYLES:
        style_name = BOT_STYLES[style_code]
        current_style = db_manager.get_user_bot_style(user_id)

        # Обновляем только если стиль изменился
        if style_code != current_style:
            logger.info(f"Пользователь {user_id} изменяет стиль на: {style_code}", extra={'user_id': str(user_id)})
            db_manager.set_user_bot_style(user_id, style_code)
            gemini_service.reset_user_chat(user_id) # Сбрасываем контекст при смене стиля
            await answer_callback_query(bot, call, text=f"Стиль изменен на '{style_name}'")
            # Обновляем клавиатуру настроек, чтобы показать новый выбранный стиль
            new_settings_markup = mk.create_settings_keyboard(user_id)
            await edit_message_reply_markup(bot, message.chat.id, message.message_id, reply_markup=new_settings_markup)
            # Можно добавить текстовое подтверждение в сообщение
            await edit_message_text(bot, message.chat.id, message.message_id,
                                    f"⚙️ **Настройки бота**\n✅ Стиль общения изменен на **'{style_name}'**.\nКонтекст разговора сброшен.",
                                    reply_markup=new_settings_markup, parse_mode='Markdown')

        else:
            logger.debug(f"Пользователь {user_id} кликнул на уже выбранный стиль {style_code}.", extra={'user_id': str(user_id)})
            await answer_callback_query(bot, call, text=f"Стиль '{style_name}' уже установлен.")

    else:
        logger.warning(f"Неверный стиль {style_code} от {user_id}", extra={'user_id': str(user_id)})
        await answer_callback_query(bot, call, text="Ошибка: неверный стиль.", show_alert=True)


async def handle_settings_set_timezone(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает нажатие кнопки 'Установить/Изменить часовой пояс'."""
    user_id = call.from_user.id
    message = call.message

    logger.info(f"Пользователь {user_id} запросил установку/изменение часового пояса.", extra={'user_id': str(user_id)})
    # Устанавливаем состояние ожидания ввода таймзоны
    user_states[user_id] = STATE_WAITING_FOR_TIMEZONE
    logger.debug(f"Установлено состояние {STATE_WAITING_FOR_TIMEZONE} для user_id {user_id}", extra={'user_id': str(user_id)})

    await answer_callback_query(bot, call) # Просто убираем часики
    # Редактируем сообщение с настройками, чтобы запросить ввод
    await edit_message_text(
        bot, message.chat.id, message.message_id,
        "🌍 Введите ваш **часовой пояс** в формате `Регион/Город` (например, `Europe/Moscow`, `Asia/Yekaterinburg`) "
        "или отправьте свою геолокацию 📍 (через меню вложений Telegram).",
        reply_markup=None, # Убираем клавиатуру настроек
        parse_mode='Markdown'
    )


async def handle_settings_detect_timezone(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает нажатие кнопки 'Определить по геолокации'."""
    user_id = call.from_user.id
    message = call.message

    logger.info(f"Пользователь {user_id} запросил определение часового пояса по геолокации.", extra={'user_id': str(user_id)})
    # Устанавливаем состояние ожидания (на случай, если он введет текстом)
    user_states[user_id] = STATE_WAITING_FOR_TIMEZONE
    logger.debug(f"Установлено состояние {STATE_WAITING_FOR_TIMEZONE} для user_id {user_id}", extra={'user_id': str(user_id)})

    await answer_callback_query(bot, call)
    # Редактируем сообщение с настройками, просим отправить геолокацию
    await edit_message_text(
        bot, message.chat.id, message.message_id,
        "📍 Пожалуйста, отправьте вашу **текущую геолокацию**, используя кнопку со скрепкой (📎) в поле ввода сообщения.",
        reply_markup=None, # Убираем клавиатуру настроек
        parse_mode='Markdown'
    )
    # НЕ отправляем ReplyKeyboard здесь, т.к. это может конфликтовать с InlineKeyboard
    # Пользователь должен сам нажать на скрепку и выбрать "Геопозиция"


async def handle_calendar_date_selection(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает выбор даты в календаре (для Истории и Напоминаний)."""
    user_id = call.from_user.id
    data = call.data
    message = call.message
    selected_date_str = data[len(CALLBACK_CALENDAR_DATE_PREFIX):]

    current_state = user_states.get(user_id)
    logger.debug(f"Выбрана дата в календаре: {selected_date_str} от user_id {user_id}. Текущее состояние: {current_state}", extra={'user_id': str(user_id)})

    if current_state not in [STATE_WAITING_FOR_HISTORY_DATE, STATE_WAITING_FOR_REMINDER_DATE]:
        logger.warning(f"Callback даты {selected_date_str} от {user_id} в неожиданном состоянии '{current_state}'. Игнорируем.", extra={'user_id': str(user_id)})
        await answer_callback_query(bot, call)
        try:
            await edit_message_reply_markup(bot, message.chat.id, message.message_id, reply_markup=None)
        except Exception as edit_err:
             logger.debug(f"Не удалось убрать клавиатуру календаря после неожиданного состояния: {edit_err}", extra={'user_id': str(user_id)})
        if user_id in user_states:
             user_states.pop(user_id, None)
        return

    # --- Обработка для ИСТОРИИ ---
    if current_state == STATE_WAITING_FOR_HISTORY_DATE:
        logger.info(f"Обработка выбора даты '{selected_date_str}' для ИСТОРИИ user_id {user_id}", extra={'user_id': str(user_id)})
        try:
            selected_date = datetime.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            logger.debug(f"Дата истории успешно распарсена: {selected_date}", extra={'user_id': str(user_id)})

            await answer_callback_query(bot, call, text=f"Загружаю историю за {selected_date.strftime('%d.%m.%Y')}...")
            await edit_message_reply_markup(bot, message.chat.id, message.message_id, reply_markup=None)
            await edit_message_text(bot, message.chat.id, message.message_id, f"⏳ Загружаю историю за {selected_date.strftime('%d.%m.%Y')}...", reply_markup=None, parse_mode='None')

            conversation_history: List[Dict[str, Any]] = db_manager.get_conversation_history_by_date(user_id, selected_date)
            logger.debug(f"Получено {len(conversation_history)} сообщений из БД для истории user_id {user_id}", extra={'user_id': str(user_id)})

            if conversation_history:
                history_text = f"📜 **История за {selected_date.strftime('%d.%m.%Y')}:**\n{'-'*20}\n\n"
                for item in conversation_history:
                    role = item.get('role', 'unknown')
                    message_text = text_helpers.remove_markdown(item.get('message_text', '')) # Убираем markdown
                    prefix = "👤 **Вы:**" if role == 'user' else "🤖 **Бот:**" if role == 'bot' else f"🔧 **({role}):**"
                    history_text += f"{prefix}\n{message_text}\n\n{'-'*15}\n\n"

                # Используем text_helpers.split_message для простого текста
                parts = text_helpers.split_message(history_text, max_length=4000)
                logger.debug(f"Текст истории разбит на {len(parts)} частей для user_id {user_id}", extra={'user_id': str(user_id)})

                try:
                    await bot.delete_message(message.chat.id, message.message_id)
                    logger.debug(f"Сообщение 'Загрузка...' ({message.message_id}) удалено.", extra={'user_id': str(user_id)})
                except Exception as del_err:
                    logger.warning(f"Не удалось удалить сообщение 'Загрузка...' ({message.message_id}): {del_err}", extra={'user_id': str(user_id)})

                for part in parts:
                    # Отправляем как Markdown, т.к. добавили ** для ролей
                    await send_message(bot, user_id, part, reply_markup=mk.create_main_keyboard(), parse_mode='Markdown')
                    await asyncio.sleep(0.1)
            else:
                logger.debug(f"Сообщений за {selected_date.strftime('%d.%m.%Y')} для user_id {user_id} не найдено.", extra={'user_id': str(user_id)})
                await edit_message_text(bot, message.chat.id, message.message_id,
                                        f"🤷‍♂️ За {selected_date.strftime('%d.%m.%Y')} сообщений не найдено.",
                                        reply_markup=None, parse_mode='None')

            user_states.pop(user_id, None)
            logger.debug(f"Состояние user_id {user_id} сброшено после обработки истории.", extra={'user_id': str(user_id)})

        except ValueError:
            logger.error(f"Неверный формат даты '{selected_date_str}' в callback от user_id {user_id}", extra={'user_id': str(user_id)})
            await answer_callback_query(bot, call, "Ошибка формата даты.", show_alert=True)
            user_states.pop(user_id, None)
        except Exception as e:
             logger.exception(f"Ошибка при получении или отправке истории для user_id {user_id}: {e}", extra={'user_id': str(user_id)})
             await answer_callback_query(bot, call, "Ошибка при получении истории.", show_alert=True)
             try:
                 await edit_message_reply_markup(bot, message.chat.id, message.message_id, reply_markup=None)
             except Exception: pass
             user_states.pop(user_id, None)

    # --- Обработка для НАПОМИНАНИЯ ---
    elif current_state == STATE_WAITING_FOR_REMINDER_DATE:
         logger.info(f"Обработка выбора даты '{selected_date_str}' для НАПОМИНАНИЯ user_id {user_id}", extra={'user_id': str(user_id)})
         try:
             datetime.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
             user_states[f"{user_id}_reminder_date"] = selected_date_str
             user_states[user_id] = STATE_WAITING_FOR_REMINDER_TIME

             await answer_callback_query(bot, call, f"Выбрана дата: {selected_date_str}")
             await edit_message_text(bot, message.chat.id, message.message_id,
                                     f"🗓️ Выбрана дата: **{selected_date_str}**\n\n"
                                     f"🕒 Теперь введите **время** напоминания в формате **ЧЧ:ММ** (например, 09:00 или 21:30):",
                                     reply_markup=None,
                                     parse_mode='Markdown')
             logger.debug(f"Состояние user_id {user_id} изменено на {STATE_WAITING_FOR_REMINDER_TIME}", extra={'user_id': str(user_id)})

         except ValueError:
             logger.error(f"Неверный формат даты '{selected_date_str}' в callback напоминания от user_id {user_id}", extra={'user_id': str(user_id)})
             await answer_callback_query(bot, call, "Ошибка формата даты.", show_alert=True)
         except Exception as e:
             logger.exception(f"Ошибка при обработке выбора даты напоминания для user_id {user_id}: {e}", extra={'user_id': str(user_id)})
             await answer_callback_query(bot, call, "Ошибка обработки даты.", show_alert=True)
             user_states.pop(user_id, None)
             user_states.pop(f"{user_id}_reminder_text", None)
             user_states.pop(f"{user_id}_reminder_date", None)


async def handle_calendar_month_navigation(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает навигацию по месяцам в календаре."""
    user_id = call.from_user.id
    data = call.data
    message = call.message
    year_month_str = data[len(CALLBACK_CALENDAR_MONTH_PREFIX):]

    current_state = user_states.get(user_id)
    # Определяем, нужно ли блокировать прошлые даты
    disable_past = True # По умолчанию для напоминаний
    if current_state == STATE_WAITING_FOR_HISTORY_DATE:
        disable_past = False # Для истории разрешаем прошлое

    if current_state not in [STATE_WAITING_FOR_HISTORY_DATE, STATE_WAITING_FOR_REMINDER_DATE]:
        logger.warning(f"Callback навигации по месяцам от {user_id} в состоянии '{current_state}'. Игнорируем.", extra={'user_id': str(user_id)})
        await answer_callback_query(bot, call)
        return

    try:
        year, month = map(int, year_month_str.split('-'))
        # Передаем disable_past в create_calendar_keyboard
        new_calendar_markup = mk.create_calendar_keyboard(year, month, disable_past=disable_past)
        await edit_message_reply_markup(bot, message.chat.id, message.message_id, reply_markup=new_calendar_markup)
        await answer_callback_query(bot, call)
    except ValueError:
        logger.error(f"Неверный формат года/месяца '{year_month_str}' в callback навигации от {user_id}", extra={'user_id': str(user_id)})
        await answer_callback_query(bot, call, "Ошибка навигации.", show_alert=True)
    except Exception as e:
        logger.exception(f"Ошибка навигации календаря для {user_id}: {e}", extra={'user_id': str(user_id)})
        await answer_callback_query(bot, call, "Ошибка обновления календаря.", show_alert=True)


async def handle_delete_reminder(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает удаление напоминания."""
    user_id = call.from_user.id
    data = call.data
    message = call.message
    try:
        reminder_id_to_delete = int(data[len(CALLBACK_DELETE_REMINDER_PREFIX):])
        logger.info(f"Запрос удаления напоминания ID {reminder_id_to_delete} от user_id {user_id}", extra={'user_id': str(user_id)})

        success = await reminders.remove_scheduled_reminder(reminder_id_to_delete, user_id)

        if success:
            await answer_callback_query(bot, call, text="Напоминание удалено")
            # Обновляем список напоминаний в сообщении
            user_reminders = db_manager.get_user_reminders(user_id)
            new_markup = mk.create_reminders_keyboard(user_reminders)
            await edit_message_text(bot, message.chat.id, message.message_id,
                                    "⏰ **Управление напоминаниями**", # Обновляем заголовок
                                    reply_markup=new_markup, parse_mode='Markdown')
        else:
            await answer_callback_query(bot, call, text="Не удалось удалить.", show_alert=True)
            # Обновляем клавиатуру на случай, если она устарела
            try:
                user_reminders = db_manager.get_user_reminders(user_id)
                new_markup = mk.create_reminders_keyboard(user_reminders)
                await edit_message_reply_markup(bot, message.chat.id, message.message_id, reply_markup=new_markup)
            except Exception as update_err:
                logger.error(f"Ошибка обновления клавиатуры напоминаний после неудачного удаления для user_id {user_id}: {update_err}", extra={'user_id': str(user_id)})

    except (ValueError, IndexError):
        logger.error(f"Неверный ID напоминания в callback '{data}' от user_id {user_id}", extra={'user_id': str(user_id)})
        await answer_callback_query(bot, call, "Ошибка: Неверный ID.", show_alert=True)
    except Exception as e:
        logger.exception(f"Ошибка при обработке удаления напоминания для user_id {user_id}: {e}", extra={'user_id': str(user_id)})
        await answer_callback_query(bot, call, "Ошибка при удалении.", show_alert=True)

async def handle_error_report(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает нажатие кнопки 'Сообщить об ошибке'."""
    user_id = call.from_user.id
    message = call.message
    user_info_str = f"User ID: `{user_id}`"
    if call.from_user:
        if call.from_user.first_name: user_info_str += f", Имя: {text_helpers.remove_markdown(call.from_user.first_name)}"
        if call.from_user.username: user_info_str += f", Username: @{call.from_user.username}"

    logger.info(f"Сообщение об ошибке от {user_info_str}.", extra={'user_id': str(user_id)})

    admin_message = f"🆘 Сообщение об ошибке!\n\n"
    admin_message += f"Пользователь: {user_info_str}\n"
    original_bot_message = text_helpers.remove_markdown(message.text or "[Нет текста сообщения]")
    admin_message += f"\nСообщение бота (ID: {message.message_id}):\n---\n{original_bot_message}\n---"

    try:
        if ADMIN_USER_ID:
            await send_message(bot, ADMIN_USER_ID, admin_message, parse_mode='Markdown')
            await answer_callback_query(bot, call, text="✅ Отчет отправлен администратору.")
            await edit_message_reply_markup(bot, message.chat.id, message.message_id, reply_markup=None)
        else:
            logger.warning("ADMIN_USER_ID не настроен. Отчет об ошибке не отправлен.", extra={'user_id': str(user_id)})
            await answer_callback_query(bot, call, text="Функция отчета не настроена.", show_alert=True)

    except Exception as e:
        logger.exception(f"Ошибка отправки отчета об ошибке от {user_id}: {e}", extra={'user_id': str(user_id)})
        await answer_callback_query(bot, call, text="Не удалось отправить отчет.", show_alert=True)


# --- Обработчики для админской рассылки ---
async def handle_confirm_broadcast(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает подтверждение рассылки администратором."""
    user_id = call.from_user.id
    message = call.message

    if user_id != ADMIN_USER_ID:
        logger.warning(f"Попытка подтвердить рассылку не админом (user_id: {user_id})", extra={'user_id': str(user_id)})
        await answer_callback_query(bot, call, text="У вас нет прав.", show_alert=True)
        return

    broadcast_text = user_states.pop(f"{ADMIN_USER_ID}_broadcast_text", None)
    if not broadcast_text:
        logger.error(f"Текст рассылки не найден в user_states для ADMIN_USER_ID {ADMIN_USER_ID}", extra={'user_id': str(user_id)})
        await answer_callback_query(bot, call, text="Ошибка: Текст рассылки не найден.", show_alert=True)
        await edit_message_text(bot, message.chat.id, message.message_id, "Ошибка: текст рассылки потерян.", reply_markup=None)
        return

    await answer_callback_query(bot, call) # Убираем часики
    await edit_message_text(bot, message.chat.id, message.message_id, "🚀 Начинаю рассылку...", reply_markup=None)

    # Запускаем саму рассылку
    await broadcast_message(bot, broadcast_text)


async def handle_cancel_broadcast(bot: AsyncTeleBot, call: types.CallbackQuery):
    """Обрабатывает отмену рассылки администратором."""
    user_id = call.from_user.id
    message = call.message

    if user_id != ADMIN_USER_ID:
        logger.warning(f"Попытка отменить рассылку не админом (user_id: {user_id})", extra={'user_id': str(user_id)})
        await answer_callback_query(bot, call, text="У вас нет прав.", show_alert=True)
        return

    # Удаляем текст рассылки из временного хранилища
    user_states.pop(f"{ADMIN_USER_ID}_broadcast_text", None)
    logger.info(f"Администратор {user_id} отменил рассылку.", extra={'user_id': str(user_id)})

    await answer_callback_query(bot, call)
    await edit_message_text(bot, message.chat.id, message.message_id, "❌ Рассылка отменена.", reply_markup=None)


async def broadcast_message(bot: AsyncTeleBot, text: str):
    """Выполняет рассылку сообщения всем активным пользователям."""
    admin_id = ADMIN_USER_ID # Для краткости
    logger.info(f"Запуск рассылки сообщения администратором {admin_id}.", extra={'user_id': str(admin_id)})
    active_user_ids = db_manager.get_active_users()
    sent_count = 0
    failed_count = 0
    blocked_count = 0
    total_users = len(active_user_ids)

    start_time = time.time()

    for target_user_id in active_user_ids:
        # Не отправляем самому админу
        if target_user_id == admin_id:
            continue

        try:
            # Отправляем без Markdown по умолчанию, если только админ явно не использовал разметку
            # Лучше всегда отправлять без parse_mode='None' для надежности
            await send_message(bot, target_user_id, text, reply_markup=mk.create_main_keyboard(), parse_mode='None')
            sent_count += 1
            logger.debug(f"Рассылка: Сообщение успешно отправлено user_id {target_user_id}", extra={'user_id': 'AdminBroadcast'})
            # Задержка для избежания лимитов Telegram (20-30 сообщений в минуту)
            await asyncio.sleep(0.1) # 0.1 сек = 600/мин (слишком быстро)
            # Увеличим задержку до 0.5 сек (120/мин) или даже 1 сек (60/мин)
            await asyncio.sleep(0.5)

        except Exception as e:
             error_str = str(e).lower()
             if "forbidden: bot was blocked by the user" in error_str or "user is deactivated" in error_str or "chat not found" in error_str:
                  blocked_count += 1
                  logger.warning(f"Рассылка: Пользователь {target_user_id} заблокировал бота или неактивен.", extra={'user_id': 'AdminBroadcast'})
                  # Опционально: можно деактивировать пользователя в БД
                  # db_manager.deactivate_user(target_user_id)
             else:
                  failed_count += 1
                  logger.error(f"Рассылка: Неизвестная ошибка отправки пользователю {target_user_id}: {e}", extra={'user_id': 'AdminBroadcast'})

        # Периодический отчет админу о прогрессе (например, каждые 50 пользователей)
        if (sent_count + failed_count + blocked_count) % 50 == 0:
            elapsed_time = time.time() - start_time
            progress_msg = (f"⏳ Рассылка: Обработано {sent_count + failed_count + blocked_count}/{total_users} пользователей. "
                            f"Успешно: {sent_count}, Ошибки: {failed_count}, Заблокировано: {blocked_count}. "
                            f"Время: {elapsed_time:.1f} сек.")
            try:
                await send_message(bot, admin_id, progress_msg, parse_mode='None')
            except Exception: pass # Игнорируем ошибки отправки прогресса админу


    end_time = time.time()
    total_time = end_time - start_time
    result_message = (f"✅ Рассылка завершена за {total_time:.1f} сек!\n\n"
                      f"Всего пользователей: {total_users}\n"
                      f"Отправлено успешно: {sent_count}\n"
                      f"Заблокировали бота: {blocked_count}\n"
                      f"Другие ошибки отправки: {failed_count}")
    await send_message(bot, admin_id, result_message, parse_mode='None')


# --- Регистрация обработчиков ---

def register_callback_handlers(bot: AsyncTeleBot):
    """Регистрирует основной обработчик callback запросов."""
    # Регистрируем обработчик для всех callback-запросов
    bot.register_callback_query_handler(handle_callback_query, func=lambda call: True, pass_bot=True)
    logger.info("Обработчик callback query зарегистрирован.")

# Необходим импорт asyncio для пауз и time для рассылки
import asyncio
import time
# --- END OF FILE handlers/callback_handlers.py ---