# File: database/db_manager.py
import sqlite3
import threading
import datetime
from typing import List, Tuple, Optional, Dict, Any

from logger_config import get_logger
from config.settings import DATABASE_NAME
from utils import crypto_helpers

db_logger = get_logger('database', user_id='System')
db_lock = threading.Lock()

def _get_db_connection() -> sqlite3.Connection:
    """Устанавливает соединение с базой данных SQLite."""
    try:
        conn = sqlite3.connect(DATABASE_NAME, check_same_thread=False, timeout=10.0,
                               detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn
    except sqlite3.Error as e:
        db_logger.exception(f"Ошибка подключения к базе данных {DATABASE_NAME}: {e}")
        raise

def _execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False,
                   is_write_operation: bool = False) -> Optional[Any]:
    """Выполняет SQL-запрос с обработкой соединения и блокировки для операций записи."""
    conn = None
    result = None
    try:
        if is_write_operation:
            with db_lock:
                conn = _get_db_connection()
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                if query.strip().upper().startswith("INSERT"):
                    result = cursor.lastrowid
                elif query.strip().upper().startswith(("UPDATE", "DELETE")):
                    result = cursor.rowcount
        else:
            conn = _get_db_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            if fetch_one:
                result = cursor.fetchone()
            elif fetch_all:
                result = cursor.fetchall()
            elif "count(" in query.lower() or "sum(" in query.lower():
                count_result = cursor.fetchone()
                result = count_result[0] if count_result and count_result[0] is not None else 0
    except sqlite3.Error as e:
        db_logger.exception(f"Ошибка выполнения SQL: {query} | Params: {params} | Error: {e}")
        if conn and is_write_operation:
            try:
                conn.rollback()
            except sqlite3.Error as rb_err:
                db_logger.error(f"Ошибка при откате транзакции: {rb_err}")
        if fetch_all: return []
        return None
    finally:
        if conn:
            conn.close()
    return result

