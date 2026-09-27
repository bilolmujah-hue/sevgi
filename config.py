"""
Konfiguratsiya fayli
Barcha sozlamalar shu yerda saqlanadi
"""

import os


class Config:
    # ==================== TELEGRAM BOT ====================
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "8847133046:AAFihqr2ycn7M6MVmZLzZtlAoP3GPW0jTN0")
    ADMIN_ID = int(os.environ.get("ADMIN_ID", "7038296036"))

    # ==================== USERBOT (TELETHON) ====================
    API_ID = int(os.environ.get("API_ID", "31917099"))
    API_HASH = os.environ.get("API_HASH", "0d7f957624ad1bb1bbf098343ae119b2")
    USERBOT_PHONE = os.environ.get("USERBOT_PHONE", "+998900512621")
    USERBOT_SESSION = os.environ.get("USERBOT_SESSION", "userbot_session")

    # ==================== DATABASE ====================
    # Railway avtomatik DATABASE_URL beradi
    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:root@localhost:5432/sevgi_db"
    )

    # ==================== WEB APP ====================
    WEBAPP_URL = os.environ.get("WEBAPP_URL", "http://localhost:8000")

    # ==================== XAVFSIZLIK ====================
    JWT_SECRET = os.environ.get("JWT_SECRET", "bilolbek_super_secret_key_2024")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_MINUTES = 60

    # ==================== LIMITLAR ====================
    MAX_PHOTOS_PER_USER = 20
    PAROL_LENGTH = 5
    MAX_LOGIN_ATTEMPTS = 5
    RATE_LIMIT_WINDOW = 60

    # ==================== VAQT BLOK ====================
    BLOK_MAX_HOURS = 24

    # ==================== MAXFIYLIK ====================
    MAXFIYLIK_KUN = 3

    # ==================== SERVER ====================
    # ⚠️ Railway PORT ni avtomatik beradi!
    HOST = "0.0.0.0"
    PORT = int(os.environ.get("PORT", 8000))

    # ==================== RASMLAR ====================
    UPLOAD_DIR = "static/uploads"
    MAX_PHOTO_SIZE = 5 * 1024 * 1024
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

    # ==================== SELF-DESTRUCT ====================
    SELF_DESTRUCT_SECONDS = 5


config = Config()