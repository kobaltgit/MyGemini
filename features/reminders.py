# --- START OF FILE features/reminders.py ---
import datetime
import pytz
from typing import Optional, List, Dict, Any # Добавлены Dict, Any
# import sqlite3 # <--- УБИРАЕМ ИМПОРТ sqlite3, так как тип Dict[str, Any] используется из db_manager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import JobLookupError
from telebot.async_telebot import AsyncTeleBot
from telebot.util import smart_split # Для возможного разбиения длинных текстов напоминаний

# Импорты из проекта
from database.db_manager import (
    add_reminder,
    get_user_reminders,
    get_active_pending_reminders,
    deactivate_reminder,
    delete_reminder
)
from utils.markup_helpers import create_reminders_keyboard, create_main_keyboard
from logger_config import get_logger

logger = get_logger('reminders')

# --- Инициализация планировщика ---
# Используем UTC как таймзону планировщика для консистентности с БД
scheduler = AsyncIOScheduler(timezone=pytz.utc)

# --- Функции для управления напоминаниями ---

async def schedule_reminder(bot: AsyncTeleBot, user_id: int, reminder_text: str, reminder_dt_utc: datetime.datetime):
    """
    Сохраняет напоминание в БД и добавляет/обновляет задачу в планировщике.
    Время должно быть передано в UTC.
    """
    try:
        # Убедимся, что время точно в UTC
        if reminder_dt_utc.tzinfo is None or reminder_dt_utc.tzinfo.utcoffset(reminder_dt_utc) != datetime.timedelta(0):
            logger.warning(f"Время для schedule_reminder было не в UTC ({reminder_dt_utc.tzinfo}). Конвертируем в UTC.", extra={'user_id': user_id})
            if reminder_dt_utc.tzinfo is None:
                 reminder_dt_utc = pytz.utc.localize(reminder_dt_utc)
            else:
                 reminder_dt_utc = reminder_dt_utc.astimezone(pytz.utc)

        # 1. Сохраняем в БД
        # add_reminder ожидает datetime UTC и сама его форматирует в ISO
        reminder_id = add_reminder(user_id, reminder_text, reminder_dt_utc)

        if reminder_id:
            # 2. Добавляем/обновляем задачу в планировщике
            job_id = f"reminder_{reminder_id}"
            # Передаем время UTC в планировщик
            scheduler.add_job(
                send_reminder_job,
                trigger='date',
                run_date=reminder_dt_utc,
                args=[bot, reminder_id, user_id, reminder_text],
                id=job_id,
                misfire_grace_time=60*15, # 15 минут допустимого опоздания для выполнения
                replace_existing=True # Заменять существующее задание (важно для редактирования)
            )
            logger.info(f"Напоминание ID {reminder_id} для user_id {user_id} запланировано/обновлено на {reminder_dt_utc.strftime('%Y-%m-%d %H:%M:%S %Z')} (job_id: {job_id})", extra={'user_id': user_id})
            return True
        else:
            logger.error(f"Не удалось сохранить напоминание в БД для user_id {user_id}.", extra={'user_id': user_id})
            return False
    except Exception as e:
        logger.exception(f"Ошибка при планировании напоминания для user_id {user_id}: {e}", extra={'user_id': user_id})
        return False

async def send_reminder_job(bot: AsyncTeleBot, reminder_id: int, user_id: int, reminder_text: str):
    """
    Задача, выполняемая планировщиком для отправки напоминания.
    Деактивирует напоминание после попытки отправки (успешной или неуспешной).
    """
    job_id = f"reminder_{reminder_id}"
    logger.info(f"Сработало задание {job_id} для user_id {user_id}.", extra={'user_id': user_id})
    try:
        message_text = f"⏰ **Напоминание!** ⏰\n\n{reminder_text}"
        # Разбиваем на части, если текст слишком длинный
        message_parts = smart_split(message_text, chars_per_string=4000)

        for part in message_parts:
             # Отправляем каждую часть с основной клавиатурой
             await bot.send_message(
                 chat_id=user_id,
                 text=part,
                 parse_mode='Markdown',
                 reply_markup=create_main_keyboard()
             )
             await asyncio.sleep(0.1) # Небольшая пауза

        logger.info(f"Напоминание ID {reminder_id} успешно отправлено user_id {user_id}.", extra={'user_id': user_id})

    except Exception as e:
        # Логируем ошибку отправки (например, бот заблокирован)
        logger.exception(f"Ошибка при отправке напоминания ID {reminder_id} пользователю {user_id}: {e}", extra={'user_id': user_id})
        # Причины могут быть разные: пользователь заблокировал бота, ID невалиден и т.д.

    finally:
        # Деактивируем напоминание в любом случае (после успешной отправки или ошибки)
        logger.debug(f"Деактивация напоминания ID {reminder_id} после попытки отправки.", extra={'user_id': user_id})
        deactivate_reminder(reminder_id)


