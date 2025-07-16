# MyGemini: Ваш личный Telegram-ассистент на базе Gemini

[
![Python](https://img.shields.io/badge/Python-3.10+-blue.svg?style=flat-square)
](https://www.python.org/downloads/)
[
![pyTelegramBotAPI](https://img.shields.io/badge/pyTelegramBotAPI-4.15.0+-brightgreen.svg?style=flat-square)
](https://github.com/eternnoir/pyTelegramBotAPI)
[
![Gemini API](https://img.shields.io/badge/Gemini_API-Via_REST-orange.svg?style=flat-square)
](https://ai.google.dev/)
[
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)
](https://opensource.org/licenses/MIT)

## Описание проекта

**MyGemini** — это асинхронный, многоязычный Telegram-бот, который служит вашим личным и безопасным шлюзом к возможностям Google Gemini API. В отличие от публичных ботов, MyGemini использует **ваш собственный API-ключ**, что обеспечивает вам полный контроль над квотами и расходами.

Бот спроектирован с акцентом на безопасность: ваши API-ключи шифруются и никогда не хранятся в открытом виде.

## Возможности бота

*   **Персональный API-ключ:** Работает с вашим личным ключом Google AI, обеспечивая приватность и контроль над использованием API.
*   **Безопасное хранение:** API-ключи пользователей надежно шифруются перед сохранением в базу данных.
*   **Интеллектуальное общение:** Ответы на вопросы и генерация текста на основе модели Google Gemini.
*   **Анализ изображений:** Распознавание и описание содержимого изображений, предоставление справочной информации об объектах на фото.
*   **Перевод текста:** Встроенная функция перевода текста на различные языки.
*   **История диалога:** Просмотр истории вашей переписки с ботом за любую выбранную дату.
*   **Личный кабинет:** Просмотр статистики, текущих настроек и статуса вашего API-ключа.
*   **Гибкие настройки:**
    *   **Смена языка:** Интерфейс бота поддерживает русский и английский языки.
    *   **Стиль общения:** Возможность выбрать один из нескольких стилей ответов бота (например, официальный, краткий, подробный).

## Технологии

*   **Python 3.10+:** Основной язык программирования.
*   **pyTelegramBotAPI (async):** Асинхронная библиотека для работы с Telegram Bot API.
*   **aiohttp:** Для выполнения прямых, неблокирующих HTTP-запросов к Gemini API.
*   **Cryptography:** Для надежного шифрования API-ключей пользователей.
*   **python-dotenv:** Для управления конфигурацией через `.env` файлы.
*   **PyYAML:** Для конфигурации системы логирования.
*   **sqlite3:** Встроенная база данных SQLite для хранения пользовательских данных и истории сообщений.
*   **Pillow:** Для обработки изображений перед отправкой в API.

## Настройка и запуск

### Предварительные требования

*   **Python 3.10 или выше.**
*   **pip:** Менеджер пакетов Python.

### Шаги по установке

1.  **Клонируйте репозиторий:**
    ```bash
    git clone [https://github.com/kobaltgit/MyGemini]
    cd MyGemini
    ```

2.  **Создайте и активируйте виртуальное окружение (рекомендуется):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # для Linux/macOS
    # или
    venv\Scripts\activate  # для Windows
    ```

3.  **Установите зависимости проекта:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Сгенерируйте ключ шифрования:**
    Создайте временный файл `generate_key.py` и выполните его для получения секретного ключа:
    ```python
    # File: generate_key.py
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    print(f"ENCRYPTION_KEY={key.decode()}")
    ```
    ```bash
    python generate_key.py
    ```
    Скопируйте полученную строку (`ENCRYPTION_KEY=...`). После этого файл `generate_key.py` можно удалить.

5.  **Настройте переменные окружения:**
    Создайте файл `.env` в корневой директории проекта и добавьте в него следующие переменные:

    ```env
    # Токен вашего Telegram-бота от @BotFather
    BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11

    # Ваш Telegram User ID для админских уведомлений (опционально)
    ADMIN_USER_ID=123456789

    # Ключ шифрования, который вы сгенерировали на предыдущем шаге
    ENCRYPTION_KEY=..._ваша_сгенерированная_строка_...

    # Модель Gemini, которую будет использовать бот (опционально)
    GEMINI_MODEL_NAME=gemini-1.5-flash-latest
    ```

### Запуск бота

Запустите бота, выполнив следующую команду в терминале:

```bash
python main.py
```

После запуска бот готов к работе. Найдите его в Telegram и отправьте команду /start.

## Первое использование
1. При первом запуске бот попросит вас установить API-ключ.
2. Используйте команду `/set_api_key`.
3. Отправьте боту ваш API-ключ от [Google AI Studio](https://makersuite.google.com/app/apikey).
4. После успешной установки ключа вы сможете полноценно пользоваться ботом.

## Структура директорий
```
MyGemini/
├── .env                  # Файл с переменными окружения (создается вручную)
├── logger_config.py      # Конфигурация логирования
├── main.py               # Основной файл запуска бота
├── requirements.txt      # Список зависимостей проекта
├── config/
│   ├── logging.yaml
│   └── settings.py
├── database/
│   ├── db_manager.py
│   └── bot_database.db   # Создается автоматически
├── features/
│   └── personal_account.py
├── handlers/
│   ├── callback_handlers.py
│   ├── command_handlers.py
│   └── message_handlers.py
├── logs/                 # Директория для логов (создается автоматически)
├── services/
│   └── gemini_service.py
└── utils/
    ├── analysis_helpers.py
    ├── crypto_helpers.py
    ├── localization.py
    └── markup_helpers.py
```

## Система логирования 
огирование настроено через файл `config/logging.yaml`. Логи разделены по файлам и сохраняются в директорию `logs/`:

*   **bot_general.log** - общие логи работы приложения.
*   **database.log** - логи, связанные с операциями базы данных.
*   **gemini_api.log** - логи запросов к Gemini API.
*   **user_messages.log** - логи входящих сообщений от пользователей.
## Лицензия
* Этот проект лицензирован по лицензии MIT.
## Поддержка и обратная связь
Если у вас есть вопросы, предложения или вы обнаружили ошибки, пожалуйста, создайте issue в репозитории GitHub или свяжитесь со мной [kobaltmail@gmail.com].
## Удачи в использовании бота!
