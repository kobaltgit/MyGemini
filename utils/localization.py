# File: utils/localization.py
from typing import Dict

# Словарь со всеми текстами. Ключ - язык, значение - словарь с текстами.
LOCALIZATION: Dict[str, Dict[str, str]] = {
    'ru': {
        # --- Приветствие и Помощь ---
        'welcome': "👋 Привет, *{name}*! Я твой личный ассистент на базе Gemini.\n\n"
           "Для начала работы мне понадобится твой Google AI API ключ. "
           "Если ты не знаешь, что это и как его получить, воспользуйся новой подробной командой: /apikey_info\n\n"
           "✅ После установки ключа через /set_api_key ты сможешь полноценно общаться со мной.\n\n"
           "Используй /help_guide, чтобы увидеть полный список моих возможностей.",
        'cmd_help_text': "🆘 *Краткая справка по командам*\n\n"
                 "*/start* - Перезапустить бота.\n"
                 "*/reset* - Сбросить контекст текущего диалога.\n"
                 "*/set_api_key* - Установить или обновить API ключ.\n"
                 "*/settings* - Открыть меню настроек.\n"
                 "*/dialogs* - Управление диалогами.\n"
                 "*/history* - Посмотреть историю сообщений.\n"
                 "*/usage* - Статистика расходов токенов.\n\n"
                 "➡️ Используй /help_guide для получения **полного руководства** по всем функциям.\n"
                 "🔑 Используй /apikey_info для получения инструкции по **созданию API ключа**.",
        # --- Настройки ---
        'settings_title': "⚙️ *Настройки бота*",
        'settings_style_section': "--- Стиль общения бота ---",
        'settings_language_section': "--- Язык интерфейса ---",
        'settings_api_key_section': "--- Управление API ключом ---",
        'settings_btn_set_api_key': "🔑 Установить/обновить API ключ",
        'settings_model_section': "--- Нейросетевая модель ---",
        'settings_btn_choose_model': "🧠 Выбрать модель",
        'settings_persona_section': "--- Роль ассистента (Персона) ---",
        'settings_btn_choose_persona': "🎭 Выбрать персону",
        'style_changed_notice': "Стиль общения изменен. Контекст диалога сброшен.",
        'persona_changed_notice': "✅ Персона изменена на *{persona_name}*. Контекст диалога сброшен.",
        # --- Выбор модели ---
        'model_selection_title': "🧠 *Выбор модели Gemini*",
        'model_selection_loading': "⏳ Загружаю список доступных моделей...",
        'model_selection_error': "❌ Не удалось загрузить список моделей. Проверьте ваш API ключ или попробуйте позже.",
        'model_changed_notice': "✅ Модель изменена на *{model_name}*. Контекст диалога сброшен.",
        'btn_back_to_settings': "⬅️ Назад в настройки",
        # --- Выбор персоны ---
        'persona_selection_title': "🎭 *Выбор персоны ассистента*",
        'persona_selection_desc': "Выберите роль, которую бот будет отыгрывать. Это изменит его стиль общения и экспертизу. Текущие *стили* (краткий, подробный и т.д.) будут игнорироваться.",
        # --- НОВОЕ: Управление диалогами ---
        'dialogs_menu_title': "🗂️ *Управление диалогами*",
        'dialogs_menu_desc': "Здесь вы можете создавать новые диалоги, переключаться между ними, переименовывать и удалять. Активный диалог отмечен ✅.",
        'btn_create_dialog': "➕ Создать новый",
        'btn_rename_dialog': "✏️ Переименовать",
        'btn_delete_dialog': "❌ Удалить",
        'btn_back_to_main_menu': "⬅️ Главное меню",
        'dialog_enter_new_name_prompt': "Введите название для нового диалога:",
        'dialog_created_success': "✅ Диалог *{name}* создан и установлен как активный. Контекст сброшен.",
        'dialog_switched_success': "✅ Активный диалог изменен на *{name}*. Контекст восстановлен.",
        'dialog_deleted_success': "🗑️ Диалог *{name}* удален. Активным установлен другой диалог.",
        'dialog_deleted_last_success': "🗑️ Диалог *{name}* удален. Создан новый 'Основной диалог' и сделан активным.",
        'dialog_enter_rename_prompt': "Введите новое название для диалога *{name}*:",
        'dialog_renamed_success': "✅ Диалог переименован в *{new_name}*.",
        'dialog_delete_confirmation': "Вы уверены, что хотите удалить диалог *{name}*? Это действие необратимо.",
        'btn_confirm_delete': "Да, удалить",
        'btn_cancel_delete': "Нет, отмена",
        'dialog_name_too_long': "Название диалога слишком длинное. Пожалуйста, введите название до 50 символов.",
        'dialog_name_invalid': "Название диалога не может быть пустым.",
        'dialog_error_delete_active': "Нельзя удалить активный диалог. Сначала переключитесь на другой.",
        # --- Команды и Состояния ---
        'cmd_reset_success': "✅ Контекст текущего диалога сброшен.",
        'set_api_key_prompt': "Пожалуйста, отправьте ваш Google AI API ключ. Сообщение с ключом будет удалено.",
        'history_prompt': "🗓️ Пожалуйста, выберите дату для просмотра истории текущего диалога:",
        'translate_prompt': "Выберите язык, на который нужно перевести текст:",
        'language_selected_notice': "Язык выбран: {lang_name}.",
        'send_text_to_translate_prompt': "Теперь отправьте мне текст, который нужно перевести на {lang_name}.",
        # --- Обработка API ключа ---
        'api_key_verifying': "Проверяю ключ...",
        'api_key_success': "✅ Ключ успешно установлен и зашифрован! Теперь вы можете общаться со мной.",
        'api_key_invalid': "❌ Этот ключ недействителен. Пожалуйста, проверьте его и попробуйте снова.",
        'api_key_needed_for_chat': "Для общения со мной нужен API ключ. Пожалуйста, установите его с помощью команды /set_api_key.",
        'api_key_needed_for_vision': "Для анализа изображений нужен API ключ. Пожалуйста, установите его с помощью команды /set_api_key.",
        'api_key_needed_for_feature': "Для использования этой функции нужен API ключ. Пожалуйста, установите его через /set_api_key.",
        # --- История ---
        'history_loading': "Загружаю историю...",
        'history_for_date': "История за",
        'history_role_user': "Вы",
        'history_role_bot': "Бот",
        'history_no_messages': "В этот день в данном диалоге сообщений не найдено.",
        'history_date_error': "Произошла ошибка при обработке даты. Попробуйте еще раз.",
        # --- Статистика расходов ---
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
        'btn_dialogs': "🗂️ Диалоги", # НОВАЯ КНОПКА
        'btn_translate': "🇷🇺 Перевести",
        'btn_history': "📜 История",
        'btn_account': "👤 Личный кабинет",
        'btn_settings': "⚙️ Настройки",
        'btn_help': "❓ Помощь",
        'btn_reset': "🔄 Сброс",
        'btn_usage': "📊 Расходы",
    },
    'en': {
        # --- Welcome and Help ---
        'welcome': "👋 Hi, *{name}*! I'm your personal assistant powered by Gemini.\n\n"
           "To get started, I'll need your Google AI API key. "
           "If you don't know what it is or how to get it, use the new detailed command: /apikey_info\n\n"
           "✅ After setting the key via /set_api_key, you'll be able to chat with me.\n\n"
           "Use /help_guide to see a full list of my features.",
        'cmd_help_text': "🆘 *Quick Command Reference*\n\n"
                 "*/start* - Restart the bot.\n"
                 "*/reset* - Clear the current dialog context.\n"
                 "*/set_api_key* - Set or update your API key.\n"
                 "*/settings* - Open the settings menu.\n"
                 "*/dialogs* - Manage your dialogs.\n"
                 "*/history* - View message history.\n"
                 "*/usage* - Token usage statistics.\n\n"
                 "➡️ Use /help_guide for the **full user manual**.\n"
                 "🔑 Use /apikey_info for instructions on **creating an API key**.",
        # --- Settings ---
        'settings_title': "⚙️ *Bot Settings*",
        'settings_style_section': "--- Bot Communication Style ---",
        'settings_language_section': "--- Interface Language ---",
        'settings_api_key_section': "--- API Key Management ---",
        'settings_btn_set_api_key': "🔑 Set/Update API Key",
        'settings_model_section': "--- Neural Network Model ---",
        'settings_btn_choose_model': "🧠 Choose Model",
        'settings_persona_section': "--- Assistant's Role (Persona) ---",
        'settings_btn_choose_persona': "🎭 Choose Persona",
        'style_changed_notice': "Communication style changed. The conversation context has been reset.",
        'persona_changed_notice': "✅ Persona changed to *{persona_name}*. The conversation context has been reset.",
        # --- Model Selection ---
        'model_selection_title': "🧠 *Gemini Model Selection*",
        'model_selection_loading': "⏳ Loading list of available models...",
        'model_selection_error': "❌ Could not load the model list. Please check your API key or try again later.",
        'model_changed_notice': "✅ Model changed to *{model_name}*. The conversation context has been reset.",
        'btn_back_to_settings': "⬅️ Back to Settings",
        # --- Persona Selection ---
        'persona_selection_title': "🎭 *Assistant Persona Selection*",
        'persona_selection_desc': "Choose a role for the bot to play. This will change its communication style and expertise. Current *styles* (concise, detailed, etc.) will be ignored.",
        # --- NEW: Dialog Management ---
        'dialogs_menu_title': "🗂️ *Dialog Management*",
        'dialogs_menu_desc': "Here you can create new dialogs, switch between them, rename, and delete. The active dialog is marked with ✅.",
        'btn_create_dialog': "➕ Create New",
        'btn_rename_dialog': "✏️ Rename",
        'btn_delete_dialog': "❌ Delete",
        'btn_back_to_main_menu': "⬅️ Main Menu",
        'dialog_enter_new_name_prompt': "Enter a name for the new dialog:",
        'dialog_created_success': "✅ Dialog *{name}* created and set as active. Context has been reset.",
        'dialog_switched_success': "✅ Active dialog changed to *{name}*. Context has been restored.",
        'dialog_deleted_success': "🗑️ Dialog *{name}* has been deleted. Another dialog has been set as active.",
        'dialog_deleted_last_success': "🗑️ Dialog *{name}* has been deleted. A new 'General Chat' has been created and made active.",
        'dialog_enter_rename_prompt': "Enter a new name for the dialog *{name}*:",
        'dialog_renamed_success': "✅ Dialog renamed to *{new_name}*.",
        'dialog_delete_confirmation': "Are you sure you want to delete the dialog *{name}*? This action cannot be undone.",
        'btn_confirm_delete': "Yes, delete",
        'btn_cancel_delete': "No, cancel",
        'dialog_name_too_long': "The dialog name is too long. Please enter a name up to 50 characters.",
        'dialog_name_invalid': "The dialog name cannot be empty.",
        'dialog_error_delete_active': "You cannot delete the active dialog. Switch to another one first.",
        # --- Commands and States ---
        'cmd_reset_success': "✅ The context of the current dialog has been reset.",
        'set_api_key_prompt': "Please send your Google AI API key. The message with the key will be deleted.",
        'history_prompt': "🗓️ Please select a date to view the history of the current dialog:",
        'translate_prompt': "Select the language to translate the text into:",
        'language_selected_notice': "Language selected: {lang_name}.",
        'send_text_to_translate_prompt': "Now send me the text to be translated into {lang_name}.",
        # --- API Key Handling ---
        'api_key_verifying': "Verifying key...",
        'api_key_success': "✅ Key successfully set and encrypted! You can now chat with me.",
        'api_key_invalid': "❌ This key is invalid. Please check it and try again.",
        'api_key_needed_for_chat': "To chat with me, an API key is required. Please set it using the /set_api_key command.",
        'api_key_needed_for_vision': "To analyze images, an API key is required. Please set it using the /set_api_key command.",
        'api_key_needed_for_feature': "To use this feature, an API key is required. Please set it via /set_api_key.",
        # --- History ---
        'history_loading': "Loading history...",
        'history_for_date': "History for",
        'history_role_user': "You",
        'history_role_bot': "Bot",
        'history_no_messages': "No messages found on this day in this dialog.",
        'history_date_error': "An error occurred while processing the date. Please try again.",
        # --- Usage Statistics ---
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
        'gemini_error_api_key_invalid': "🚫 *Error: Invalid API Key.*\nPlease check your key and set it again using /set_api_key.",
        'gemini_error_permission_denied': "🚫 *Error: Permission Denied.*\nEnsure your API key is activated and has permissions in Google AI Studio.",
        'gemini_error_quota_exceeded': "⏳ *Error: Quota Exceeded.*\nYou have exhausted your API request limit. Try again later or check your Google account limits.",
        'gemini_error_safety': "censored:censored_black_rectangle: *Response Blocked.*\nThe generated response was blocked by Google's safety settings. Try rephrasing your request.",
        'gemini_error_unavailable': "🛠️ *Service Temporarily Unavailable.*\nGoogle's servers might be overloaded. Please try again in a few minutes.",
        'gemini_error_invalid_argument': "🤔 *Error: Invalid Request.*\nYou might be trying to send content not supported by the model (e.g., a video).",
        'gemini_error_unknown': "🤯 *An unknown API error occurred.*\nPlease try again. If the error persists, contact the administrator.",
        # --- Buttons ---
        'btn_dialogs': "🗂️ Dialogs", # NEW BUTTON
        'btn_translate': "🇬🇧 Translate",
        'btn_history': "📜 History",
        'btn_account': "👤 My Account",
        'btn_settings': "⚙️ Settings",
        'btn_help': "❓ Help",
        'btn_reset': "🔄 Reset",
        'btn_usage': "📊 Usage",
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
