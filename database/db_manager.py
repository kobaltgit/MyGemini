# File: database/db_manager.py
import sqlite3
import asyncio
import datetime
from typing import List, Tuple, Optional, Dict, Any

from logger_config import get_logger
from config.settings import DATABASE_NAME, DEFAULT_MODEL_ID
from utils import crypto_helpers
from handlers import telegram_helpers as tg_helpers

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
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                bot_style TEXT DEFAULT 'default' NOT NULL,
                first_interaction_date TEXT,
                api_key TEXT DEFAULT NULL,
                language_code TEXT DEFAULT 'ru' NOT NULL,
                gemini_model TEXT DEFAULT NULL,
                active_persona TEXT DEFAULT 'default' NOT NULL,
                active_dialog_id INTEGER REFERENCES dialogs(dialog_id) ON DELETE SET NULL,
                is_blocked INTEGER NOT NULL DEFAULT 0,
                thinking_budget INTEGER NOT NULL DEFAULT 1024,
                enable_code_execution INTEGER NOT NULL DEFAULT 0,
                enable_google_search INTEGER NOT NULL DEFAULT 0,
                header_style TEXT NOT NULL DEFAULT 'blockquote',
                message_format TEXT NOT NULL DEFAULT 'rich'
            )""")
        else:
            # Обновлено: добавляем новые поля для миграции
            required_user_columns = {
                'active_dialog_id': "INTEGER REFERENCES dialogs(dialog_id) ON DELETE SET NULL",
                'active_persona': "TEXT DEFAULT 'default' NOT NULL",
                'is_blocked': "INTEGER NOT NULL DEFAULT 0",
                'username': "TEXT",
                'first_name': "TEXT",
                'last_name': "TEXT",
                'thinking_budget': "INTEGER NOT NULL DEFAULT 1024",
                'enable_code_execution': "INTEGER NOT NULL DEFAULT 0",
                'enable_google_search': "INTEGER NOT NULL DEFAULT 0",
                'header_style': "TEXT NOT NULL DEFAULT 'blockquote'",
                'message_format': "TEXT NOT NULL DEFAULT 'rich'",
                'subscription_status': "TEXT DEFAULT 'inactive' NOT NULL",
                'subscription_end_date': "TEXT DEFAULT NULL",
            }
            missing_user_columns = set(required_user_columns.keys()) - user_columns
            for col in missing_user_columns:
                col_def = required_user_columns[col]
                db_logger.info(f"Добавляем отсутствующий столбец '{col}' ({col_def}) в 'users'...")
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_def}")

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

        # --- Таблица subscription_payments ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscription_payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL DEFAULT 'RUB',
                payment_date TEXT NOT NULL,
                subscription_end_date TEXT NOT NULL,
                telegram_charge_id TEXT,
                provider_charge_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_user ON subscription_payments (user_id)")

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


async def add_or_update_user(user_id: int, username: Optional[str], first_name: Optional[str], last_name: Optional[str]):
    """
    Добавляет нового пользователя или обновляет его данные (имена).
    Также создает диалог по умолчанию, если это необходимо.
    """
    user_data = await _execute_query("SELECT user_id, active_dialog_id FROM users WHERE user_id = ?", (user_id,), fetch_one=True)

    # ВРЕМЕННЫЙ ЛОГ 1
    db_logger.info(f"[DEBUG] Проверка пользователя {user_id}. Найден в БД: {'Да' if user_data else 'Нет'}")

    if not user_data:
        # ВРЕМЕННЫЙ ЛОГ 2
        db_logger.info(f"[DEBUG] Пользователь {user_id} определен как новый. Вызываю уведомление.")
        db_logger.info(f"Добавляем нового пользователя {user_id} (@{username}).")
        today_date_str = datetime.date.today().strftime('%Y-%m-%d')
        query_insert_user = """
            INSERT INTO users (user_id, username, first_name, last_name, first_interaction_date, gemini_model) 
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (user_id, username, first_name, last_name, today_date_str, DEFAULT_MODEL_ID)
        await _execute_query(query_insert_user, params, is_write_operation=True)
        # Отправка уведомления администратору
        await tg_helpers.notify_admin_of_new_user(user_id, username, first_name, last_name)
        # Создаем диалог по умолчанию для нового пользователя
        await create_dialog(user_id, "Основной диалог", set_active=True)
    else:
        # Пользователь уже существует, обновляем его имена, так как они могли измениться
        query_update_user = """
            UPDATE users SET username = ?, first_name = ?, last_name = ? WHERE user_id = ?
        """
        params = (username, first_name, last_name, user_id)
        await _execute_query(query_update_user, params, is_write_operation=True)
        
        # Проверяем, есть ли у пользователя активный диалог (для старых пользователей)
        if not user_data['active_dialog_id']:
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
    query = "SELECT role, message_text, timestamp FROM conversations WHERE dialog_id = ? AND timestamp BETWEEN ? AND ? ORDER BY timestamp ASC"
    rows = await _execute_query(query, (dialog_id, start_dt.isoformat(), end_dt.isoformat()), fetch_all=True)
    return [dict(row) for row in rows] if rows else []


