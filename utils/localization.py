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
                         "*/translate* - Перевести текст на другой язык.\n"
                         "*/usage* - Посмотреть статистику использования токенов за сегодня и за месяц.", # <-- НОВЫЙ ПУНКТ
        # --- Настройки ---
        'settings_title': "⚙️ *Настройки бота*",
        'settings_style_section': "--- Стиль общения бота ---",
        'settings_language_section': "--- Язык интерфейса ---",
        'settings_api_key_section': "--- Управление API ключом ---",
        'settings_btn_set_api_key': "🔑 Установить/обновить API ключ",
        'settings_model_section': "--- Нейросетевая модель ---",
        'settings_btn_choose_model': "🧠 Выбрать модель",
        'style_changed_notice': "Стиль общения изменен. Контекст диалога сброшен.",
        # --- Выбор модели ---
        'model_selection_title': "🧠 *Выбор модели Gemini*",
        'model_selection_loading': "⏳ Загружаю список доступных моделей...",
        'model_selection_error': "❌ Не удалось загрузить список моделей. Проверьте ваш API ключ или попробуйте позже.",
        'model_changed_notice': "✅ Модель изменена на *{model_name}*. Контекст диалога сброшен.",
        'btn_back_to_settings': "⬅️ Назад в настройки",
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
        # --- НОВОЕ: Статистика расходов ---
        'usage_title': "📊 *Статистика расходов токенов*",
        'usage_today_header': "*За сегодня:*",
        'usage_month_header': "*За текущий месяц:*",
        'usage_prompt_tokens': "📥 Входящие (prompt)",
        'usage_completion_tokens': "📤 Исходящие (completion)",
        'usage_total_tokens': "∑ Всего",
        'usage_estimated_cost': "💰 Примерная стоимость",
        'usage_no_data': "Нет данных для отображения.",
        'usage_cost_notice': "\n_Стоимость является приблизительной и рассчитывается на основе текущей модели и публичных тарифов Google._",
        # --- Ошибки ---
        'unsupported_content': "Я пока не умею обрабатывать такой тип контента.",
        'state_wrong_content_type': "Пожалуйста, отправьте текст для завершения текущего действия или нажмите /reset.",
        'translation_error_generic': "Не удалось выполнить перевод. Попробуйте еще раз.",
        # --- Ошибки Gemini API (понятные пользователю) ---
        'gemini_error_api_key_invalid': "🚫 *Ошибка: Неверный API-ключ.*\nПожалуйста, проверьте правильность вашего ключа и установите его заново с помощью /set_api_key.",
        'gemini_error_permission_denied': "🚫 *Ошибка: Доступ запрещен.*\nУбедитесь, что ваш API-ключ активирован и имеет необходимые разрешения в Google AI Studio.",
        'gemini_error_quota_exceeded': "⏳ *Ошибка: Превышена квота.*\nВы исчерпали лимит запросов к API. Попробуйте позже или проверьте лимиты в вашей учетной записи Google.",
        'gemini_error_safety': "censored:censored_black_rectangle: *Ответ заблокирован.*\nСгенерированный ответ был заблокирован настройками безопасности Google. Попробуйте переформулировать запрос.",
        'gemini_error_unavailable': "🛠️ *Сервис временно недоступен.*\nСерверы Google могут быть перегружены. Пожалуйста, повторите попытку через несколько минут.",
        'gemini_error_invalid_argument': "🤔 *Ошибка: Некорректный запрос.*\nВозможно, вы пытаетесь отправить контент, который не поддерживается выбранной моделью (например, видео).",
        'gemini_error_unknown': "🤯 *Произошла неизвестная ошибка при обращении к API.*\nПожалуйста, попробуйте еще раз. Если ошибка повторяется, свяжитесь с администратором.",
        # --- Кнопки ---
        'btn_translate': "🇷🇺 Перевести",
        'btn_history': "📜 История",
        'btn_account': "👤 Личный кабинет",
        'btn_settings': "⚙️ Настройки",
        'btn_help': "❓ Помощь",
        'btn_reset': "🔄 Сброс",
        'btn_usage': "📊 Расходы", # <-- НОВАЯ КНОПКА
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
                         "*/translate* - Translate text to another language.\n"
                         "*/usage* - View token usage statistics for today and this month.", # <-- NEW ITEM
        # --- Settings ---
        'settings_title': "⚙️ *Bot Settings*",
        'settings_style_section': "--- Bot Communication Style ---",
        'settings_language_section': "--- Interface Language ---",
        'settings_api_key_section': "--- API Key Management ---",
        'settings_btn_set_api_key': "🔑 Set/Update API Key",
        'settings_model_section': "--- Neural Network Model ---",
        'settings_btn_choose_model': "🧠 Choose Model",
        'style_changed_notice': "Communication style changed. The conversation context has been reset.",
        # --- Model Selection ---
        'model_selection_title': "🧠 *Gemini Model Selection*",
        'model_selection_loading': "⏳ Loading list of available models...",
        'model_selection_error': "❌ Could not load the model list. Please check your API key or try again later.",
        'model_changed_notice': "✅ Model changed to *{model_name}*. The conversation context has been reset.",
        'btn_back_to_settings': "⬅️ Back to Settings",
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
        # --- NEW: Usage Statistics ---
        'usage_title': "📊 *Token Usage Statistics*",
        'usage_today_header': "*For Today:*",
        'usage_month_header': "*For Current Month:*",
        'usage_prompt_tokens': "📥 Input (prompt)",
        'usage_completion_tokens': "📤 Output (completion)",
        'usage_total_tokens': "∑ Total",
        'usage_estimated_cost': "💰 Estimated Cost",
        'usage_no_data': "No data to display.",
        'usage_cost_notice': "\n_The cost is an estimate based on the current model and public Google tariffs._",
        # --- Errors ---
        'unsupported_content': "I don't know how to handle this type of content yet.",
        'state_wrong_content_type': "Please send text to complete the current action, or press /reset.",
        'translation_error_generic': "Failed to perform translation. Please try again.",
        # --- Gemini API Errors (User-Friendly) ---
        'gemini_error_api_key_invalid': "🚫 *Error: Invalid API Key.*\nPlease check if your key is correct and set it again using /set_api_key.",
        'gemini_error_permission_denied': "🚫 *Error: Permission Denied.*\nEnsure your API key is activated and has the necessary permissions in Google AI Studio.",
        'gemini_error_quota_exceeded': "⏳ *Error: Quota Exceeded.*\nYou have exhausted your API request limit. Please try again later or check your limits in your Google account.",
        'gemini_error_safety': "censored:censored_black_rectangle: *Response Blocked.*\nThe generated response was blocked by Google's safety settings. Please try rephrasing your request.",
        'gemini_error_unavailable': "🛠️ *Service Temporarily Unavailable.*\nGoogle's servers might be overloaded. Please try again in a few minutes.",
        'gemini_error_invalid_argument': "🤔 *Error: Invalid Request.*\nYou might be trying to send content that is not supported by the selected model (e.g., a video).",
        'gemini_error_unknown': "🤯 *An unknown error occurred while contacting the API.*\nPlease try again. If the error persists, contact the administrator.",
        # --- Buttons ---
        'btn_translate': "🇬🇧 Translate",
        'btn_history': "📜 History",
        'btn_account': "👤 My Account",
        'btn_settings': "⚙️ Settings",
        'btn_help': "❓ Help",
        'btn_reset': "🔄 Reset",
        'btn_usage': "📊 Usage", # <-- NEW BUTTON
    }
}

DEFAULT_LANG = 'ru'


def get_text(key: str, lang_code: str) -> str:
    """
    Возвращает текст по ключу для указанного языка.
    Если ключ или язык не найден, возвращает ключ в виде строки.
    """
    lang_dict = LOCALIZATION.get(lang_code)
    if lang_dict is None:
        lang_dict = LOCALIZATION.get(DEFAULT_LANG, {})
    return lang_dict.get(key, key)
