"""
PostgreSQL bilan ishlash
asyncpg orqali
"""

import asyncpg
from config import config


# ==================== SQL KONSTANTALAR ====================
# Bu SQL lar PyCharm tomonidan buzilmasligi uchun
# alohida konstanta sifatida saqlanadi

SQL_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    chat_id BIGINT PRIMARY KEY,
    ism TEXT NOT NULL,
    familya TEXT,
    username TEXT UNIQUE,
    telefon TEXT UNIQUE,
    parol_hash TEXT,
    parol_vaqt TIMESTAMP,
    blok_vaqt TIMESTAMP,
    blok_son TEXT,
    blok_soat INTEGER,
    maxfiylik BOOLEAN DEFAULT FALSE,
    maxfiylik_vaqt TIMESTAMP,
    profil_rasm TEXT,
    tungi_rejim BOOLEAN DEFAULT FALSE,
    oxirgi_faollik TIMESTAMP DEFAULT NOW(),
    sana TIMESTAMP DEFAULT NOW()
)
"""

SQL_CREATE_MESSAGES = """
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    from_chat BIGINT,
    to_chat BIGINT,
    matn TEXT,
    rasm_url TEXT,
    stiker_id TEXT,
    xabar_turi TEXT DEFAULT 'text',
    ochirilgan BOOLEAN DEFAULT FALSE,
    tahrirlangan BOOLEAN DEFAULT FALSE,
    kurilgan BOOLEAN DEFAULT FALSE,
    vaqt TIMESTAMP DEFAULT NOW()
)
"""

SQL_CREATE_PHOTOS = """
CREATE TABLE IF NOT EXISTS photos (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT,
    rasm_url TEXT NOT NULL,
    nom TEXT,
    vaqt TIMESTAMP DEFAULT NOW()
)
"""

SQL_CREATE_BLOCKS = """
CREATE TABLE IF NOT EXISTS blocks (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT,
    blocked_chat BIGINT,
    vaqt TIMESTAMP DEFAULT NOW(),
    UNIQUE(chat_id, blocked_chat)
)
"""

SQL_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    chat_id BIGINT,
    vaqt TIMESTAMP DEFAULT NOW(),
    ip TEXT
)
"""

SQL_CREATE_ADMIN_LOGS = """
CREATE TABLE IF NOT EXISTS admin_logs (
    id SERIAL PRIMARY KEY,
    admin_id BIGINT,
    harakat TEXT,
    tafsilot TEXT,
    vaqt TIMESTAMP DEFAULT NOW()
)
"""

SQL_CREATE_INDEX_1 = "CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(from_chat, to_chat)"
SQL_CREATE_INDEX_2 = "CREATE INDEX IF NOT EXISTS idx_messages_vaqt ON messages(vaqt DESC)"
SQL_CREATE_INDEX_3 = "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"