async def get_total_user_message_count(user_id: int) -> int:
    """Получает общее количество сообщений пользователя во всех его диалогах."""
    query = "SELECT COUNT(*) FROM conversations WHERE user_id = ?"
    count = await _execute_query(query, (user_id,))
    return count if count is not None else 0


async def set_user_bot_style(user_id: int, style: str):
    user_info = await _execute_query("SELECT username, first_name, last_name FROM users WHERE user_id = ?", (user_id,), fetch_one=True)
    await add_or_update_user(user_id, user_info['username'], user_info['first_name'], user_info['last_name'])
    query = "UPDATE users SET bot_style = ? WHERE user_id = ?"
    await _execute_query(query, (style, user_id), is_write_operation=True)


async def get_user_bot_style(user_id: int) -> str:
    query = "SELECT bot_style FROM users WHERE user_id = ?"
    result = await _execute_query(query, (user_id,), fetch_one=True)
    return result['bot_style'] if result else 'default'


async def set_user_api_key(user_id: int, api_key: Optional[str]):
    """Устанавливает или сбрасывает API-ключ пользователя."""
    user_info = await _execute_query("SELECT username, first_name, last_name FROM users WHERE user_id = ?", (user_id,), fetch_one=True)
    await add_or_update_user(user_id, user_info['username'], user_info['first_name'], user_info['last_name'])
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
    user_info = await _execute_query("SELECT username, first_name, last_name FROM users WHERE user_id = ?", (user_id,), fetch_one=True)
    await add_or_update_user(user_id, user_info['username'], user_info['first_name'], user_info['last_name'])
    query = "UPDATE users SET language_code = ? WHERE user_id = ?"
    await _execute_query(query, (lang_code, user_id), is_write_operation=True)


async def get_user_language(user_id: int) -> str:
    query = "SELECT language_code FROM users WHERE user_id = ?"
    result = await _execute_query(query, (user_id,), fetch_one=True)
    return result['language_code'] if result and result['language_code'] else 'ru'


async def set_user_gemini_model(user_id: int, model_name: str):
    user_info = await _execute_query("SELECT username, first_name, last_name FROM users WHERE user_id = ?", (user_id,), fetch_one=True)
    await add_or_update_user(user_id, user_info['username'], user_info['first_name'], user_info['last_name'])
    query = "UPDATE users SET gemini_model = ? WHERE user_id = ?"
    await _execute_query(query, (model_name, user_id), is_write_operation=True)


async def get_user_gemini_model(user_id: int) -> Optional[str]:
    query = "SELECT gemini_model FROM users WHERE user_id = ?"
    result = await _execute_query(query, (user_id,), fetch_one=True)
    return result['gemini_model'] if result and result['gemini_model'] else None


