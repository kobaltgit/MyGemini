from typing import Dict

# Словарь со всеми текстами. Ключ - язык, значение - словарь с текстами.
LOCALIZATION: Dict[str, Dict[str, str]] = {
    'ru': {
        # Приветствие
        'welcome': "👋 Привет, *{name}*! Я твой личный ассистент на базе Gemini.\n\n"
                   "Для работы мне понадобится твой Google AI API ключ. "
                   "Пожалуйста, установи его с помощью команды /set_api_key.\n\n"
                   "После этого ты сможешь:\n"
                   "🧠 Отвечать на вопросы и генерировать тексты.\n"
                   "🖼️ Анализировать изображения (просто отправь картинку).\n"
                   "🇷🇺 Переводить текст (кнопка 'Перевести').\n"
                   "📜 Смотреть историю диалога (кнопка 'История').\n\n"
                   "Используй /help для получения справки.",
        # Настройки
        'settings_title': "⚙️ *Настройки бота*",
        'settings_style_section': "--- Стиль общения бота ---",
        'settings_language_section': "--- Язык интерфейса ---",
        # Команды
        'cmd_reset_success': "✅ Контекст разговора и ваше текущее состояние сброшены.",
        'cmd_help_title': "🆘 *Справка по боту*",
        # Кнопки
        'btn_translate': "🇷🇺 Перевести",
        'btn_history': "📜 История",
        'btn_account': "👤 Личный кабинет",
        'btn_settings': "⚙️ Настройки",
        'btn_help': "❓ Помощь",
        'btn_reset': "🔄 Сброс",
    },
    'en': {
        # Welcome
        'welcome': "👋 Hi, *{name}*! I'm your personal assistant powered by Gemini.\n\n"
                   "To get started, I'll need your Google AI API key. "
                   "Please set it using the /set_api_key command.\n\n"
                   "After that, you'll be able to:\n"
                   "🧠 Answer questions and generate text.\n"
                   "🖼️ Analyze images (just send a picture).\n"
                   "🇬🇧 Translate text (the 'Translate' button).\n"
                   "📜 View conversation history (the 'History' button).\n\n"
                   "Use /help to get assistance.",
        # Settings
        'settings_title': "⚙️ *Bot Settings*",
        'settings_style_section': "--- Bot Communication Style ---",
        'settings_language_section': "--- Interface Language ---",
        # Commands
        'cmd_reset_success': "✅ The conversation context and your current state have been reset.",
        'cmd_help_title': "🆘 *Bot Help*",
        # Buttons
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
    lang_dict = LOCALIZATION.get(lang_code, LOCALIZATION.get(DEFAULT_LANG, {}))
    return lang_dict.get(key, key)