class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        """Database ga ulanish"""
        self.pool = await asyncpg.create_pool(
            config.DATABASE_URL,
            min_size=5,
            max_size=20
        )
        await self.create_tables()
        print("✅ Database ulandi")

    async def create_tables(self):
        """Jadvallarni yaratish"""
        async with self.pool.acquire() as conn:
            await conn.execute(SQL_CREATE_USERS)
            await conn.execute(SQL_CREATE_MESSAGES)
            await conn.execute(SQL_CREATE_PHOTOS)
            await conn.execute(SQL_CREATE_BLOCKS)
            await conn.execute(SQL_CREATE_SESSIONS)
            await conn.execute(SQL_CREATE_ADMIN_LOGS)

            await conn.execute(SQL_CREATE_INDEX_1)
            await conn.execute(SQL_CREATE_INDEX_2)
            await conn.execute(SQL_CREATE_INDEX_3)

        print("✅ Jadvallar yaratildi")

    # ==================== FOYDALANUVCHILAR ====================

    async def add_user(self, chat_id, ism, familya, username, telefon):
        """Yangi foydalanuvchi qo'shish"""
        sql = (
            "INSERT INTO users (chat_id, ism, familya, username, telefon) "
            "VALUES ($1, $2, $3, $4, $5) "
            "ON CONFLICT (chat_id) DO UPDATE "
            "SET ism = $2, familya = $3, username = $4, telefon = $5"
        )
        async with self.pool.acquire() as conn:
            await conn.execute(sql, chat_id, ism, familya, username, telefon)

    async def get_user(self, chat_id):
        """Foydalanuvchini olish"""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM users WHERE chat_id = $1", chat_id
            )

    async def get_user_by_username(self, username):
        """Username orqali foydalanuvchi olish"""
        username = username.lstrip("@")
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM users WHERE username = $1", username
            )

    async def update_parol(self, chat_id, parol_hash):
        """Parolni yangilash"""
        sql = (
            "UPDATE users SET parol_hash = $1, parol_vaqt = NOW() "
            "WHERE chat_id = $2"
        )
        async with self.pool.acquire() as conn:
            await conn.execute(sql, parol_hash, chat_id)

    async def update_blok(self, chat_id, blok_vaqt, blok_son, blok_soat):
        """Vaqt blokni yangilash"""
        sql = (
            "UPDATE users SET blok_vaqt = $1, blok_son = $2, blok_soat = $3 "
            "WHERE chat_id = $4"
        )
        async with self.pool.acquire() as conn:
            await conn.execute(sql, blok_vaqt, blok_son, blok_soat, chat_id)

    async def clear_blok(self, chat_id):
        """Blokni tozalash"""
        sql = (
            "UPDATE users SET blok_vaqt = NULL, blok_son = NULL, blok_soat = NULL "
            "WHERE chat_id = $1"
        )
        async with self.pool.acquire() as conn:
            await conn.execute(sql, chat_id)

    async def update_maxfiylik(self, chat_id, holat):
        """Maxfiylikni yangilash"""
        sql = (
            "UPDATE users SET maxfiylik = $1, maxfiylik_vaqt = NOW() "
            "WHERE chat_id = $2"
        )
        async with self.pool.acquire() as conn:
            await conn.execute(sql, holat, chat_id)

    async def update_profil_rasm(self, chat_id, rasm_url):
        """Profil rasmini yangilash"""
        sql = "UPDATE users SET profil_rasm = $1 WHERE chat_id = $2"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, rasm_url, chat_id)

    async def update_tungi_rejim(self, chat_id, holat):
        """Tungi rejimni yangilash"""
        sql = "UPDATE users SET tungi_rejim = $1 WHERE chat_id = $2"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, holat, chat_id)

    async def get_all_users(self):
        """Barcha foydalanuvchilarni olish (admin uchun)"""
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM users ORDER BY sana DESC")

    async def update_oxirgi_faollik(self, chat_id):
        """Oxirgi faollikni yangilash"""
        sql = "UPDATE users SET oxirgi_faollik = NOW() WHERE chat_id = $1"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, chat_id)

    # ==================== XABARLAR ====================

    async def add_message(self, from_chat, to_chat, matn=None,
                          rasm_url=None, stiker_id=None, xabar_turi='text'):
        """Yangi xabar qo'shish"""
        sql = (
            "INSERT INTO messages "
            "(from_chat, to_chat, matn, rasm_url, stiker_id, xabar_turi) "
            "VALUES ($1, $2, $3, $4, $5, $6) RETURNING id"
        )
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                sql, from_chat, to_chat, matn, rasm_url, stiker_id, xabar_turi
            )

    async def get_messages(self, chat1, chat2, limit=50, offset=0):
        """Ikki foydalanuvchi orasidagi xabarlar"""
        sql = (
            "SELECT * FROM messages "
            "WHERE ((from_chat = $1 AND to_chat = $2) "
            "    OR (from_chat = $2 AND to_chat = $1)) "
            "  AND ochirilgan = FALSE "
            "ORDER BY vaqt DESC "
            "LIMIT $3 OFFSET $4"
        )
        async with self.pool.acquire() as conn:
            return await conn.fetch(sql, chat1, chat2, limit, offset)

    async def delete_message(self, msg_id, chat_id):
        """Xabarni o'chirish (faqat o'zi yozgan)"""
        sql = (
            "UPDATE messages SET ochirilgan = TRUE "
            "WHERE id = $1 AND from_chat = $2 RETURNING *"
        )
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, msg_id, chat_id)

    async def edit_message(self, msg_id, chat_id, yangi_matn):
        """Xabarni tahrirlash"""
        sql = (
            "UPDATE messages SET matn = $1, tahrirlangan = TRUE "
            "WHERE id = $2 AND from_chat = $3 RETURNING *"
        )
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, yangi_matn, msg_id, chat_id)

    async def mark_as_read(self, from_chat, to_chat):
        """Xabarlarni o'qilgan deb belgilash"""
        sql = (
            "UPDATE messages SET kurilgan = TRUE "
            "WHERE from_chat = $1 AND to_chat = $2 AND kurilgan = FALSE"
        )
        async with self.pool.acquire() as conn:
            await conn.execute(sql, from_chat, to_chat)

    # ==================== RASMLAR ====================

    async def add_photo(self, chat_id, rasm_url, nom=None):
        """Rasm qo'shish (20 ta limit)"""
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM photos WHERE chat_id = $1", chat_id
            )
            if count >= config.MAX_PHOTOS_PER_USER:
                return None
            sql = (
                "INSERT INTO photos (chat_id, rasm_url, nom) "
                "VALUES ($1, $2, $3) RETURNING id"
            )
            return await conn.fetchrow(sql, chat_id, rasm_url, nom)

    async def get_photos(self, chat_id):
        """Foydalanuvchi rasmlarini olish"""
        sql = "SELECT * FROM photos WHERE chat_id = $1 ORDER BY vaqt DESC"
        async with self.pool.acquire() as conn:
            return await conn.fetch(sql, chat_id)

    async def delete_photo(self, photo_id, chat_id):
        """Rasmni o'chirish"""
        sql = "DELETE FROM photos WHERE id = $1 AND chat_id = $2 RETURNING *"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, photo_id, chat_id)

    # ==================== BLOKLAR ====================

    async def block_user(self, chat_id, blocked_chat):
        """Foydalanuvchini bloklash"""
        sql = (
            "INSERT INTO blocks (chat_id, blocked_chat) "
            "VALUES ($1, $2) ON CONFLICT DO NOTHING"
        )
        async with self.pool.acquire() as conn:
            await conn.execute(sql, chat_id, blocked_chat)

    async def unblock_user(self, chat_id, blocked_chat):
        """Blokdan chiqarish"""
        sql = "DELETE FROM blocks WHERE chat_id = $1 AND blocked_chat = $2"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, chat_id, blocked_chat)

    async def is_blocked(self, chat_id, blocked_chat):
        """Bloklanganligini tekshirish"""
        sql = (
            "SELECT COUNT(*) FROM blocks "
            "WHERE chat_id = $1 AND blocked_chat = $2"
        )
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(sql, chat_id, blocked_chat)
            return result > 0

    async def get_blocked_list(self, chat_id):
        """Bloklangan foydalanuvchilar ro'yxati"""
        sql = (
            "SELECT b.blocked_chat, u.ism, u.familya, u.username "
            "FROM blocks b "
            "JOIN users u ON u.chat_id = b.blocked_chat "
            "WHERE b.chat_id = $1"
        )
        async with self.pool.acquire() as conn:
            return await conn.fetch(sql, chat_id)

    # ==================== SESSIONS ====================

    async def save_session(self, token, chat_id, ip=None):
        """Session saqlash"""
        sql = "INSERT INTO sessions (token, chat_id, ip) VALUES ($1, $2, $3)"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, token, chat_id, ip)

    async def get_session(self, token):
        """Session olish"""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM sessions WHERE token = $1", token
            )

    async def delete_session(self, token):
        """Session o'chirish"""
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM sessions WHERE token = $1", token)

    # ==================== ADMIN ====================

    async def log_admin_action(self, admin_id, harakat, tafsilot=None):
        """Admin harakatini log qilish"""
        sql = (
            "INSERT INTO admin_logs (admin_id, harakat, tafsilot) "
            "VALUES ($1, $2, $3)"
        )
        async with self.pool.acquire() as conn:
            await conn.execute(sql, admin_id, harakat, tafsilot)

    async def close(self):
        """Ulanishni yopish"""
        if self.pool:
            await self.pool.close()


# Global instance
db = Database()