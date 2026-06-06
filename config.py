"""
config.py — конфигурация из .env
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# VK API
VK_TOKEN: str = os.getenv("VK_TOKEN", "")
VK_API_VERSION: str = "5.199"
VK_API_URL: str = "https://api.vk.com/method"

# Фильтры
MIN_MEMBERS: int = int(os.getenv("MIN_MEMBERS", "1000"))
MAX_RESULTS: int = int(os.getenv("MAX_RESULTS", "30"))

# Доступ (пусто = открытый для всех)
ALLOWED_USERS: list[int] = [
    int(x.strip())
    for x in os.getenv("ALLOWED_USERS", "").split(",")
    if x.strip().isdigit()
]


def validate_config():
    errors = []
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN не задан")
    if not VK_TOKEN:
        errors.append("VK_TOKEN не задан")
    if errors:
        raise ValueError("Ошибки конфигурации:\n" + "\n".join(errors))
