# File: logger_config.py
import logging
import logging.config
import yaml
import os
from logging import LoggerAdapter, LogRecord
from typing import MutableMapping, Any, Optional

# Определяем базовую директорию проекта (папка, где лежит main.py)
# os.path.abspath(__file__) -> d:\Projects\MyGemini\logger_config.py
# os.path.dirname(...) -> d:\Projects\MyGemini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_CONFIG_FILE = os.path.join(BASE_DIR, "config", "logging.yaml")
LOG_DIR = os.path.join(BASE_DIR, "logs")


# Адаптер для добавления user_id к записям лога через 'extra'
class UserIdAdapter(LoggerAdapter):
    """
    Адаптер логгера, который обеспечивает наличие 'user_id' в каждой записи лога.
    """
    def process(self, msg: str, kwargs: MutableMapping[str, Any]) -> tuple[str, MutableMapping[str, Any]]:
        # Эта логика теперь не нужна, так как мы переопределяем log()
        return msg, kwargs

    def log(self, level: int, msg: Any, *args: Any, **kwargs: Any) -> None:
        """
        Переопределенный метод для гарантированного добавления user_id в 'extra'.
        """
        if self.isEnabledFor(level):
            # Получаем user_id, установленный при создании адаптера (например, get_logger('name', user_id=123))
            default_user_id = self.extra.get('user_id', 'System')

            # Проверяем, был ли user_id передан напрямую в вызове .log() (например, logger.info("msg", extra={'user_id': 456}))
            extra = kwargs.get('extra', {})
            if 'user_id' not in extra:
                extra['user_id'] = default_user_id

            kwargs['extra'] = extra

            # Вызываем оригинальный метод log базового логгера
            self.logger.log(level, msg, *args, **kwargs)


def setup_logging():
    """Настраивает логгер из YAML файла."""
    os.makedirs(LOG_DIR, exist_ok=True)

    if not os.path.exists(LOG_CONFIG_FILE):
        # Базовая конфигурация, если файл не найден.
        # Используем простой форматтер без user_id, чтобы избежать ошибок от сторонних библиотек.
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        logging.basicConfig(level=logging.INFO, format=log_format)
        logging.warning(
            f"Файл конфигурации логирования не найден: {LOG_CONFIG_FILE}. Используется базовая конфигурация.")
        return

    try:
        with open(LOG_CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            # Устанавливаем UserIdAdapter в качестве "фабрики" логгеров
            logging.setLoggerClass(UserIdAdapter)
            logging.config.dictConfig(config)
        print(f"Конфигурация логирования успешно загружена из {LOG_CONFIG_FILE}")
    except Exception as e:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        logging.basicConfig(level=logging.ERROR, format=log_format)
        logging.exception(
            f"Ошибка при загрузке конфигурации логирования из {LOG_CONFIG_FILE}: {e}. Используется базовая конфигурация.")


def get_logger(name: str, user_id: Optional[str | int] = None) -> UserIdAdapter:
    """
    Возвращает именованный логгер, обернутый в UserIdAdapter.
    """
    logger = logging.getLogger(name)
    user_id_str = str(user_id) if user_id is not None else 'System'

    # Убеждаемся, что логгер является экземпляром UserIdAdapter.
    # После setup_logging() это должно быть так, но для надежности можно проверить.
    if not isinstance(logger, UserIdAdapter):
        # Эта ветка не должна выполняться при нормальной работе, но она защищает от сбоев
        # ИСПРАВЛЕНА ОПЕЧАТКА: UserId-Adapter -> UserIdAdapter
        logger = UserIdAdapter(logger, {'user_id': user_id_str})
    else:
        # Если это уже адаптер, просто обновляем его 'extra'
        logger.extra['user_id'] = user_id_str

    return logger
