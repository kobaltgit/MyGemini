"""
Promo Engine for MyGemini.
Provides native, non-intrusive promotion for creator's projects (flagship @mgemz_bot).
"""

from typing import Optional, Dict, Any
from config.settings import PROMO_PROJECTS


def get_flagship_promo(lang_code: str = "ru") -> str:
    """Returns promotional snippet for flagship MyGemini Zero (@mgemz_bot)."""
    if lang_code == "ru":
        return (
            "🔒 <b>Нужна абсолютная приватность и долговременная память?</b>\n"
            "Попробуйте <b>MyGemini Zero</b> (<code>@mgemz_bot</code>) — сквозное Zero-Knowledge шифрование, "
            "персональный мастер-пароль и векторная RAG-память документов.\n"
            "👉 <a href=\"https://t.me/mgemz_bot\">Открыть @mgemz_bot</a>"
        )
    return (
        "🔒 <b>Need absolute privacy and long-term document memory?</b>\n"
        "Try <b>MyGemini Zero</b> (<code>@mgemz_bot</code>) — end-to-end Zero-Knowledge encryption, "
        "personal master password and vector RAG memory.\n"
        "👉 <a href=\"https://t.me/mgemz_bot\">Open @mgemz_bot</a>"
    )


def get_export_footer(lang_code: str = "ru") -> str:
    """Generates markdown export footer for downloaded transcripts."""
    if lang_code == "ru":
        return (
            "\n\n---\n"
            "*Экспортировано из бота MyGemini*\n"
            "*Флагманский проект с Zero-Knowledge защитой: [@mgemz_bot](https://t.me/mgemz_bot)*\n"
        )
    return (
        "\n\n---\n"
        "*Exported from MyGemini bot*\n"
        "*Flagship project with Zero-Knowledge privacy: [@mgemz_bot](https://t.me/mgemz_bot)*\n"
    )


def get_projects_overview(lang_code: str = "ru") -> str:
    """Returns formatted list of all projects by the author."""
    if lang_code == "ru":
        text = "🚀 <b>Проекты экосистемы Gemini:</b>\n\n"
        text += (
            "1. <b>MyGemini</b> (Текущий бот) — бесплатный быстрый ассистент BYOK с историей в SQLite.\n\n"
            "2. <b>MyGemini Zero</b> (<code>@mgemz_bot</code>) — максимальная безопасность: "
            "клиентское шифрование Zero-Knowledge (PBKDF2 480k, Fernet), долговременная память RAG "
            "и векторный поиск по документам.\n\n"
            "🔗 <a href=\"https://t.me/mgemz_bot\">Перейти к MyGemini Zero</a>"
        )
        return text
    else:
        text = "🚀 <b>Gemini Ecosystem Projects:</b>\n\n"
        text += (
            "1. <b>MyGemini</b> (Current bot) — free & fast BYOK assistant with SQLite history.\n\n"
            "2. <b>MyGemini Zero</b> (<code>@mgemz_bot</code>) — ultimate security: "
            "client-side Zero-Knowledge encryption (PBKDF2 480k, Fernet), long-term RAG memory "
            "and vector document search.\n\n"
            "🔗 <a href=\"https://t.me/mgemz_bot\">Go to MyGemini Zero</a>"
        )
        return text