def setup_database():
    """Инициализирует структуру базы данных, если она не существует."""
    # ИЗМЕНЕНО: Добавлено поле active_persona
    required_user_columns = {
        'user_id', 'bot_style', 'first_interaction_date',
        'api_key', 'language_code', 'gemini_model', 'active_persona'
    }
    required_conversation_columns = {
        'conversation_id', 'user_id', 'timestamp', 'role', 'message_text',
        'prompt_tokens', 'completion_tokens', 'total_tokens'
    }

    conn = None
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        existing_tables = {table['name'] for table in tables}
        db_logger.info(f"Существующие таблицы: {existing_tables}")

        if 'users' not in existing_tables:
            db_logger.info("Таблица 'users' не найдена, создаем...")
            cursor.execute("""
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                bot_style TEXT DEFAULT 'default' NOT NULL,
                first_interaction_date TEXT,
                api_key TEXT DEFAULT NULL,
                language_code TEXT DEFAULT 'ru' NOT NULL,
                gemini_model TEXT DEFAULT NULL,
                active_persona TEXT DEFAULT 'default' NOT NULL
            )
            """)
            db_logger.info("Таблица 'users' успешно создана.")
        else:
            cursor.execute("PRAGMA table_info(users)")
            current_columns = {col['name'] for col in cursor.fetchall()}
            missing_columns = required_user_columns - current_columns
            for col in missing_columns:
                db_logger.info(f"Добавляем отсутствующий столбец '{col}' в таблицу 'users'...")
                col_type = 'TEXT'
                default_val_str = 'DEFAULT NULL'
                not_null_str = ''

                if col == 'bot_style':
                    default_val_str = "DEFAULT 'default'"
                    not_null_str = 'NOT NULL'
                elif col == 'language_code':
                    default_val_str = "DEFAULT 'ru'"
                    not_null_str = 'NOT NULL'
                # НОВОЕ: Правило для нового поля
                elif col == 'active_persona':
                    default_val_str = "DEFAULT 'default'"
                    not_null_str = 'NOT NULL'

                try:
                    add_col_query = f"ALTER TABLE users ADD COLUMN {col} {col_type} {not_null_str} {default_val_str}"
                    cursor.execute(add_col_query)
                    db_logger.info(f"Столбец '{col}' успешно добавлен в 'users'.")
                except sqlite3.OperationalError as alter_err:
                    db_logger.warning(f"Не удалось добавить столбец {col} в users: {alter_err}")

        if 'reminders' in existing_tables:
            db_logger.info("Таблица 'reminders' больше не используется, удаляем...")
            cursor.execute("DROP TABLE reminders")
            db_logger.info("Таблица 'reminders' успешно удалена.")

        if 'conversations' not in existing_tables:
            db_logger.info("Таблица 'conversations' не найдена, создаем...")
            cursor.execute("""
                CREATE TABLE conversations (
                    conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'bot', 'system')),
                    message_text TEXT,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_time ON conversations (user_id, timestamp)")
            db_logger.info("Таблица 'conversations' и индекс успешно созданы.")
        else:
            cursor.execute("PRAGMA table_info(conversations)")
            current_columns = {col['name'] for col in cursor.fetchall()}
            missing_columns = required_conversation_columns - current_columns
            for col in missing_columns:
                if col in ['prompt_tokens', 'completion_tokens', 'total_tokens']:
                    db_logger.info(f"Добавляем отсутствующий столбец '{col}' в таблицу 'conversations'...")
                    try:
                        add_col_query = f"ALTER TABLE conversations ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0"
                        cursor.execute(add_col_query)
                        db_logger.info(f"Столбец '{col}' успешно добавлен в 'conversations'.")
                    except sqlite3.OperationalError as alter_err:
                        db_logger.warning(f"Не удалось добавить столбец {col} в conversations: {alter_err}")

        conn.commit()
        db_logger.info("Проверка и настройка базы данных завершена.")
    except sqlite3.Error as e:
        db_logger.exception(f"Ошибка при настройке базы данных: {e}")
        if conn:
            try: conn.rollback()
            except sqlite3.Error as rb_err: db_logger.error(f"Ошибка при откате транзакции: {rb_err}")
    finally:
        if conn: conn.close()

def add_or_update_user(user_id: int, bot_style: str = 'default'):
    """Добавляет нового пользователя или обновляет его данные."""
    query_select = "SELECT user_id, first_interaction_date FROM users WHERE user_id = ?"
    user_data = _execute_query(query_select, (user_id,), fetch_one=True)
    today_date_str = datetime.date.today().strftime('%Y-%m-%d')

    if user_data:
        if not user_data['first_interaction_date']:
            query_update = "UPDATE users SET first_interaction_date = ? WHERE user_id = ?"
            _execute_query(query_update, (today_date_str, user_id), is_write_operation=True)
    else:
        db_logger.info(f"Добавляем нового пользователя {user_id}.", extra={'user_id': str(user_id)})
        query_insert = "INSERT INTO users (user_id, bot_style, first_interaction_date) VALUES (?, ?, ?)"
        _execute_query(query_insert, (user_id, bot_style, today_date_str), is_write_operation=True)

# --- Функции для работы с пользователями (users) ---

def get_user_bot_style(user_id: int) -> str:
    query = "SELECT bot_style FROM users WHERE user_id = ?"
    result = _execute_query(query, (user_id,), fetch_one=True)
    return result['bot_style'] if result and result['bot_style'] else 'default'

def set_user_bot_style(user_id: int, style: str):
    add_or_update_user(user_id)
    query = "UPDATE users SET bot_style = ? WHERE user_id = ?"
    _execute_query(query, (style, user_id), is_write_operation=True)
    db_logger.info(f"Стиль бота для {user_id} изменен на '{style}'.", extra={'user_id': str(user_id)})

def set_user_api_key(user_id: int, api_key: str):
    add_or_update_user(user_id)
    try:
        encrypted_key = crypto_helpers.encrypt_data(api_key)
        query = "UPDATE users SET api_key = ? WHERE user_id = ?"
        _execute_query(query, (encrypted_key, user_id), is_write_operation=True)
        db_logger.info(f"API-ключ для пользователя {user_id} был зашифрован и сохранен.", extra={'user_id': str(user_id)})
    except Exception as e:
        db_logger.exception(f"Ошибка при шифровании и сохранении API-ключа для {user_id}: {e}", extra={'user_id': str(user_id)})

def get_user_api_key(user_id: int) -> Optional[str]:
    query = "SELECT api_key FROM users WHERE user_id = ?"
    result = _execute_query(query, (user_id,), fetch_one=True)
    if result and result['api_key']:
        encrypted_key = result['api_key']
        try:
            decrypted_key = crypto_helpers.decrypt_data(encrypted_key)
            if decrypted_key:
                return decrypted_key
            else:
                db_logger.error(f"Не удалось дешифровать API-ключ для {user_id}. Возможно, ключ шифрования изменился.", extra={'user_id': str(user_id)})
                return None
        except Exception as e:
            db_logger.exception(f"Ошибка при дешифровании API-ключа для {user_id}: {e}", extra={'user_id': str(user_id)})
            return None
    return None

def set_user_language(user_id: int, lang_code: str):
    add_or_update_user(user_id)
    query = "UPDATE users SET language_code = ? WHERE user_id = ?"
    _execute_query(query, (lang_code, user_id), is_write_operation=True)
    db_logger.info(f"Язык для {user_id} изменен на '{lang_code}'.", extra={'user_id': str(user_id)})

def get_user_language(user_id: int) -> str:
    query = "SELECT language_code FROM users WHERE user_id = ?"
    result = _execute_query(query, (user_id,), fetch_one=True)
    return result['language_code'] if result and result['language_code'] else 'ru'

def set_user_gemini_model(user_id: int, model_name: str):
    """Устанавливает выбранную модель Gemini для пользователя."""
    add_or_update_user(user_id)
    query = "UPDATE users SET gemini_model = ? WHERE user_id = ?"
    _execute_query(query, (model_name, user_id), is_write_operation=True)
    db_logger.info(f"Модель Gemini для {user_id} изменена на '{model_name}'.", extra={'user_id': str(user_id)})

def get_user_gemini_model(user_id: int) -> Optional[str]:
    """Получает модель Gemini, выбранную пользователем."""
    query = "SELECT gemini_model FROM users WHERE user_id = ?"
    result = _execute_query(query, (user_id,), fetch_one=True)
    return result['gemini_model'] if result and result['gemini_model'] else None

# --- НОВЫЕ ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ ПЕРСОНОЙ ---
def set_user_persona(user_id: int, persona_id: str):
    """Устанавливает активную персону для пользователя."""
    add_or_update_user(user_id)
    query = "UPDATE users SET active_persona = ? WHERE user_id = ?"
    _execute_query(query, (persona_id, user_id), is_write_operation=True)
    db_logger.info(f"Активная персона для {user_id} изменена на '{persona_id}'.", extra={'user_id': str(user_id)})

def get_user_persona(user_id: int) -> str:
    """Получает активную персону пользователя."""
    query = "SELECT active_persona FROM users WHERE user_id = ?"
    result = _execute_query(query, (user_id,), fetch_one=True)
    return result['active_persona'] if result and result['active_persona'] else 'default'

# --- Функции для работы с историей сообщений (conversations) ---

def store_message(user_id: int, role: str, message_text: str,
                  prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0):
    """Сохраняет сообщение в базу данных, включая информацию о токенах."""
    if role not in ('user', 'bot', 'system'):
        return
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    query = """
        INSERT INTO conversations 
        (user_id, timestamp, role, message_text, prompt_tokens, completion_tokens, total_tokens) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    params = (user_id, timestamp, role, message_text, prompt_tokens, completion_tokens, total_tokens)
    _execute_query(query, params, is_write_operation=True)

def get_conversation_history(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    query = "SELECT role, message_text FROM conversations WHERE user_id = ? ORDER BY conversation_id DESC LIMIT ?"
    rows = _execute_query(query, (user_id, limit), fetch_all=True)
    return [dict(row) for row in reversed(rows)] if rows else []

def get_conversation_history_by_date(user_id: int, history_date: datetime.date) -> List[Dict[str, Any]]:
    start_dt = datetime.datetime.combine(history_date, datetime.time.min, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime.combine(history_date, datetime.time.max, tzinfo=datetime.timezone.utc)
    query = "SELECT role, message_text FROM conversations WHERE user_id = ? AND timestamp BETWEEN ? AND ? ORDER BY timestamp ASC"
    rows = _execute_query(query, (user_id, start_dt.isoformat(), end_dt.isoformat()), fetch_all=True)
    return [dict(row) for row in rows] if rows else []

def get_conversation_count(user_id: int) -> int:
    query = "SELECT COUNT(*) FROM conversations WHERE user_id = ?"
    count = _execute_query(query, (user_id,))
    return count if count is not None else 0

def get_first_interaction_date(user_id: int) -> Optional[str]:
    query = "SELECT first_interaction_date FROM users WHERE user_id = ?"
    result = _execute_query(query, (user_id,), fetch_one=True)
    return result['first_interaction_date'] if result else None

def get_token_usage_by_period(user_id: int, period: str) -> Dict[str, int]:
    """
    Возвращает суммарное количество токенов за указанный период ('today' или 'month').
    """
    if period == 'today':
        start_date_str = datetime.date.today().isoformat() + "T00:00:00Z"
    elif period == 'month':
        start_date_str = datetime.date.today().replace(day=1).isoformat() + "T00:00:00Z"
    else:
        return {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}

    query = """
        SELECT 
            SUM(prompt_tokens), 
            SUM(completion_tokens), 
            SUM(total_tokens) 
        FROM conversations 
        WHERE user_id = ? AND timestamp >= ?
    """
    params = (user_id, start_date_str)

    conn = _get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        result = cursor.fetchone()
        if result and result[0] is not None:
            return {
                'prompt_tokens': int(result[0]),
                'completion_tokens': int(result[1]),
                'total_tokens': int(result[2])
            }
    except sqlite3.Error as e:
        db_logger.exception(f"Ошибка при получении статистики токенов за период '{period}' для user {user_id}: {e}")
    finally:
        if conn:
            conn.close()

    return {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