async def remove_scheduled_reminder(reminder_id: int, user_id: int) -> bool:
    """
    Удаляет напоминание из БД и отменяет запланированную задачу.
    """
    job_id = f"reminder_{reminder_id}"
    scheduler_success = False
    db_success = False

    # 1. Удаляем из планировщика
    try:
        scheduler.remove_job(job_id)
        logger.info(f"Задание {job_id} удалено из планировщика (по запросу user_id {user_id}).", extra={'user_id': user_id})
        scheduler_success = True
    except JobLookupError:
        logger.warning(f"Задание {job_id} не найдено в планировщике при удалении (user_id {user_id}). Возможно, уже выполнено или удалено.", extra={'user_id': user_id})
        scheduler_success = True # Считаем успехом, если задания и так нет

    # 2. Удаляем из БД (функция delete_reminder проверяет user_id)
    try:
        db_success = delete_reminder(reminder_id, user_id)
        if not db_success:
             # delete_reminder уже логирует причину (не найдено или не принадлежит)
             pass
    except Exception as db_del_err:
        logger.exception(f"Ошибка при удалении напоминания ID {reminder_id} из БД для user_id {user_id}: {db_del_err}", extra={'user_id': user_id})
        db_success = False

    # Возвращаем True только если обе операции успешны (или не требовались)
    return scheduler_success and db_success


async def load_pending_reminders(bot: AsyncTeleBot):
    """
    Загружает ВСЕ активные напоминания из БД при старте бота
    и добавляет/обновляет их в планировщике.
    APScheduler сам обработает пропущенные задачи в рамках misfire_grace_time.
    Задачи, время которых слишком сильно прошло, будут проигнорированы планировщиком
    или выполнены немедленно, если misfire_grace_time позволяет.
    """
    logger.info("Загрузка активных напоминаний из БД для планировщика...", extra={'user_id': 'System'})
    pending_reminders: List[Dict[str, Any]] = []
    try:
        # Получаем ВСЕ активные напоминания
        pending_reminders = get_active_pending_reminders()
        logger.debug(f"Найдено {len(pending_reminders)} активных напоминаний в БД.", extra={'user_id': 'System'})
    except Exception as db_err:
         logger.exception(f"Критическая ошибка при получении активных напоминаний из db_manager: {db_err}", extra={'user_id': 'System'})
         return # Прерываем загрузку, если БД недоступна

    count_scheduled = 0
    count_errors = 0
    now_utc = datetime.datetime.now(pytz.utc)

    for reminder_data in pending_reminders:
        reminder_id = reminder_data.get('reminder_id')
        user_id = reminder_data.get('user_id')
        reminder_text = reminder_data.get('reminder_text')
        reminder_time_str = reminder_data.get('reminder_time')

        # Проверяем наличие всех данных
        if not all([reminder_id, user_id, reminder_text, reminder_time_str]):
            logger.error(f"Неполные данные для напоминания в БД: {reminder_data}. Пропускаем.", extra={'user_id': 'System'})
            count_errors += 1
            continue

        try:
            # Парсим время из ISO строки UTC
            reminder_dt_utc = datetime.datetime.fromisoformat(reminder_time_str.replace('Z', '+00:00'))
            # Убедимся, что оно aware и в UTC
            if reminder_dt_utc.tzinfo is None or reminder_dt_utc.tzinfo.utcoffset(reminder_dt_utc) != datetime.timedelta(0):
                 logger.warning(f"Время напоминания ID {reminder_id} из БД не было в UTC ({reminder_dt_utc.tzinfo}). Приводим к UTC.", extra={'user_id': 'System'})
                 if reminder_dt_utc.tzinfo is None:
                      reminder_dt_utc = pytz.utc.localize(reminder_dt_utc)
                 else:
                      reminder_dt_utc = reminder_dt_utc.astimezone(pytz.utc)

            job_id = f"reminder_{reminder_id}"

            # --- Логика обработки времени ---
            # Просто добавляем задачу в планировщик.
            # APScheduler сам решит, что делать, если время уже прошло,
            # основываясь на misfire_grace_time.
            scheduler.add_job(
                send_reminder_job,
                trigger='date',
                run_date=reminder_dt_utc, # Время UTC
                args=[bot, reminder_id, user_id, reminder_text],
                id=job_id,
                misfire_grace_time=60*15, # 15 минут
                replace_existing=True # Перезаписываем, если задание уже есть (на случай перезапуска)
            )
            count_scheduled += 1
            logger.debug(f"Задание {job_id} добавлено/обновлено в планировщике на {reminder_dt_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}", extra={'user_id': 'System'})

            # Логика для слишком старых напоминаний больше не нужна здесь,
            # так как send_reminder_job деактивирует их после выполнения или ошибки.
            # if reminder_dt_utc <= now_utc:
            #    time_diff_seconds = (now_utc - reminder_dt_utc).total_seconds()
            #    logger.info(f"Напоминание ID {reminder_id} ({reminder_dt_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}) уже в прошлом (на {time_diff_seconds:.0f} сек). APScheduler обработает его согласно misfire_grace_time.", extra={'user_id': 'System'})


        except ValueError as parse_err:
             logger.error(f"Ошибка парсинга времени '{reminder_time_str}' для напоминания ID {reminder_id}: {parse_err}. Деактивируем.", extra={'user_id': 'System'})
             deactivate_reminder(reminder_id) # Деактивируем в БД, если время некорректно
             count_errors += 1
        except Exception as schedule_err:
             logger.exception(f"Ошибка при добавлении/обновлении задания для напоминания ID {reminder_id} (user_id {user_id}): {schedule_err}", extra={'user_id': 'System'})
             count_errors += 1
             # Не деактивируем здесь, возможно временная проблема с планировщиком

    logger.info(f"Загрузка напоминаний завершена. Добавлено/обновлено в планировщике: {count_scheduled}. Ошибок обработки данных из БД: {count_errors}.", extra={'user_id': 'System'})