async def set_user_persona(user_id: int, persona_id: str):
    user_info = await _execute_query("SELECT username, first_name, last_name FROM users WHERE user_id = ?", (user_id,), fetch_one=True)
    await add_or_update_user(user_id, user_info['username'], user_info['first_name'], user_info['last_name'])
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
            u.username,
            u.first_name,
            u.last_name,
            u.language_code,
            u.first_interaction_date,
            u.is_blocked,
            (SELECT COUNT(*) FROM conversations WHERE user_id = u.user_id) as message_count
        FROM users u
        WHERE u.user_id = ?
    """
    row = await _execute_query(query, (user_id,), fetch_one=True)
    # Также обновляем информацию о пользователе при просмотре
    if row:
        user_info = dict(row)
        # Добавляем обновление имени пользователя при его просмотре админом
        # Это необязательно, но может быть полезно
        # await add_or_update_user(user_id, user_info.get('username'), user_info.get('first_name'), user_info.get('last_name'))
        return user_info
    return None


async def get_users_with_key_count() -> int:
    """Возвращает количество пользователей с установленным API-ключом."""
    count = await _execute_query("SELECT COUNT(*) FROM users WHERE api_key IS NOT NULL AND api_key != ''")
    return count if count is not None else 0


async def get_user_message_count(user_id: int) -> int:
    """Возвращает количество сообщений конкретного пользователя."""
    count = await _execute_query("SELECT COUNT(*) FROM conversations WHERE user_id = ?", (user_id,))
    return count if count is not None else 0


async def get_all_users_with_stats() -> List[Dict[str, Any]]:
    """Возвращает список всех пользователей с агрегированной статистикой."""
    query = """
        SELECT
            u.user_id,
            u.username,
            u.first_name,
            u.last_name,
            u.language_code,
            u.first_interaction_date,
            u.is_blocked,
            (u.api_key IS NOT NULL AND u.api_key != '') as has_api_key,
            u.gemini_model,
            u.bot_style,
            u.active_persona,
            (SELECT COUNT(*) FROM conversations WHERE user_id = u.user_id) as message_count
        FROM users u
        ORDER BY u.user_id DESC
    """
    rows = await _execute_query(query, fetch_all=True)
    return [dict(r) for r in rows] if rows else []


# --- ФУНКЦИЯ ДЛЯ ЭКСПОРТА ---
async def get_all_users_for_export() -> List[Dict[str, Any]]:
    """Извлекает всех пользователей со всеми необходимыми полями для экспорта в CSV."""
    query = """
        SELECT
            u.user_id,
            u.username,
            u.first_name,
            u.last_name,
            u.language_code,
            u.first_interaction_date,
            u.is_blocked,
            (u.api_key IS NOT NULL AND u.api_key != '') as has_api_key,
            u.bot_style,
            u.gemini_model,
            u.active_persona,
            (SELECT COUNT(*) FROM conversations WHERE user_id = u.user_id) as message_count
        FROM users u
        ORDER BY u.user_id ASC
    """
    rows = await _execute_query(query, fetch_all=True)
    return [dict(row) for row in rows] if rows else []


# ===================================================================================
# --- НОВЫЕ МЕТОДЫ ДЛЯ MyGemini v2 (aiogram 3.x) ---
# ===================================================================================

async def get_user_settings(user_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает все настройки пользователя."""
    query = """
        SELECT user_id, username, first_name, last_name, bot_style,
               first_interaction_date, api_key, language_code, gemini_model,
               active_persona, active_dialog_id, is_blocked, thinking_budget,
               enable_code_execution, enable_google_search, header_style, message_format
        FROM users WHERE user_id = ?
    """
    row = await _execute_query(query, (user_id,), fetch_one=True)
    return dict(row) if row else None


async def set_user_header_style(user_id: int, header_style: str):
    """Обновляет стиль шапки ответа (blockquote, expandable, hidden)."""
    query = "UPDATE users SET header_style = ? WHERE user_id = ?"
    await _execute_query(query, (header_style, user_id), is_write_operation=True)


async def get_user_header_style(user_id: int) -> str:
    """Возвращает стиль шапки ответа пользователя."""
    query = "SELECT header_style FROM users WHERE user_id = ?"
    row = await _execute_query(query, (user_id,), fetch_one=True)
    if row and row['header_style']:
        return row['header_style']
    return 'blockquote'


