# --- START OF FILE main.py ---
import asyncio
import signal
import sys
import os
from telebot.async_telebot import AsyncTeleBot
# from telebot import SimpleCustomFilter # Закомментировано, так как не используется
from telebot.asyncio_storage import StateMemoryStorage # Простое хранилище состояний в памяти

# --- 1. Настройка и инициализация ---
# Важно: сначала настроить логирование
from logger_config import setup_logging, get_logger

# Запускаем настройку логирования ДО импорта других модулей, использующих логгер
setup_logging()
main_logger = get_logger(__name__) # Логгер для главного модуля

# Импортируем остальные компоненты
try:
    from config import settings # Настройки бота (токены и т.д.)
    from database import db_manager
    from features import reminders # Модуль напоминаний
    # Импортируем регистраторы хендлеров
    from handlers import command_handlers, callback_handlers, message_handlers
    # user_states импортируется внутри хендлеров, здесь он не нужен напрямую
    # from handlers.command_handlers import user_states # Убираем этот импорт
    # Импортируем сервисы
    from services import gemini_service # Добавим импорт для возможной инициализации сервисов
except ImportError as e:
    main_logger.exception(f"Критическая ошибка: Не удалось импортировать необходимые модули: {e}", extra={'user_id': 'System'})
    sys.exit(1) # Завершаем работу, если базовые модули не найдены
except Exception as e:
    main_logger.exception(f"Критическая ошибка при инициализации импортов: {e}", extra={'user_id': 'System'})
    sys.exit(1)


# --- 2. Инициализация бота ---
try:
    # Используем StateMemoryStorage для простого управления состояниями
    # В production лучше использовать RedisStorage или аналоги
    state_storage = StateMemoryStorage()
    # Создаем асинхронного бота
    bot = AsyncTeleBot(settings.BOT_TOKEN, state_storage=state_storage, parse_mode='Markdown')
    main_logger.info("Экземпляр AsyncTeleBot создан.", extra={'user_id': 'System'})
except Exception as e:
    main_logger.exception(f"Критическая ошибка: Не удалось создать экземпляр бота: {e}", extra={'user_id': 'System'})
    sys.exit(1)

# --- 3. Настройка базы данных ---
try:
    main_logger.info("Настройка базы данных...", extra={'user_id': 'System'})
    db_manager.setup_database()
    main_logger.info("База данных успешно настроена.", extra={'user_id': 'System'})
except Exception as e:
    main_logger.exception("Критическая ошибка: Не удалось настроить базу данных.", extra={'user_id': 'System'})
    sys.exit(1)

# --- 4. Регистрация обработчиков ---
try:
    main_logger.info("Регистрация обработчиков...", extra={'user_id': 'System'})
    # Передаем экземпляр бота в функции регистрации
    command_handlers.register_command_handlers(bot)
    callback_handlers.register_callback_handlers(bot)
    message_handlers.register_message_handlers(bot)
    # Здесь можно добавить регистрацию других обработчиков (inline, кастомные фильтры и т.д.)
    main_logger.info("Обработчики успешно зарегистрированы.", extra={'user_id': 'System'})
except Exception as e:
    main_logger.exception("Критическая ошибка: Не удалось зарегистрировать обработчики.", extra={'user_id': 'System'})
    sys.exit(1)

# --- 5. Инициализация и запуск фоновых задач (планировщик) ---
# Эта функция будет вызвана внутри основного async цикла
async def initialize_background_tasks(bot_instance: AsyncTeleBot):
    """Инициализирует и запускает фоновые задачи, такие как планировщик."""
    try:
        main_logger.info("Инициализация планировщика напоминаний...", extra={'user_id': 'System'})
        # Загружаем напоминания из БД в планировщик
        await reminders.load_pending_reminders(bot_instance)
        # Запускаем сам планировщик
        reminders.start_scheduler() # Эта функция теперь не async
        main_logger.info("Планировщик напоминаний инициализирован и запущен.", extra={'user_id': 'System'})

        # Здесь можно инициализировать другие фоновые сервисы, если они появятся
        # await some_other_service.initialize()

    except Exception as e:
        main_logger.exception("Критическая ошибка при инициализации фоновых задач (планировщик).", extra={'user_id': 'System'})
        # Решаем, критична ли эта ошибка для запуска бота
        sys.exit(1) # Если планировщик критичен, завершаем работу

