# File: utils/localization.py
from typing import Dict

# Словарь со всеми текстами. Ключ - язык, значение - словарь с текстами.
LOCALIZATION: Dict[str, Dict[str, str]] = {
    'ru': {
        # --- Приветствие и Помощь ---
        'welcome': "👋 Привет, *{name}*! Я твой личный ассистент на базе Gemini.\n\n"
                   "Для работы мне понадобится твой Google AI API ключ. "
                   "Пожалуйста, установи его с помощью команды /set_api_key.\n\n"
                   "После этого ты сможешь:\n"
                   "🧠 Отвечать на вопросы и генерировать тексты.\n"
                   "🖼️ Анализировать изображения (просто отправь картинку).\n"
                   "🇷🇺 Переводить текст (кнопка 'Перевести').\n"
                   "📜 Смотреть историю диалога (кнопка 'История').\n\n"
                   "Используй /help для получения справки.",
        'cmd_help_text': "🆘 *Справка по боту*\n\n"
                         "*/start* - Перезапустить бота и сбросить контекст.\n"
                         "*/reset* - Сбросить контекст текущего диалога, не меняя настроек.\n"
                         "*/set_api_key* (или */setapikey*) - Установить или обновить ваш API ключ от Google AI.\n"
                         "*/settings* - Открыть меню настроек (стиль общения, язык, API ключ).\n"
                         "*/history* - Посмотреть историю сообщений за определенную дату.\n"
                         "*/translate* - Перевести текст на другой язык.\n\n"
                         "Вы также можете использовать кнопки внизу для быстрого доступа к этим функциям.",
        # --- Настройки ---
        'settings_title': "⚙️ *Настройки бота*",
        'settings_style_section': "--- Стиль общения бота ---",
        'settings_language_section': "--- Язык интерфейса ---",
        'settings_api_key_section': "--- Управление API ключом ---",
        'settings_btn_set_api_key': "🔑 Установить/обновить API ключ",
        'settings_model_section': "--- Нейросетевая модель ---", # <-- НОВАЯ СТРОКА
        'settings_btn_choose_model': "🧠 Выбрать модель", # <-- НОВАЯ СТРОКА
        'style_changed_notice': "Стиль общения изменен. Контекст диалога сброшен.",
        # --- Выбор модели ---
        'model_selection_title': "🧠 *Выбор модели Gemini*", # <-- НОВАЯ СТРОКА
        'model_selection_loading': "⏳ Загружаю список доступных моделей...", # <-- НОВАЯ СТРОКА
        'model_selection_error': "❌ Не удалось загрузить список моделей. Проверьте ваш API ключ или попробуйте позже.", # <-- НОВАЯ СТРОКА
        'model_changed_notice': "✅ Модель изменена на *{model_name}*. Контекст диалога сброшен.", # <-- НОВАЯ СТРОКА
        'btn_back_to_settings': "⬅️ Назад в настройки", # <-- НОВАЯ СТРОКА
        # --- Команды и Состояния ---
        'cmd_reset_success': "✅ Контекст разговора и ваше текущее состояние сброшены.",
        'set_api_key_prompt': "Пожалуйста, отправьте ваш Google AI API ключ. Сообщение с ключом будет удалено.",
        'history_prompt': "🗓️ Пожалуйста, выберите дату для просмотра истории:",
        'translate_prompt': "Выберите язык, на который нужно перевести текст:",
        'language_selected_notice': "Язык выбран: {lang_name}.",
        'send_text_to_translate_prompt': "Теперь отправьте мне текст, который нужно перевести на {lang_name}.",
        # --- Обработка API ключа ---
        'api_key_verifying': "Проверяю ключ...",
        'api_key_success': "✅ Ключ успешно установлен и зашифрован! Теперь вы можете общаться со мной.",
        'api_key_invalid': "❌ Этот ключ недействителен. Пожалуйста, проверьте его и попробуйте снова. Вы можете отправить другой ключ прямо сейчас или вызвать /set_api_key позже.",
        'api_key_needed_for_chat': "Для общения со мной нужен API ключ. Пожалуйста, установите его с помощью команды /set_api_key.",
        'api_key_needed_for_vision': "Для анализа изображений нужен API ключ. Пожалуйста, установите его с помощью команды /set_api_key.",
        'api_key_needed_for_feature': "Для использования этой функции нужен API ключ. Пожалуйста, установите его через /set_api_key.",
        # --- История ---
        'history_loading': "Загружаю историю...",
        'history_for_date': "История за",
        'history_role_user': "Вы",
        'history_role_bot': "Бот",
        'history_no_messages': "В этот день сообщений не найдено.",
        'history_date_error': "Произошла ошибка при обработке даты. Попробуйте еще раз.",
        # --- Ошибки и уведомления ---
        'unsupported_content': "Я пока не умею обрабатывать такой тип контента.",
        'state_wrong_content_type': "Пожалуйста, отправьте текст для завершения текущего действия или нажмите /reset.",
        'gemini_error_response': "К сожалению, не удалось обработать ваш запрос. Пожалуйста, попробуйте переформулировать его или повторите попытку позже.",
        'translation_error_generic': "Не удалось выполнить перевод. Попробуйте еще раз.",
        # --- Кнопки ---
        'btn_translate': "🇷🇺 Перевести",
        'btn_history': "📜 История",
        'btn_account': "👤 Личный кабинет",
        'btn_settings': "⚙️ Настройки",
        'btn_help': "❓ Помощь",
        'btn_reset': "🔄 Сброс",
    },
    'en': {
        # --- Welcome and Help ---
        'welcome': "👋 Hi, *{name}*! I'm your personal assistant powered by Gemini.\n\n"
                   "To get started, I'll need your Google AI API key. "
                   "Please set it using the /set_api_key command.\n\n"
                   "After that, you'll be able to:\n"
                   "🧠 Answer questions and generate text.\n"
                   "🖼️ Analyze images (just send a picture).\n"
                   "🇬🇧 Translate text (the 'Translate' button).\n"
                   "📜 View conversation history (the 'History' button).\n\n"
                   "Use /help to get assistance.",
        'cmd_help_text': "🆘 *Bot Help*\n\n"
                         "*/start* - Restart the bot and clear the context.\n"
                         "*/reset* - Clear the context of the current conversation without changing settings.\n"
                         "*/set_api_key* (or */setapikey*) - Set or update your Google AI API key.\n"
                         "*/settings* - Open the settings menu (communication style, language, API key).\n"
                         "*/history* - View message history for a specific date.\n"
                         "*/translate* - Translate text to another language.\n\n"
                         "You can also use the buttons below for quick access to these functions.",
        # --- Settings ---
        'settings_title': "⚙️ *Bot Settings*",
        'settings_style_section': "--- Bot Communication Style ---",
        'settings_language_section': "--- Interface Language ---",
        'settings_api_key_section': "--- API Key Management ---",
        'settings_btn_set_api_key': "🔑 Set/Update API Key",
        'settings_model_section': "--- Neural Network Model ---", # <-- НОВАЯ СТРОКА
        'settings_btn_choose_model': "🧠 Choose Model", # <-- НОВАЯ СТРОКА
        'style_changed_notice': "Communication style changed. The conversation context has been reset.",
        # --- Model Selection ---
        'model_selection_title': "🧠 *Gemini Model Selection*", # <-- НОВАЯ СТРОКА
        'model_selection_loading': "⏳ Loading list of available models...", # <-- НОВАЯ СТРОКА
        'model_selection_error': "❌ Could not load the model list. Please check your API key or try again later.", # <-- НОВАЯ СТРОКА
        'model_changed_notice': "✅ Model changed to *{model_name}*. The conversation context has been reset.", # <-- НОВАЯ СТРОКА
        'btn_back_to_settings': "⬅️ Back to Settings", # <-- НОВАЯ СТРОКА
        # --- Commands and States ---
        'cmd_reset_success': "✅ The conversation context and your current state have been reset.",
        'set_api_key_prompt': "Please send your Google AI API key. The message with the key will be deleted.",
        'history_prompt': "🗓️ Please select a date to view the history:",
        'translate_prompt': "Select the language to translate the text into:",
        'language_selected_notice': "Language selected: {lang_name}.",
        'send_text_to_translate_prompt': "Now send me the text to be translated into {lang_name}.",
        # --- API Key Handling ---
        'api_key_verifying': "Verifying key...",
        'api_key_success': "✅ Key successfully set and encrypted! You can now chat with me.",
        'api_key_invalid': "❌ This key is invalid. Please check it and try again. You can send another key right now or call /set_api_key later.",
        'api_key_needed_for_chat': "To chat with me, an API key is required. Please set it using the /set_api_key command.",
        'api_key_needed_for_vision': "To analyze images, an API key is required. Please set it using the /set_api_key command.",
        'api_key_needed_for_feature': "To use this feature, an API key is required. Please set it via /set_api_key.",
        # --- History ---
        'history_loading': "Loading history...",
        'history_for_date': "History for",
        'history_role_user': "You",
        'history_role_bot': "Bot",
        'history_no_messages': "No messages found on this day.",
        'history_date_error': "An error occurred while processing the date. Please try again.",
        # --- Errors and Notifications ---
        'unsupported_content': "I don't know how to handle this type of content yet.",
        'state_wrong_content_type': "Please send text to complete the current action, or press /reset.",
        'gemini_error_response': "Sorry, your request could not be processed. Please try to rephrase it or try again later.",
        'translation_error_generic': "Failed to perform translation. Please try again.",
        # --- Buttons ---
        'btn_translate': "🇬🇧 Translate",
        'btn_history': "📜 History",
        'btn_account': "👤 My Account",
        'btn_settings': "⚙️ Settings",
        'btn_help': "❓ Help",
        'btn_reset': "🔄 Reset",
    }
}

DEFAULT_LANG = 'ru'


def get_text(key: str, lang_code: str) -> str:
    """
    Возвращает текст по ключу для указанного языка.
    Если ключ или язык не найден, возвращает ключ в виде строки.
    """
    # Сначала пытаемся получить словарь для нужного языка
    lang_dict = LOCALIZATION.get(lang_code)
    # Если его нет, берем словарь для языка по умолчанию
    if lang_dict is None:
        lang_dict = LOCALIZATION.get(DEFAULT_LANG, {})
    # Возвращаем текст по ключу. Если его нет, возвращаем сам ключ,
    # чтобы было легче отлаживать недостающие переводы.
    return lang_dict.get(key, key)