async def set_user_message_format(user_id: int, message_format: str):
    """Обновляет формат сообщений (rich, classic)."""
    query = "UPDATE users SET message_format = ? WHERE user_id = ?"
    await _execute_query(query, (message_format, user_id), is_write_operation=True)


async def get_user_message_format(user_id: int) -> str:
    """Возвращает формат сообщений пользователя."""
    query = "SELECT message_format FROM users WHERE user_id = ?"
    row = await _execute_query(query, (user_id,), fetch_one=True)
    if row and row['message_format']:
        return row['message_format']
    return 'rich'


async def set_user_thinking_budget(user_id: int, budget: int):
    """Обновляет бюджет размышлений модели (0, 1024, 4096)."""
    query = "UPDATE users SET thinking_budget = ? WHERE user_id = ?"
    await _execute_query(query, (budget, user_id), is_write_operation=True)


async def get_user_thinking_budget(user_id: int) -> int:
    """Возвращает бюджет размышлений пользователя."""
    query = "SELECT thinking_budget FROM users WHERE user_id = ?"
    row = await _execute_query(query, (user_id,), fetch_one=True)
    if row and row['thinking_budget'] is not None:
        return int(row['thinking_budget'])
    return 1024


async def toggle_user_code_execution(user_id: int) -> bool:
    """Переключает статус песочницы Python и возвращает новое значение."""
    query_select = "SELECT enable_code_execution FROM users WHERE user_id = ?"
    row = await _execute_query(query_select, (user_id,), fetch_one=True)
    current_val = bool(row['enable_code_execution']) if row and row['enable_code_execution'] is not None else False
    new_val = not current_val
    query_update = "UPDATE users SET enable_code_execution = ? WHERE user_id = ?"
    await _execute_query(query_update, (1 if new_val else 0, user_id), is_write_operation=True)
    return new_val


async def get_user_code_execution(user_id: int) -> bool:
    """Возвращает флаг активности песочницы Python."""
    query = "SELECT enable_code_execution FROM users WHERE user_id = ?"
    row = await _execute_query(query, (user_id,), fetch_one=True)
    return bool(row['enable_code_execution']) if row and row['enable_code_execution'] is not None else False


async def toggle_user_google_search(user_id: int) -> bool:
    """Переключает статус Google Search и возвращает новое значение."""
    query_select = "SELECT enable_google_search FROM users WHERE user_id = ?"
    row = await _execute_query(query_select, (user_id,), fetch_one=True)
    current_val = bool(row['enable_google_search']) if row and row['enable_google_search'] is not None else False
    new_val = not current_val
    query_update = "UPDATE users SET enable_google_search = ? WHERE user_id = ?"
    await _execute_query(query_update, (1 if new_val else 0, user_id), is_write_operation=True)
    return new_val


async def get_user_google_search(user_id: int) -> bool:
    """Возвращает флаг активности Google Search."""
    query = "SELECT enable_google_search FROM users WHERE user_id = ?"
    row = await _execute_query(query, (user_id,), fetch_one=True)
    return bool(row['enable_google_search']) if row and row['enable_google_search'] is not None else False


async def clear_dialog_history(dialog_id: int):
    """Удаляет все сообщения из диалога, сохраняя сам диалог."""
    query = "DELETE FROM conversations WHERE dialog_id = ?"
    await _execute_query(query, (dialog_id,), is_write_operation=True)
    db_logger.info(f"Очищена история диалога ID {dialog_id}")


async def delete_last_assistant_message(dialog_id: int) -> Optional[int]:
    """Удаляет последнее сообщение ассистента из диалога (для кнопки [🔄 Еще раз])."""
    query_find = """
        SELECT conversation_id FROM conversations
        WHERE dialog_id = ? AND role = 'bot'
        ORDER BY conversation_id DESC LIMIT 1
    """
    row = await _execute_query(query_find, (dialog_id,), fetch_one=True)
    if not row:
        return None
    conv_id = row['conversation_id']
    query_del = "DELETE FROM conversations WHERE conversation_id = ?"
    await _execute_query(query_del, (conv_id,), is_write_operation=True)
    return conv_id


