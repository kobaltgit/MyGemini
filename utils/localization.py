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
        'cmd_help_text': (
            "🆘 <b>Краткая справка по командам:</b>\n\n"
            "• <code>/start</code> — Перезапустить бота\n"
            "• <code>/reset</code> — Сбросить контекст диалога\n"
            "• <code>/set_api_key</code> — Установить/обновить API-ключ\n"
            "• <code>/settings</code> — Меню настроек\n"
            "• <code>/dialogs</code> — Управление диалогами\n"
            "• <code>/history</code> — История сообщений по календарю\n"
            "• <code>/usage</code> — Статистика расходов токенов\n"
            "• <code>/translate</code> — Быстрый переводчик\n"
            "• <code>/account</code> — Личный кабинет\n\n"
            "➡️ <code>/help_guide</code> — <b>Полное руководство</b> по всем возможностям\n"
            "🔑 <code>/apikey_info</code> — Инструкция по созданию <b>API-ключа</b>"
        ),
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
        # --- Управление диалогами ---
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
        # --- Обратная связь ---
        'feedback_prompt': "Пожалуйста, скопируйте текст ошибки и вставьте в сообщение, опишите проблему или ваше предложение. Это сообщение будет отправлено администратору.",
        'feedback_sent': "✅ Спасибо! Ваше сообщение отправлено администратору.",

        'feedback_admin_notification': "⚠️ *Новое сообщение от пользователя\\!*\n\n*От:* `{user_id}` \\(@{username}\\)\n*Имя:* {first_name}\n\n*Сообщение:*\n{text}\n\n*Для ответа используйте команду:* `/reply {user_id}`",

        # --- Поддержка ---
        'support_prompt': "Если вам нравится бот и вы хотите поддержать его развитие, вы можете сделать небольшой донат:",
        # --- Ошибки ---
        'unsupported_content': "Я пока не умею обрабатывать такой тип контента.",
        'state_wrong_content_type': "Пожалуйста, отправьте текст для завершения текущего действия или нажмите /reset.",
        'translation_error_generic': "Не удалось выполнить перевод. Попробуйте еще раз.",
        # --- Ошибки Gemini API (понятные пользователю) ---
        'gemini_error_timeout': "⏳ *Сервер не ответил вовремя.*\nЭто может быть связано с большой нагрузкой на API Google или временными проблемами с сетью. Пожалуйста, повторите ваш запрос через несколько минут.",
        'gemini_error_api_key_invalid': "🚫 *Ошибка: Неверный API-ключ.*\nПожалуйста, проверьте правильность вашего ключа и установите его заново с помощью /set_api_key.",
        'gemini_error_permission_denied': "🚫 *Ошибка: Доступ запрещен.*\nУбедитесь, что ваш API-ключ активирован и имеет необходимые разрешения в Google AI Studio.",
        'gemini_error_quota_exceeded': "⏳ *Ошибка: Превышена квота.*\nВы исчерпали лимит запросов к API. Попробуйте позже или проверьте лимиты в вашей учетной записи Google.",
        'gemini_error_safety': "🛡️ *Ответ заблокирован фильтрами безопасности.*\nЗапрос или сгенерированный ответ был заблокирован политиками безопасности Google. Попробуйте переформулировать ваш вопрос.",
        'gemini_error_recitation': "📚 *Ответ заблокирован (авторские права).*\nОтвет содержит дословное цитирование защищенных авторским правом материалов и был скрыт Google. Попробуйте переформулировать вопрос.",
        'gemini_error_empty_response': "⚠️ *Модель вернула пустой ответ.*\nНейросеть не сформировала текстового ответа на этот запрос. Попробуйте повторить попытку или задать вопрос иначе.",
        'gemini_error_overloaded': "⏳ *Модель {model_name} сейчас перегружена.*\nНа серверах Google зафиксирован высокий спрос (High demand). Пожалуйста, подождите 1–2 минуты или выберите другую модель (например, gemini-2.5-flash) через /settings.",
        'gemini_error_model_deprecated': "🚫 *Модель {model_name} недоступна.*\nЭта модель устарела или отключена в Google API. Пожалуйста, выберите актуальную рабочую модель через /settings -> 'Выбрать модель'.",
        'gemini_error_unavailable': "🛠️ *Сервис временно недоступен.*\nСерверы Google могут быть перегружены. Пожалуйста, повторите попытку через несколько минут или смените модель через /settings.",
        'gemini_error_search_not_supported': "🔍 *Поиск Google не поддерживается моделью {model_name}.*\nПожалуйста, выберите модель с поддержкой поиска (например, gemini-2.5-flash) через /settings.",
        'gemini_error_invalid_argument': "🤔 *Ошибка: Некорректный запрос.*\nВозможно, отправлен неподдерживаемый формат контента или недопустимые параметры.",
        'gemini_error_unknown': "🤯 *Произошла ошибка при обращении к API.*\nПожалуйста, попробуйте еще раз. Если ошибка повторяется, попробуйте сменить модель в /settings или свяжитесь с администратором.",
        'user_is_blocked': "❌ Вы были заблокированы администратором.",
        'maintenance_mode_on': "🛠️ Бот временно находится на техническом обслуживании. Пожалуйста, попробуйте позже.",
        # --- Кнопки ---
        'btn_dialogs': "🗂️ Диалоги",
        'btn_translate': "🇷🇺 Перевести",
        'btn_history': "📜 История",
        'btn_account': "👤 Личный кабинет",
        'btn_settings': "⚙️ Настройки",
        'btn_help': "❓ Помощь",
        'btn_reset': "🔄 Сброс",
        'btn_usage': "📊 Расходы",
        'btn_admin_panel': "👑 Админ-панель",
        'btn_support': "❤️ Поддержать автора",
        # --- Секция админа ---
        'admin': {
            'panel_title': "👑 *Админ-панель*",
            'not_admin': "❌ У вас нет прав для выполнения этой команды.",
            # Меню
            'btn_stats': "📊 Статистика",
            'btn_communication': "📬 Коммуникация",
            'btn_user_management': "👤 Управление пользователями",
            'btn_maintenance': "🛠️ Режим обслуживания",
            'btn_export_users': "📥 Выгрузить пользователей",
            'btn_back_to_admin_menu': "⬅️ Назад в админ-панель",
            # Режим обслуживания
            'maintenance_menu_title': "🛠️ *Режим обслуживания*",
            'maintenance_status_on': "🟢 *Статус:* ВКЛЮЧЕН",
            'maintenance_status_off': "🔴 *Статус:* ВЫКЛЮЧЕН",
            'btn_maintenance_enable': "Включить",
            'btn_maintenance_disable': "Выключить",
            'maintenance_enabled_msg': "✅ Режим обслуживания ВКЛЮЧЕН. Только администратор может использовать бота.",
            'maintenance_disabled_msg': "✅ Режим обслуживания ВЫКЛЮЧЕН. Бот доступен всем пользователям.",
            # Статистика
            'stats_title': "📊 *Глобальная статистика бота*",
            'stats_total_users': "👥 Всего пользователей:",
            'stats_active_users': "🏃 Активных за 7 дней:",
            'stats_new_users': "🌱 Новых за 7 дней:",
            'stats_blocked_users': "🚫 Заблокированных:",
            # Управление пользователями
            'user_management_title': "👤 *Управление пользователями*",
            'user_management_prompt': "Введите User ID для получения информации:",
            'user_info_title': "ℹ️ *Информация о пользователе*",
            'user_info_id': "ID:",
            'user_info_lang': "Язык:",
            'user_info_reg_date': "Дата регистрации:",
            'user_info_messages': "Сообщений:",
            'user_info_status': "Статус:",
            'user_status_active': "Активен",
            'user_status_blocked': "Заблокирован",
            'btn_block_user': "🚫 Заблокировать",
            'btn_unblock_user': "✅ Разблокировать",
            'btn_reset_user_api_key': "🔑 Сбросить API ключ",
            'user_not_found': "❌ Пользователь с ID `{user_id}` не найден.",
            'user_blocked_success': "✅ Пользователь `{user_id}` заблокирован.",
            'user_unblocked_success': "✅ Пользователь `{user_id}` разблокирован.",
            'user_api_key_reset_success': "✅ API ключ для пользователя `{user_id}` сброшен.",
            # Коммуникация
            'communication_title': "📬 *Коммуникация*",
            'btn_broadcast': "📢 Рассылка всем",
            'btn_reply_to_user': "✉️ Ответить пользователю",
            'reply_prompt_user_id': "Введите User ID пользователя, которому вы хотите отправить сообщение:",
            'reply_prompt_message': "Теперь введите сообщение для пользователя `{user_id}`:",
            'broadcast_prompt': "Отправьте сообщение, которое будет разослано всем пользователям. Для отмены введите /cancel.",
            'broadcast_confirm_prompt': "Вы собираетесь отправить следующее сообщение `{count}` пользователям. Вы уверены?\n\n---\n{message_text}\n---",
            'btn_confirm_broadcast': "Да, отправить",
            'btn_cancel_broadcast': "Отмена",
            'broadcast_started': "✅ Рассылка начата...",
            'broadcast_cancelled': "❌ Рассылка отменена.",
            'broadcast_finished': "✅ Рассылка завершена. Отправлено: {sent}. Не удалось: {failed}.",
            'reply_to_user_prompt': "Ответить пользователю `{user_id}`:",
            'reply_sent_success': "✅ Сообщение отправлено пользователю `{user_id}`.",
            'reply_sent_fail': "❌ Не удалось отправить сообщение. Возможно, пользователь заблокировал бота.",
            'reply_admin_notification': "✉️ *Сообщение от администратора:*\n\n`{text}`"
        }
    },
    'en': {
        # --- Welcome and Help ---
        'welcome': "👋 Hi, *{name}*! I'm your personal assistant powered by Gemini.\n\n"
           "To get started, I'll need your Google AI API key. "
           "If you don't know what it is or how to get it, use the new detailed command: /apikey_info\n\n"
           "✅ After setting the key via /set_api_key, you'll be able to chat with me.\n\n"
           "Use /help_guide to see a full list of my features.",
        'cmd_help_text': (
            "🆘 <b>Quick Command Reference:</b>\n\n"
            "• <code>/start</code> — Restart the bot\n"
            "• <code>/reset</code> — Clear dialogue context\n"
            "• <code>/set_api_key</code> — Set or update API key\n"
            "• <code>/settings</code> — Open settings menu\n"
            "• <code>/dialogs</code> — Manage dialogues\n"
            "• <code>/history</code> — View message history\n"
            "• <code>/usage</code> — Token usage & cost statistics\n"
            "• <code>/translate</code> — Built-in translator\n"
            "• <code>/account</code> — Personal account\n\n"
            "➡️ <code>/help_guide</code> — <b>Full user manual</b> with all features\n"
            "🔑 <code>/apikey_info</code> — Instructions on creating an <b>API key</b>"
        ),
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
        # --- Dialog Management ---
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
        # --- Feedback ---
        'feedback_prompt': "Please copy the error text and paste it into the message, then describe the problem or your suggestion. This message will be sent to the administrator.",
        'feedback_sent': "✅ Thank you! Your message has been sent to the administrator.",

        'feedback_admin_notification': "⚠️ *New message from a user\\!*\n\n*From:* `{user_id}` \\(@{username}\\)\n*Name:* {first_name}\n\n*Message:*\n{text}\n\n*To reply, use the command:* `/reply {user_id}`",
        
        # --- Support ---
        'support_prompt': "If you like the bot and wish to support its development, you can make a small donation:",
        # --- Errors ---
        'unsupported_content': "I don't know how to handle this type of content yet.",
        'state_wrong_content_type': "Please send text to complete the current action, or press /reset.",
        'translation_error_generic': "Failed to perform translation. Please try again.",
        # --- Gemini API Errors (User-Friendly) ---
        'gemini_error_timeout': "⏳ *Server did not respond in time.*\nThis might be due to a high load on the Google API or temporary network issues. Please try your request again in a few minutes.",
        'gemini_error_api_key_invalid': "🚫 *Error: Invalid API Key.*\nPlease check your key and set it again using /set_api_key.",
        'gemini_error_permission_denied': "🚫 *Error: Permission Denied.*\nEnsure your API key is activated and has permissions in Google AI Studio.",
        'gemini_error_quota_exceeded': "⏳ *Error: Quota Exceeded.*\nYou have exhausted your API request limit. Try again later or check your Google account limits.",
        'gemini_error_safety': "🛡️ *Response Blocked by Safety Filters.*\nThe request or generated response was blocked by Google's safety policies. Try rephrasing your question.",
        'gemini_error_recitation': "📚 *Response Blocked (Copyright).*\nThe response contains verbatim recitation of copyrighted material and was withheld by Google. Try rephrasing your question.",
        'gemini_error_empty_response': "⚠️ *Empty Response from Model.*\nThe model did not return any text for this request. Please try again or rephrase your prompt.",
        'gemini_error_overloaded': "⏳ *Model {model_name} is currently overloaded.*\nGoogle servers are experiencing high demand for this model. Please wait 1–2 minutes or switch to another model (e.g. gemini-2.5-flash) via /settings.",
        'gemini_error_model_deprecated': "🚫 *Model {model_name} is no longer available.*\nThis model is disabled or deprecated in the Google API. Please choose an active model via /settings -> 'Choose Model'.",
        'gemini_error_unavailable': "🛠️ *Service Temporarily Unavailable.*\nGoogle's servers might be overloaded. Please try again in a few minutes or switch models via /settings.",
        'gemini_error_search_not_supported': "🔍 *Google Search is not supported by {model_name}.*\nPlease select a supported model (e.g., gemini-2.5-flash) in /settings.",
        'gemini_error_invalid_argument': "🤔 *Error: Invalid Request.*\nAn unsupported content format or invalid parameters were provided.",
        'gemini_error_unknown': "🤯 *An unexpected API error occurred.*\nPlease try again. If the error persists, try switching models in /settings or contact the administrator.",
        'user_is_blocked': "❌ You have been blocked by the administrator.",
        'maintenance_mode_on': "🛠️ The bot is temporarily in maintenance mode. Please try again later.",
        # --- Buttons ---
        'btn_dialogs': "🗂️ Dialogs",
        'btn_translate': "🇬🇧 Translate",
        'btn_history': "📜 History",
        'btn_account': "👤 My Account",
        'btn_settings': "⚙️ Settings",
        'btn_help': "❓ Help",
        'btn_reset': "🔄 Reset",
        'btn_usage': "📊 Usage",
        'btn_admin_panel': "👑 Admin Panel",
        'btn_support': "❤️ Support the Author",
        # --- Admin Section ---
        'admin': {
            'panel_title': "👑 *Admin Panel*",
            'not_admin': "❌ You do not have permission to execute this command.",
            # Menu
            'btn_stats': "📊 Statistics",
            'btn_communication': "📬 Communication",
            'btn_user_management': "👤 User Management",
            'btn_maintenance': "🛠️ Maintenance Mode",
            'btn_export_users': "📥 Export Users",
            'btn_back_to_admin_menu': "⬅️ Back to Admin Panel",
            # Maintenance Mode
            'maintenance_menu_title': "🛠️ *Maintenance Mode*",
            'maintenance_status_on': "🟢 *Status:* ENABLED",
            'maintenance_status_off': "🔴 *Status:* DISABLED",
            'btn_maintenance_enable': "Enable",
            'btn_maintenance_disable': "Disable",
            'maintenance_enabled_msg': "✅ Maintenance mode is ENABLED. Only the admin can use the bot.",
            'maintenance_disabled_msg': "✅ Maintenance mode is DISABLED. The bot is available to all users.",
            # Statistics
            'stats_title': "📊 *Global Bot Statistics*",
            'stats_total_users': "👥 Total users:",
            'stats_active_users': "🏃 Active in last 7 days:",
            'stats_new_users': "🌱 New in last 7 days:",
            'stats_blocked_users': "🚫 Blocked users:",
            # User Management
            'user_management_title': "👤 *User Management*",
            'user_management_prompt': "Enter User ID for details:",
            'user_info_title': "ℹ️ *User Information*",
            'user_info_id': "ID:",
            'user_info_lang': "Language:",
            'user_info_reg_date': "Registration Date:",
            'user_info_messages': "Messages:",
            'user_info_status': "Status:",
            'user_status_active': "Active",
            'user_status_blocked': "Blocked",
            'btn_block_user': "🚫 Block",
            'btn_unblock_user': "✅ Unblock",
            'btn_reset_user_api_key': "🔑 Reset API Key",
            'user_not_found': "❌ User with ID `{user_id}` not found.",
            'user_blocked_success': "✅ User `{user_id}` has been blocked.",
            'user_unblocked_success': "✅ User `{user_id}` has been unblocked.",
            'user_api_key_reset_success': "✅ API key for user `{user_id}` has been reset.",
            # Communication
            'communication_title': "📬 *Communication*",
            'btn_broadcast': "📢 Broadcast to all",
            'btn_reply_to_user': "✉️ Reply to User",
            'reply_prompt_user_id': "Enter the User ID of the user you want to message:",
            'reply_prompt_message': "Now enter the message for user `{user_id}`:",
            'broadcast_prompt': "Send the message to be broadcast to all users. To cancel, type /cancel.",
            'broadcast_confirm_prompt': "You are about to send the following message to `{count}` users. Are you sure?\n\n---\n{message_text}\n---",
            'btn_confirm_broadcast': "Yes, send",
            'btn_cancel_broadcast': "Cancel",
            'broadcast_started': "✅ Broadcast initiated...",
            'broadcast_cancelled': "❌ Broadcast cancelled.",
            'broadcast_finished': "✅ Broadcast finished. Sent: {sent}. Failed: {failed}.",
            'reply_to_user_prompt': "Reply to user `{user_id}`:",
            'reply_sent_success': "✅ Message sent to user `{user_id}`.",
            'reply_sent_fail': "❌ Failed to send message. The user may have blocked the bot.",
            'reply_admin_notification': "✉️ *Message from the administrator:*\n\n`{text}`"
        }
    }
}

DEFAULT_LANG = 'ru'


def get_text(key: str, lang_code: str) -> str:
    """
    Возвращает текст по ключу для указанного языка.
    Если ключ или язык не найден, возвращает ключ в виде строки.
    Поддерживает вложенные ключи (например, 'admin.panel_title').
    """
    lang_dict = LOCALIZATION.get(lang_code)
    if lang_dict is None:
        lang_dict = LOCALIZATION.get(DEFAULT_LANG, {})
    
    # Обработка вложенных ключей
    keys = key.split('.')
    value = lang_dict
    try:
        for k in keys:
            value = value[k]
        if isinstance(value, str):
            return value
        else:
            # Если по ключу лежит словарь, а не строка
            return key
    except KeyError:
        # Пытаемся найти в словаре по умолчанию
        default_dict = LOCALIZATION.get(DEFAULT_LANG, {})
        value = default_dict
        try:
            for k in keys:
                value = value[k]
            if isinstance(value, str):
                return value
        except (KeyError, TypeError):
            return key # Возвращаем сам ключ, если ничего не найдено
    except TypeError:
        # Если пытаемся получить ключ от не-словаря
        return key

    return key