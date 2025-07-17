# File: database/db_manager.py
import sqlite3
import asyncio
import datetime
from typing import List, Tuple, Optional, Dict, Any

from logger_config import get_logger
from config.settings import DATABASE_NAME
from utils import crypto_helpers

db_logger = get_logger('database', user_id='System')
db_lock = asyncio.Lock()  # Используем asyncio.Lock

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


def _execute_sync(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False,
                  is_write_operation: bool = False) -> Optional[Any]:
    """
    (СИНХРОННАЯ ВНУТРЕННЯЯ ФУНКЦИЯ) Выполняет SQL-запрос.
    Эта функция предназначена для запуска в отдельном потоке.
    """
    conn = None
    result = None
    try:
        conn = _get_db_connection()
        if is_write_operation:
            conn.isolation_level = 'EXCLUSIVE'
            conn.execute('BEGIN EXCLUSIVE')

        cursor = conn.cursor()
        cursor.execute(query, params)

        if fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
        elif "count(" in query.lower() or "sum(" in query.lower():
            count_result = cursor.fetchone()
            result = count_result[0] if count_result and count_result[0] is not None else 0

        if is_write_operation:
            if query.strip().upper().startswith("INSERT"):
                result = cursor.lastrowid
            elif query.strip().upper().startswith(("UPDATE", "DELETE")):
                result = cursor.rowcount
            conn.commit()

    except sqlite3.Error as e:
        db_logger.exception(f"Ошибка выполнения SQL: {query} | Params: {params} | Error: {e}")
        if conn and is_write_operation:
            try:
                conn.rollback()
            except sqlite3.Error as rb_err:
                db_logger.error(f"Ошибка при откате транзакции: {rb_err}")
        if fetch_all: return []
        # Пробрасываем ошибку дальше, чтобы ее можно было обработать
        raise e
    finally:
        if conn:
            conn.close()
    return result


async def _execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False,
                         is_write_operation: bool = False) -> Optional[Any]:
    """(АСИНХРОННАЯ ОБЕРТКА) Выполняет SQL-запрос в отдельном потоке, чтобы не блокировать event loop."""
    try:
        if is_write_operation:
            async with db_lock:
                return await asyncio.to_thread(
                    _execute_sync, query, params, fetch_one, fetch_all, is_write_operation
                )
        else:
            return await asyncio.to_thread(
                _execute_sync, query, params, fetch_one, fetch_all, is_write_operation
            )
    except Exception as e:
        # Логируем ошибку, которая была проброшена из _execute_sync
        db_logger.error(f"Перехвачена ошибка из _execute_sync в _execute_query: {e}")
        # Возвращаем None или пустой список, чтобы не ломать вызывающий код
        if fetch_all: return []
        return None