def start_scheduler():
    """Запускает планировщик."""
    try:
        if not scheduler.running:
            # Устанавливаем 'asyncio' в качестве event loop для APScheduler
            scheduler.configure(event_loop=asyncio.get_event_loop())
            scheduler.start()
            logger.info("Планировщик напоминаний APScheduler запущен.", extra={'user_id': 'System'})
        else:
             logger.warning("Планировщик напоминаний APScheduler уже был запущен.", extra={'user_id': 'System'})
    except Exception as e:
        logger.exception(f"Критическая ошибка: Не удалось запустить планировщик APScheduler: {e}", extra={'user_id': 'System'})
        # Возможно, стоит завершить работу бота, если планировщик критичен
        # sys.exit(1)

def shutdown_scheduler(wait: bool = False): # Добавили параметр wait
    """Останавливает планировщик."""
    try:
        if scheduler.running:
            # wait=False - не ждать завершения текущих задач (они могут быть долгими)
            # wait=True - дождаться завершения активных задач
            scheduler.shutdown(wait=wait)
            logger.info(f"Планировщик напоминаний APScheduler остановлен (wait={wait}).", extra={'user_id': 'System'})
        else:
            logger.info("Планировщик напоминаний APScheduler уже был остановлен.", extra={'user_id': 'System'})
    except Exception as e:
        logger.exception(f"Ошибка при остановке планировщика APScheduler: {e}", extra={'user_id': 'System'})

# Необходим импорт asyncio для пауз и event loop
import asyncio

def format_reminders_list(reminders: List[Dict[str, Any]]) -> str:
    """Форматирует список напоминаний для отображения в личном кабинете в виде текста."""
    if not reminders:
        return "У вас пока нет активных напоминаний."

    reminder_list_text = "--- Активные напоминания ---\n"
    # Сортируем напоминания по времени (как и в оригинальной функции)
    sorted_reminders = sorted(reminders, key=lambda r: r.get('reminder_time', ''))

    for reminder in sorted_reminders:
        try:
            reminder_id = reminder.get('reminder_id')
            reminder_text = reminder.get('reminder_text', 'Без текста')
            reminder_time_str = reminder.get('reminder_time')

            if not reminder_id or not reminder_time_str:
                 logger.warning(f"Неполные данные для напоминания в списке: {reminder}. Пропускаем.")
                 continue

            # Парсим время из ISO строки UTC
            reminder_time_dt_utc = datetime.datetime.fromisoformat(reminder_time_str.replace('Z', '+00:00'))

            # Форматируем для отображения (показываем UTC)
            time_str = reminder_time_dt_utc.strftime("%d.%m.%y %H:%M UTC")

            reminder_list_text += f"- ⏰ {time_str} - {reminder_text}\n"

        except Exception as e:
            reminder_id_log = reminder.get('reminder_id', 'N/A')
            logger.error(f"Ошибка обработки данных напоминания ID {reminder_id_log} для списка: {e}")
            reminder_list_text += f"⚠️ Ошибка данных напоминания ID {reminder_id_log}\n"

    return reminder_list_text
# --- END OF FILE features/reminders.py ---