async def delete_last_conversation_turn(dialog_id: int) -> bool:
    """Удаляет последний диалоговый шаг (сообщение бота и предшествующее сообщение пользователя) (для [↩️ Откатить шаг])."""
    query_last_bot = """
        SELECT conversation_id FROM conversations
        WHERE dialog_id = ? AND role = 'bot'
        ORDER BY conversation_id DESC LIMIT 1
    """
    bot_row = await _execute_query(query_last_bot, (dialog_id,), fetch_one=True)
    if not bot_row:
        return False
    bot_conv_id = bot_row['conversation_id']

    query_last_user = """
        SELECT conversation_id FROM conversations
        WHERE dialog_id = ? AND role = 'user' AND conversation_id < ?
        ORDER BY conversation_id DESC LIMIT 1
    """
    user_row = await _execute_query(query_last_user, (dialog_id, bot_conv_id), fetch_one=True)

    ids_to_delete = [bot_conv_id]
    if user_row:
        ids_to_delete.append(user_row['conversation_id'])

    for cid in ids_to_delete:
        await _execute_query("DELETE FROM conversations WHERE conversation_id = ?", (cid,), is_write_operation=True)
    return True


async def get_dialog_all_messages(dialog_id: int) -> List[Dict[str, Any]]:
    """Извлекает всю историю сообщений диалога по возрастанию времени (для экспорта в .md)."""
    query = """
        SELECT role, message_text, timestamp, prompt_tokens, completion_tokens, total_tokens
        FROM conversations
        WHERE dialog_id = ?
        ORDER BY conversation_id ASC
    """
    rows = await _execute_query(query, (dialog_id,), fetch_all=True)
    return [dict(r) for r in rows] if rows else []


