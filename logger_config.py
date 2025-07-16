# --- START OF FILE logger_config.py ---
import logging
import logging.config
import yaml
import os
from logging import LoggerAdapter
from typing import MutableMapping, Any, Optional

# Определяем базовую директорию проекта (где лежит этот файл)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_CONFIG_FILE = os.path.join(BASE_DIR, "config", "logging.yaml")  # Путь к файлу конфигурации логов
LOG_DIR = os.path.join(BASE_DIR, "logs")  # Путь к папке с логами


# Адаптер для добавления user_id к записям лога через 'extra'
class UserIdAdapter(LoggerAdapter):
    def process(self, msg: str, kwargs: MutableMapping[str, Any]) -> tuple[str, MutableMapping[str, Any]]:
        # Получаем user_id из 'extra' самого адаптера (установленного при создании)
        default_user_id = self.extra.get('user_id', 'System')

        # Получаем user_id из 'extra', переданного при вызове лога
        # Если он есть, он переопределит user_id из адаптера
        log_call_user_id = kwargs.get('extra', {}).get('user_id')

        # Определяем финальный user_id для этой записи лога
        final_user_id = log_call_user_id or default_user_id

        # Убедимся, что 'extra' существует в kwargs
        if 'extra' not in kwargs:
            kwargs['extra'] = {}

        # Добавляем/обновляем user_id в 'extra' для использования форматтером
        kwargs['extra']['user_id'] = final_user_id

        # Возвращаем исходное сообщение и обновленные kwargs
        # Форматтер должен быть настроен на использование %(user_id)s
        return msg, kwargs


def setup_logging():
    """Настраивает логгер из YAML файла."""
    # Создаем папку для логов, если она не существует
    os.makedirs(LOG_DIR, exist_ok=True)

    if not os.path.exists(LOG_CONFIG_FILE):
        # Базовая конфигурация, если файл не найден
        # Определяем форматтер с user_id для базовой конфигурации
        log_format = '%(asctime)s - %(name)s - [%(user_id)s] - %(levelname)s - %(message)s'
        logging.basicConfig(level=logging.INFO, format=log_format)
        logging.warning(
            f"Файл конфигурации логирования не найден: {LOG_CONFIG_FILE}. Используется базовая конфигурация.")
        # Не нужно устанавливать UserIdAdapter как класс логгера
        return

    try:
        with open(LOG_CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            # Загружаем конфигурацию
            logging.config.dictConfig(config)

        print(f"Конфигурация логирования успешно загружена из {LOG_CONFIG_FILE}")
    except Exception as e:
        # Обработка ошибок при загрузке конфигурации
        log_format = '%(asctime)s - %(name)s - [%(user_id)s] - %(levelname)s - %(message)s'
        logging.basicConfig(level=logging.ERROR, format=log_format)
        logging.exception(
            f"Ошибка при загрузке конфигурации логирования из {LOG_CONFIG_FILE}: {e}. Используется базовая конфигурация.")


# Используем UserIdAdapter в аннотации возвращаемого значения
def get_logger(name: str, user_id: Optional[str | int] = None) -> UserIdAdapter:
    """
    Возвращает именованный логгер, который должен быть UserIdAdapter.
    Устанавливает user_id по умолчанию для этого экземпляра адаптера.
    """
    # Получаем логгер. После setup_logging он должен быть UserIdAdapter.
    logger = logging.getLogger(name)
    # Преобразуем user_id в строку, если это число
    user_id_str = str(user_id) if user_id is not None else 'System'

    # Оборачиваем логгер в UserIdAdapter
    logger = UserIdAdapter(logger, {'user_id': user_id_str})

    # Убедимся, что возвращаем именно UserIdAdapter (для корректной аннотации)
    # Это приведение типа не меняет объект, но удовлетворяет проверку типов
    return logger  # type: ignore

# --- END OF FILE logger_config.py ---