def setup_database_sync():
    """Синхронная функция для инициализации и миграции структуры базы данных."""
    conn = _get_db_connection()
    cursor = conn.cursor()
    try:
        # --- Таблица app_settings ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        db_logger.info("Таблица 'app_settings' проверена/создана.")

        # --- Таблица users ---
        cursor.execute("PRAGMA table_info(users)")
        user_columns = {col['name'] for col in cursor.fetchall()}
        if not user_columns:
            db_logger.info("Таблица 'users' не найдена, создаем...")
            cursor.execute("""
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                bot_style TEXT DEFAULT 'default' NOT NULL,
                first_interaction_date TEXT,
                api_key TEXT DEFAULT NULL,
                language_code TEXT DEFAULT 'ru' NOT NULL,
                gemini_model TEXT DEFAULT NULL,
                active_persona TEXT DEFAULT 'default' NOT NULL,
                active_dialog_id INTEGER REFERENCES dialogs(dialog_id) ON DELETE SET NULL,
                is_blocked INTEGER NOT NULL DEFAULT 0
            )""")
        else:
            required_user_columns = {'active_dialog_id', 'active_persona', 'is_blocked'}
            missing_user_columns = required_user_columns - user_columns
            for col in missing_user_columns:
                db_logger.info(f"Добавляем отсутствующий столбец '{col}' в 'users'...")
                if col == 'active_persona':
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT 'default' NOT NULL")
                elif col == 'is_blocked':
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
                else: # active_dialog_id
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER REFERENCES dialogs(dialog_id) ON DELETE SET NULL")

        # --- Таблица dialogs ---
        cursor.execute("PRAGMA table_info(dialogs)")
        if not cursor.fetchall():
            db_logger.info("Таблица 'dialogs' не найдена, создаем...")
            cursor.execute("""
            CREATE TABLE dialogs (
                dialog_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )""")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dialogs_user ON dialogs (user_id)")

        # --- Таблица conversations ---
        cursor.execute("PRAGMA table_info(conversations)")
        conversation_columns = {col['name'] for col in cursor.fetchall()}
        if not conversation_columns:
             db_logger.info("Таблица 'conversations' не найдена, создаем...")
             cursor.execute("""
                CREATE TABLE conversations (
                    conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'bot')),
                    message_text TEXT,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    dialog_id INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (dialog_id) REFERENCES dialogs(dialog_id) ON DELETE CASCADE
                )""")
             cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_dialog_time ON conversations (dialog_id, timestamp)")
        elif 'dialog_id' not in conversation_columns:
            db_logger.info("Добавляем отсутствующий столбец 'dialog_id' в 'conversations'...")
            cursor.execute("ALTER TABLE conversations ADD COLUMN dialog_id INTEGER REFERENCES dialogs(dialog_id) ON DELETE CASCADE")

        conn.commit()

        # --- Миграция старых данных ---
        cursor.execute("SELECT user_id FROM users WHERE active_dialog_id IS NULL")
        users_to_migrate = cursor.fetchall()
        if users_to_migrate:
            db_logger.info(f"Найдено {len(users_to_migrate)} пользователей для миграции на систему диалогов...")
            for row in users_to_migrate:
                user_id = row['user_id']
                default_dialog_name = "Основной диалог"
                now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cursor.execute("INSERT INTO dialogs (user_id, name, created_at) VALUES (?, ?, ?)",
                               (user_id, default_dialog_name, now_str))
                new_dialog_id = cursor.lastrowid
                cursor.execute("UPDATE users SET active_dialog_id = ? WHERE user_id = ?", (new_dialog_id, user_id))
                cursor.execute("UPDATE conversations SET dialog_id = ? WHERE user_id = ? AND dialog_id IS NULL", (new_dialog_id, user_id))
                db_logger.info(f"Пользователь {user_id} успешно мигрирован. Создан диалог ID: {new_dialog_id}.")
            conn.commit()

            # Пересоздаем таблицу, чтобы сделать dialog_id NOT NULL
            db_logger.info("Пересоздание таблицы 'conversations', чтобы сделать столбец 'dialog_id' NOT NULL...")
            cursor.execute("PRAGMA foreign_keys=off")
            cursor.execute("BEGIN TRANSACTION")
            cursor.execute("""
                CREATE TABLE conversations_new (
                    conversation_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('user', 'bot')),
                    message_text TEXT, prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0, total_tokens INTEGER NOT NULL DEFAULT 0,
                    dialog_id INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (dialog_id) REFERENCES dialogs(dialog_id) ON DELETE CASCADE
                )""")
            cursor.execute("INSERT INTO conversations_new SELECT * FROM conversations WHERE dialog_id IS NOT NULL")
            cursor.execute("DROP TABLE conversations")
            cursor.execute("ALTER TABLE conversations_new RENAME TO conversations")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_dialog_time ON conversations (dialog_id, timestamp)")
            cursor.execute("COMMIT")
            cursor.execute("PRAGMA foreign_keys=on")
            db_logger.info("Столбец 'dialog_id' в таблице 'conversations' успешно обновлен.")

        db_logger.info("Проверка и настройка базы данных завершена.")
    except Exception as e:
        db_logger.exception(f"Критическая ошибка при настройке/миграции базы данных: {e}")
        if conn: conn.rollback()
        raise
    finally:
        if conn: conn.close()


async def setup_database():
    """Асинхронная обертка для запуска синхронной настройки БД в отдельном потоке."""
    await asyncio.to_thread(setup_database_sync)


async def add_or_update_user(user_id: int):
    """Добавляет нового пользователя или обновляет его данные, включая создание диалога по умолчанию."""
    user_data = await _execute_query("SELECT user_id, active_dialog_id FROM users WHERE user_id = ?", (user_id,), fetch_one=True)
    if not user_data:
        db_logger.info(f"Добавляем нового пользователя {user_id}.")
        today_date_str = datetime.date.today().strftime('%Y-%m-%d')
        query_insert_user = "INSERT INTO users (user_id, first_interaction_date) VALUES (?, ?)"
        await _execute_query(query_insert_user, (user_id, today_date_str), is_write_operation=True)
        await create_dialog(user_id, "Основной диалог", set_active=True)
    elif not user_data['active_dialog_id']:
        db_logger.warning(f"У существующего пользователя {user_id} нет активного диалога. Создаем новый.")
        await create_dialog(user_id, "Основной диалог", set_active=True)