async def get_dialog_info(dialog_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает информацию о диалоге по ID."""
    query = "SELECT dialog_id, user_id, name, created_at FROM dialogs WHERE dialog_id = ?"
    row = await _execute_query(query, (dialog_id,), fetch_one=True)
    return dict(row) if row else None


# ===================================================================================
# --- АДМИН-ПАНЕЛЬ: УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ И ПОДПИСКАМИ ---
# ===================================================================================

async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает полную карточку пользователя по ID."""
    query = """
        SELECT user_id, username, first_name, last_name, bot_style,
               first_interaction_date, api_key, language_code, gemini_model,
               active_persona, active_dialog_id, is_blocked, thinking_budget,
               enable_code_execution, enable_google_search, header_style, message_format,
               subscription_status, subscription_end_date
        FROM users WHERE user_id = ?
    """
    row = await _execute_query(query, (user_id,), fetch_one=True)
    return dict(row) if row else None


async def get_all_users() -> List[Dict[str, Any]]:
    """Возвращает список всех зарегистрированных пользователей."""
    query = """
        SELECT user_id, username, first_name, last_name, bot_style,
               first_interaction_date, api_key, language_code, gemini_model,
               active_persona, is_blocked, subscription_status, subscription_end_date
        FROM users ORDER BY user_id ASC
    """
    rows = await _execute_query(query, fetch_all=True)
    return [dict(r) for r in rows] if rows else []


async def set_user_blocked(user_id: int, is_blocked: bool):
    """Блокирует или разблокирует пользователя."""
    query = "UPDATE users SET is_blocked = ? WHERE user_id = ?"
    await _execute_query(query, (1 if is_blocked else 0, user_id), is_write_operation=True)
    db_logger.info(f"Статус блокировки пользователя {user_id} изменен на {is_blocked}")


async def reset_user_api_key(user_id: int):
    """Сбрасывает сохраненный API-ключ пользователя."""
    query = "UPDATE users SET api_key = NULL WHERE user_id = ?"
    await _execute_query(query, (user_id,), is_write_operation=True)
    db_logger.info(f"API-ключ пользователя {user_id} сброшен администратором")


async def update_user_subscription(user_id: int, status: str, end_date: str):
    """Обновляет статус и дату окончания подписки пользователя."""
    query = "UPDATE users SET subscription_status = ?, subscription_end_date = ? WHERE user_id = ?"
    await _execute_query(query, (status, end_date, user_id), is_write_operation=True)
    db_logger.info(f"Подписка пользователя {user_id} обновлена: статус={status}, до={end_date}")


async def record_payment(
    user_id: int,
    plan_id: str,
    amount: int,
    currency: str = "RUB",
    payment_date: Optional[str] = None,
    subscription_end_date: Optional[str] = None,
    telegram_charge_id: Optional[str] = None,
    provider_charge_id: Optional[str] = None,
) -> int:
    """Записывает транзакцию оплаты подписки."""
    now_str = payment_date or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    end_str = subscription_end_date or ""
    query = """
        INSERT INTO subscription_payments (
            user_id, plan_id, amount, currency, payment_date,
            subscription_end_date, telegram_charge_id, provider_charge_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (user_id, plan_id, amount, currency, now_str, end_str, telegram_charge_id, provider_charge_id)
    payment_id = await _execute_query(query, params, is_write_operation=True)
    db_logger.info(f"Записан платеж {amount} {currency} для пользователя {user_id}")
    return payment_id


async def get_user_payments(user_id: int) -> List[Dict[str, Any]]:
    """Возвращает историю платежей конкретного пользователя."""
    query = """
        SELECT payment_id, user_id, plan_id, amount, currency, payment_date, subscription_end_date
        FROM subscription_payments
        WHERE user_id = ?
        ORDER BY payment_id DESC
    """
    rows = await _execute_query(query, (user_id,), fetch_all=True)
    return [dict(r) for r in rows] if rows else []


async def get_all_payments() -> List[Dict[str, Any]]:
    """Возвращает все платежи в обратном хронологическом порядке."""
    query = """
        SELECT payment_id, user_id, plan_id, amount, currency, payment_date, subscription_end_date
        FROM subscription_payments
        ORDER BY payment_id DESC
    """
    rows = await _execute_query(query, fetch_all=True)
    return [dict(r) for r in rows] if rows else []


async def get_all_subscribers() -> List[Dict[str, Any]]:
    """Возвращает список всех подписчиков (активных или когда-либо оформлявших)."""
    from config.settings import ADMIN_USER_ID
    query = """
        SELECT user_id, username, first_name, last_name, language_code,
               first_interaction_date, subscription_status, subscription_end_date, is_blocked
        FROM users
        WHERE subscription_status = 'active'
           OR subscription_end_date IS NOT NULL
           OR user_id = ?
        ORDER BY user_id ASC
    """
    rows = await _execute_query(query, (ADMIN_USER_ID or 0,), fetch_all=True)
    return [dict(r) for r in rows] if rows else []


async def get_payment_stats() -> Dict[str, Any]:
    """Агрегирует статистику по платежам и подписчикам."""
    count_row = await _execute_query("SELECT COUNT(*) as c FROM subscription_payments", fetch_one=True)
    sum_row = await _execute_query("SELECT SUM(amount) as s FROM subscription_payments", fetch_one=True)
    unique_row = await _execute_query("SELECT COUNT(DISTINCT user_id) as u FROM subscription_payments", fetch_one=True)

    total_payments = count_row['c'] if count_row else 0
    total_revenue = sum_row['s'] if sum_row and sum_row['s'] is not None else 0
    unique_paying_users = unique_row['u'] if unique_row else 0

    return {
        "total_payments": total_payments,
        "total_revenue": total_revenue,
        "unique_paying_users": unique_paying_users,
    }


def is_subscription_active(user_dict: Dict[str, Any]) -> bool:
    """Проверяет, активна ли подписка пользователя (вечная для ADMIN_USER_ID)."""
    from config.settings import ADMIN_USER_ID
    uid = user_dict.get("user_id")
    if ADMIN_USER_ID and uid == ADMIN_USER_ID:
        return True

    status = user_dict.get("subscription_status")
    end_date_str = user_dict.get("subscription_end_date")
    if status == "active":
        if not end_date_str:
            return True
        try:
            end_date = datetime.datetime.strptime(end_date_str[:10], "%Y-%m-%d").date()
            return end_date >= datetime.date.today()
        except Exception:
            return True
    return False