# --- 6. Функция основного цикла бота ---
async def run_bot_polling(bot_instance: AsyncTeleBot):
    """Запускает основной цикл опроса Telegram (polling)."""
    main_logger.info("Запуск бота (polling)...", extra={'user_id': 'System'})
    # none_stop=True - продолжает работу при большинстве ошибок Telegram API
    # interval=1 - интервал опроса (в секундах)
    try:
        await bot_instance.polling(none_stop=True, interval=1)
    except asyncio.CancelledError:
        main_logger.info("Задача поллинга отменена (ожидаемо при завершении).", extra={'user_id': 'System'})
        # Не пробрасываем CancelledError дальше
    except Exception as e:
         # Ловим другие возможные ошибки поллинга
         main_logger.exception("Критическая ошибка в цикле polling.", extra={'user_id': 'System'})
         # Здесь можно добавить логику перезапуска или уведомления
    finally:
        main_logger.info("Цикл polling завершен.", extra={'user_id': 'System'})

# --- 7. Управление жизненным циклом приложения ---
shutdown_event = asyncio.Event() # Событие для сигнализации о завершении

async def main():
    """Основная асинхронная функция, управляющая запуском и остановкой."""
    main_logger.info("Запуск основной асинхронной функции main().", extra={'user_id': 'System'})

    # Инициализируем фоновые задачи (планировщик)
    await initialize_background_tasks(bot)

    # Создаем задачу для поллинга
    polling_task = asyncio.create_task(run_bot_polling(bot))

    # Ожидаем сигнала о завершении
    await shutdown_event.wait()

    # Начало процесса остановки
    main_logger.warning("Начало процесса graceful shutdown...", extra={'user_id': 'System'})

    # 1. Останавливаем планировщик (ждем завершения активных задач или нет - False)
    main_logger.info("Остановка планировщика...", extra={'user_id': 'System'})
    reminders.shutdown_scheduler(wait=False) # Не ждем завершения задач напоминаний

    # 2. Отменяем задачу поллинга
    main_logger.info("Отмена задачи поллинга...", extra={'user_id': 'System'})
    polling_task.cancel()

    # 3. Ждем завершения задачи поллинга (она должна обработать CancelledError)
    try:
        await polling_task
        main_logger.info("Задача поллинга успешно завершилась после отмены.", extra={'user_id': 'System'})
    except asyncio.CancelledError:
        main_logger.info("Поллинг был отменен (как и ожидалось).", extra={'user_id': 'System'})
    except Exception as e:
         main_logger.exception("Ошибка при ожидании завершения задачи поллинга.", extra={'user_id': 'System'})


    # 4. Закрываем соединение с ботом (если необходимо)
    # В pyTelegramBotAPI обычно нет явного метода close() для AsyncTeleBot,
    # остановка поллинга считается достаточной.

    # 5. Здесь можно добавить остановку других сервисов, если они есть

    main_logger.info("Graceful shutdown завершен.", extra={'user_id': 'System'})


def handle_shutdown_signal(signum, frame):
    """Обработчик сигналов SIGINT и SIGTERM."""
    if not shutdown_event.is_set():
        main_logger.warning(f"Получен сигнал завершения ({signal.Signals(signum).name}). Инициирую graceful shutdown...", extra={'user_id': 'System'})
        shutdown_event.set() # Устанавливаем событие, чтобы основной цикл начал завершение
    else:
        main_logger.warning("Повторный сигнал завершения получен. Процесс уже останавливается.", extra={'user_id': 'System'})


# --- 8. Точка входа ---
if __name__ == '__main__':
    main_logger.info(f"Запуск бота (PID: {os.getpid()})...", extra={'user_id': 'System'})

    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, handle_shutdown_signal) # Ctrl+C
    signal.signal(signal.SIGTERM, handle_shutdown_signal) # Сигнал от systemd/docker

    try:
        # Запускаем основной асинхронный цикл
        asyncio.run(main())
    except KeyboardInterrupt:
        # Это исключение может возникнуть, если Ctrl+C нажать до запуска asyncio.run()
        main_logger.info("Завершение работы по KeyboardInterrupt (до запуска main loop).", extra={'user_id': 'System'})
    except Exception as e:
        main_logger.exception("Необработанная критическая ошибка на верхнем уровне.", extra={'user_id': 'System'})
        # Убедимся, что планировщик остановлен перед выходом, если он успел запуститься
        reminders.shutdown_scheduler(wait=False)
        sys.exit(1) # Выход с кодом ошибки
    finally:
        # Этот блок выполнится после завершения asyncio.run()
        main_logger.info("Работа бота завершена.", extra={'user_id': 'System'})
        logging.shutdown() # Корректно закрываем логгеры
        sys.exit(0) # Нормальный выход

# Добавим импорт os для getpid()
import os
import logging # Для logging.shutdown()
# --- END OF FILE main.py ---