async def create_dialog(user_id: int, name: str, set_active: bool = False) -> Optional[int]:
    """Создает новый диалог для пользователя и опционально делает его активным."""
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    query = "INSERT INTO dialogs (user_id, name, created_at) VALUES (?, ?, ?)"
    new_dialog_id = await _execute_query(query, (user_id, name, now_str), is_write_operation=True)
    if new_dialog_id:
        if set_active:
            await set_active_dialog(user_id, new_dialog_id)
        db_logger.info(f"Для пользователя {user_id} создан новый диалог '{name}' (ID: {new_dialog_id}).")
        return int(new_dialog_id)
    return None


async def get_user_dialogs(user_id: int) -> List[Dict[str, Any]]:
    """Получает список всех диалогов пользователя."""
    query = "SELECT d.dialog_id, d.name, u.active_dialog_id FROM dialogs d JOIN users u ON d.user_id = u.user_id WHERE d.user_id = ? ORDER BY d.created_at DESC"
    rows = await _execute_query(query, (user_id,), fetch_all=True)
    return [dict(row) for row in rows] if rows else []


async def set_active_dialog(user_id: int, dialog_id: int):
    """Устанавливает активный диалог для пользователя."""
    query = "UPDATE users SET active_dialog_id = ? WHERE user_id = ?"
    await _execute_query(query, (dialog_id, user_id), is_write_operation=True)
    db_logger.info(f"Для пользователя {user_id} установлен активный диалог ID: {dialog_id}.")


async def rename_dialog(dialog_id: int, new_name: str):
    """Переименовывает диалог."""
    query = "UPDATE dialogs SET name = ? WHERE dialog_id = ?"
    await _execute_query(query, (new_name, dialog_id), is_write_operation=True)
    db_logger.info(f"Диалог ID {dialog_id} переименован в '{new_name}'.")


async def delete_dialog(user_id: int, dialog_id_to_delete: int) -> Optional[str]:
    """
    Удаляет диалог и его историю. Гарантирует, что у пользователя останется активный диалог.
    Возвращает имя удаленного диалога.
    """
    other_dialogs = await _execute_query(
        "SELECT dialog_id FROM dialogs WHERE user_id = ? AND dialog_id != ? ORDER BY created_at DESC",
        (user_id, dialog_id_to_delete),
        fetch_all=True
    )
    if not other_dialogs:
        db_logger.warning(f"Попытка удалить последний диалог {dialog_id_to_delete} для пользователя {user_id}. Операция отменена.")
        return None
    
    active_dialog_id = await get_active_dialog_id(user_id)
    if active_dialog_id == dialog_id_to_delete:
        new_active_dialog_id = other_dialogs[0]['dialog_id']
        await set_active_dialog(user_id, new_active_dialog_id)

    dialog_info = await _execute_query("SELECT name FROM dialogs WHERE dialog_id = ?", (dialog_id_to_delete,), fetch_one=True)
    if not dialog_info: return None

    delete_query = "DELETE FROM dialogs WHERE dialog_id = ?"
    rows_affected = await _execute_query(delete_query, (dialog_id_to_delete,), is_write_operation=True)
    if rows_affected:
        db_logger.info(f"Диалог ID {dialog_id_to_delete} удален для пользователя {user_id}.")
        return dialog_info['name']
    return None


async def get_active_dialog_id(user_id: int) -> Optional[int]:
    """Получает ID активного диалога пользователя."""
    query = "SELECT active_dialog_id FROM users WHERE user_id = ?"
    result = await _execute_query(query, (user_id,), fetch_one=True)
    return result['active_dialog_id'] if result else None


async def get_user_context_info(user_id: int) -> Optional[Dict[str, Any]]:
    """Получает единым запросом всю информацию для контекстного заголовка."""
    query = """
        SELECT
            d.name as dialog_name,
            u.gemini_model,
            u.active_persona
        FROM users u
        LEFT JOIN dialogs d ON u.active_dialog_id = d.dialog_id
        WHERE u.user_id = ?
    """
    result = await _execute_query(query, (user_id,), fetch_one=True)
    return dict(result) if result else None


