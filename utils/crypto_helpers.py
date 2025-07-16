import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

from logger_config import get_logger

# Загружаем переменные окружения, чтобы получить доступ к ENCRYPTION_KEY
load_dotenv()

logger = get_logger(__name__, user_id='CryptoSystem')

# Загружаем мастер-ключ из переменных окружения
# Этот ключ вы должны сгенерировать один раз и добавить в .env
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    logger.critical("ENCRYPTION_KEY не найдена в переменных окружения! Шифрование невозможно.")
    raise ValueError("Необходимо установить переменную окружения ENCRYPTION_KEY")

try:
    # Инициализируем Fernet с мастер-ключом
    fernet = Fernet(ENCRYPTION_KEY.encode())
    logger.info("Сервис шифрования успешно инициализирован.")
except (ValueError, TypeError) as e:
    logger.critical(f"Ошибка инициализации Fernet. Проверьте корректность ENCRYPTION_KEY: {e}")
    raise

def encrypt_data(data: str) -> str:
    """Шифрует строку и возвращает зашифрованную строку в формате base64."""
    encrypted_data = fernet.encrypt(data.encode('utf-8'))
    return encrypted_data.decode('utf-8')

def decrypt_data(encrypted_data: str) -> Optional[str]:
    """Дешифрует строку. Возвращает исходную строку или None в случае ошибки."""
    try:
        decrypted_data = fernet.decrypt(encrypted_data.encode('utf-8'))
        return decrypted_data.decode('utf-8')
    except InvalidToken:
        logger.error("Ошибка дешифрования: неверный токен (ключ или данные повреждены).")
        return None
    except Exception as e:
        logger.exception(f"Неожиданная ошибка при дешифровании: {e}")
        return None