async def store_message(user_id: int, dialog_id: int, role: str, message_text: str,
                  prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0):
    """Сохраняет сообщение в базу данных с привязкой к диалогу."""
    if role not in ('user', 'bot'): return
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    query = """
        INSERT INTO conversations 
        (user_id, dialog_id, timestamp, role, message_text, prompt_tokens, completion_tokens, total_tokens) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (user_id, dialog_id, timestamp, role, message_text, prompt_tokens, completion_tokens, total_tokens)
    await _execute_query(query, params, is_write_operation=True)


async def get_conversation_history(dialog_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """Получает историю сообщений для конкретного диалога."""
    query = "SELECT role, message_text FROM conversations WHERE dialog_id = ? ORDER BY conversation_id DESC LIMIT ?"
    rows = await _execute_query(query, (dialog_id, limit), fetch_all=True)
    return [dict(row) for row in reversed(rows)] if rows else []


async def get_conversation_history_by_date(dialog_id: int, history_date: datetime.date) -> List[Dict[str, Any]]:
    """Получает историю сообщений для конкретного диалога за определенную дату."""
    start_dt = datetime.datetime.combine(history_date, datetime.time.min, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime.combine(history_date, datetime.time.max, tzinfo=datetime.timezone.utc)
    query = "SELECT role, message_text FROM conversations WHERE dialog_id = ? AND timestamp BETWEEN ? AND ? ORDER BY timestamp ASC"
    rows = await _execute_query(query, (dialog_id, start_dt.isoformat(), end_dt.isoformat()), fetch_all=True)
    return [dict(row) for row in rows] if rows else []


async def get_total_user_message_count(user_id: int) -> int:
    """Получает общее количество сообщений пользователя во всех его диалогах."""
    query = "SELECT COUNT(*) FROM conversations WHERE user_id = ?"
    count = await _execute_query(query, (user_id,))
    return count if count is not None else 0


async def set_user_bot_style(user_id: int, style: str):
    await add_or_update_user(user_id)
    query = "UPDATE users SET bot_style = ? WHERE user_id = ?"
    await _execute_query(query, (style, user_id), is_write_operation=True)


async def get_user_bot_style(user_id: int) -> str:
    query = "SELECT bot_style FROM users WHERE user_id = ?"
    result = await _execute_query(query, (user_id,), fetch_one=True)
    return result['bot_style'] if result else 'default'


async def set_user_api_key(user_id: int, api_key: Optional[str]):
    """Устанавливает или сбрасывает API-ключ пользователя."""
    await add_or_update_user(user_id)
    encrypted_key = crypto_helpers.encrypt_data(api_key) if api_key else None
    query = "UPDATE users SET api_key = ? WHERE user_id = ?"
    await _execute_query(query, (encrypted_key, user_id), is_write_operation=True)
    db_logger.info(f"API-ключ для пользователя {user_id} {'установлен' if api_key else 'сброшен'}.")


async def get_user_api_key(user_id: int) -> Optional[str]:
    query = "SELECT api_key FROM users WHERE user_id = ?"
    result = await _execute_query(query, (user_id,), fetch_one=True)
    if result and result['api_key']:
        encrypted_key = result['api_key']
        try:
            return crypto_helpers.decrypt_data(encrypted_key)
        except Exception as e:
            db_logger.exception(f"Ошибка при дешифровании API-ключа для {user_id}: {e}", extra={'user_id': str(user_id)})
            return None
    return None


async def set_user_language(user_id: int, lang_code: str):
    await add_or_update_user(user_id)
    query = "UPDATE users SET language_code = ? WHERE user_id = ?"
    await _execute_query(query, (lang_code, user_id), is_write_operation=True)


async def get_user_language(user_id: int) -> str:
    query = "SELECT language_code FROM users WHERE user_id = ?"
    result = await _execute_query(query, (user_id,), fetch_one=True)
    return result['language_code'] if result and result['language_code'] else 'ru'


async def set_user_gemini_model(user_id: int, model_name: str):
    await add_or_update_user(user_id)
    query = "UPDATE users SET gemini_model = ? WHERE user_id = ?"
    await _execute_query(query, (model_name, user_id), is_write_operation=True)


async def get_user_gemini_model(user_id: int) -> Optional[str]:
    query = "SELECT gemini_model FROM users WHERE user_id = ?"
    result = await _execute_query(query, (user_id,), fetch_one=True)
    return result['gemini_model'] if result and result['gemini_model'] else None


async def set_user_persona(user_id: int, persona_id: str):
    await add_or_update_user(user_id)
    query = "UPDATE users SET active_persona = ? WHERE user_id = ?"
    await _execute_query(query, (persona_id, user_id), is_write_operation=True)


async def get_user_persona(user_id: int) -> str:
    query = "SELECT active_persona FROM users WHERE user_id = ?"
    result = await _execute_query(query, (user_id,), fetch_one=True)
    return result['active_persona'] if result and result['active_persona'] else 'default'


async def get_first_interaction_date(user_id: int) -> Optional[str]:
    query = "SELECT first_interaction_date FROM users WHERE user_id = ?"
    result = await _execute_query(query, (user_id,), fetch_one=True)
    return result['first_interaction_date'] if result else None


async def get_token_usage_by_period(user_id: int, period: str) -> Dict[str, int]:
    if period == 'today':
        start_date_str = datetime.date.today().isoformat() + "T00:00:00Z"
    elif period == 'month':
        start_date_str = datetime.date.today().replace(day=1).isoformat() + "T00:00:00Z"
    else:
        return {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}

    query = "SELECT SUM(prompt_tokens), SUM(completion_tokens), SUM(total_tokens) FROM conversations WHERE user_id = ? AND timestamp >= ?"
    params = (user_id, start_date_str)
    
    result_row = await _execute_query(query, params, fetch_one=True)
    
    if result_row and result_row[0] is not None:
        return {
            'prompt_tokens': int(result_row[0]),
            'completion_tokens': int(result_row[1]),
            'total_tokens': int(result_row[2])
        }
    return {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}

# --- НОВЫЕ ФУНКЦИИ ДЛЯ АДМИН-ПАНЕЛИ ---

async def set_app_setting(key: str, value: str):
    """Устанавливает или обновляет глобальную настройку приложения."""
    query = "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value"
    await _execute_query(query, (key, value), is_write_operation=True)
    db_logger.info(f"Глобальная настройка '{key}' установлена в значение '{value}'.")

async def get_app_setting(key: str) -> Optional[str]:
    """Получает значение глобальной настройки приложения."""
    query = "SELECT value FROM app_settings WHERE key = ?"
    result = await _execute_query(query, (key,), fetch_one=True)
    return result['value'] if result else None

async def is_user_blocked(user_id: int) -> bool:
    """Проверяет, заблокирован ли пользователь."""
    query = "SELECT is_blocked FROM users WHERE user_id = ?"
    result = await _execute_query(query, (user_id,), fetch_one=True)
    return result['is_blocked'] == 1 if result else False

async def block_user(user_id: int):
    """Блокирует пользователя."""
    await _execute_query("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,), is_write_operation=True)
    db_logger.info(f"Пользователь {user_id} заблокирован.")

async def unblock_user(user_id: int):
    """Разблокирует пользователя."""
    await _execute_query("UPDATE users SET is_blocked = 0 WHERE user_id = ?", (user_id,), is_write_operation=True)
    db_logger.info(f"Пользователь {user_id} разблокирован.")

async def get_all_user_ids() -> List[int]:
    """Возвращает список ID всех пользователей."""
    rows = await _execute_query("SELECT user_id FROM users", fetch_all=True)
    return [row['user_id'] for row in rows] if rows else []

async def get_total_users_count() -> int:
    """Возвращает общее количество пользователей."""
    count = await _execute_query("SELECT COUNT(*) FROM users")
    return count if count is not None else 0

async def get_blocked_users_count() -> int:
    """Возвращает количество заблокированных пользователей."""
    count = await _execute_query("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
    return count if count is not None else 0

async def get_active_users_count(days: int = 7) -> int:
    """Возвращает количество пользователей, отправлявших сообщения за последние N дней."""
    start_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    query = "SELECT COUNT(DISTINCT user_id) FROM conversations WHERE timestamp >= ?"
    count = await _execute_query(query, (start_date.isoformat(),))
    return count if count is not None else 0

async def get_new_users_count(days: int = 7) -> int:
    """Возвращает количество новых пользователей за последние N дней."""
    start_date = datetime.date.today() - datetime.timedelta(days=days)
    query = "SELECT COUNT(*) FROM users WHERE first_interaction_date >= ?"
    count = await _execute_query(query, (start_date.strftime('%Y-%m-%d'),))
    return count if count is not None else 0

async def get_user_info_for_admin(user_id: int) -> Optional[Dict[str, Any]]:
    """Собирает подробную информацию о пользователе для админ-панели."""
    query = """
        SELECT
            u.user_id,
            u.language_code,
            u.first_interaction_date,
            u.is_blocked,
            (SELECT COUNT(*) FROM conversations WHERE user_id = u.user_id) as message_count
        FROM users u
        WHERE u.user_id = ?
    """
    row = await _execute_query(query, (user_id,), fetch_one=True)
    return dict(row) if row else None