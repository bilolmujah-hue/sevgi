"""
PostgreSQL bilan ishlash
asyncpg orqali
"""

import asyncpg
from datetime import datetime
from config import config


# ==================== SQL KONSTANTALAR ====================

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
    tugilgan_kun DATE,
    bio TEXT,
    oxirgi_faollik TIMESTAMP DEFAULT NOW(),
    online BOOLEAN DEFAULT FALSE,
    sana TIMESTAMP DEFAULT NOW()
)
"""

SQL_CREATE_MESSAGES = """
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    from_chat BIGINT,
    to_chat BIGINT,
    group_id INTEGER,
    matn TEXT,
    rasm_url TEXT,
    ovoz_url TEXT,
    ovoz_davomiyligi INTEGER,
    video_url TEXT,
    video_davomiyligi INTEGER,
    fayl_url TEXT,
    fayl_nom TEXT,
    fayl_hajm BIGINT,
    stiker_id TEXT,
    xabar_turi TEXT DEFAULT 'text',
    reply_to_id INTEGER,
    pinned BOOLEAN DEFAULT FALSE,
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

SQL_CREATE_REACTIONS = """
CREATE TABLE IF NOT EXISTS reactions (
    id SERIAL PRIMARY KEY,
    msg_id INTEGER,
    chat_id BIGINT,
    emoji TEXT,
    vaqt TIMESTAMP DEFAULT NOW(),
    UNIQUE(msg_id, chat_id, emoji)
)
"""

SQL_CREATE_GROUPS = """
CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    nom TEXT NOT NULL,
    username TEXT UNIQUE,
    yaratuvchi BIGINT,
    rasm TEXT,
    vaqt TIMESTAMP DEFAULT NOW()
)
"""

SQL_CREATE_GROUP_MEMBERS = """
CREATE TABLE IF NOT EXISTS group_members (
    id SERIAL PRIMARY KEY,
    group_id INTEGER,
    chat_id BIGINT,
    rol TEXT DEFAULT 'member',
    vaqt TIMESTAMP DEFAULT NOW(),
    UNIQUE(group_id, chat_id)
)
"""

SQL_CREATE_CHAT_SETTINGS = """
CREATE TABLE IF NOT EXISTS chat_settings (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT,
    other_chat BIGINT,
    fon_url TEXT,
    vaqt TIMESTAMP DEFAULT NOW(),
    UNIQUE(chat_id, other_chat)
)
"""

# ⚡ YANGI: Global settings
SQL_CREATE_APP_SETTINGS = """
CREATE TABLE IF NOT EXISTS app_settings (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT,
    key TEXT,
    value TEXT,
    vaqt TIMESTAMP DEFAULT NOW(),
    UNIQUE(chat_id, key)
)
"""


class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        url = config.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        
        ssl_param = "require" if ("railway" in url or "render" in url) else None
        
        self.pool = await asyncpg.create_pool(
            url, min_size=2, max_size=10, ssl=ssl_param
        )
        await self.create_tables()
        print("✅ Database ulandi")

    async def create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute(SQL_CREATE_USERS)
            await conn.execute(SQL_CREATE_MESSAGES)
            await conn.execute(SQL_CREATE_PHOTOS)
            await conn.execute(SQL_CREATE_BLOCKS)
            await conn.execute(SQL_CREATE_SESSIONS)
            await conn.execute(SQL_CREATE_ADMIN_LOGS)
            await conn.execute(SQL_CREATE_REACTIONS)
            await conn.execute(SQL_CREATE_GROUPS)
            await conn.execute(SQL_CREATE_GROUP_MEMBERS)
            await conn.execute(SQL_CREATE_CHAT_SETTINGS)
            await conn.execute(SQL_CREATE_APP_SETTINGS)

            alters = [
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS tugilgan_kun DATE",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS online BOOLEAN DEFAULT FALSE",
                "ALTER TABLE messages ADD COLUMN IF NOT EXISTS ovoz_url TEXT",
                "ALTER TABLE messages ADD COLUMN IF NOT EXISTS ovoz_davomiyligi INTEGER",
                "ALTER TABLE messages ADD COLUMN IF NOT EXISTS video_url TEXT",
                "ALTER TABLE messages ADD COLUMN IF NOT EXISTS video_davomiyligi INTEGER",
                "ALTER TABLE messages ADD COLUMN IF NOT EXISTS fayl_url TEXT",
                "ALTER TABLE messages ADD COLUMN IF NOT EXISTS fayl_nom TEXT",
                "ALTER TABLE messages ADD COLUMN IF NOT EXISTS fayl_hajm BIGINT",
                "ALTER TABLE messages ADD COLUMN IF NOT EXISTS reply_to_id INTEGER",
                "ALTER TABLE messages ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE",
                "ALTER TABLE messages ADD COLUMN IF NOT EXISTS group_id INTEGER",
                "ALTER TABLE groups ADD COLUMN IF NOT EXISTS username TEXT",
            ]
            for sql in alters:
                try: await conn.execute(sql)
                except Exception: pass

            try:
                await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_groups_username ON groups(username) WHERE username IS NOT NULL")
            except Exception: pass

            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(from_chat, to_chat)",
                "CREATE INDEX IF NOT EXISTS idx_messages_vaqt ON messages(vaqt DESC)",
                "CREATE INDEX IF NOT EXISTS idx_messages_group ON messages(group_id)",
                "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
                "CREATE INDEX IF NOT EXISTS idx_messages_kurilgan ON messages(to_chat, kurilgan)",
                "CREATE INDEX IF NOT EXISTS idx_reactions_msg ON reactions(msg_id)",
                "CREATE INDEX IF NOT EXISTS idx_group_members ON group_members(group_id, chat_id)",
            ]
            for sql in indexes:
                try: await conn.execute(sql)
                except Exception: pass

        print("✅ Jadvallar yaratildi")

    # ==================== FOYDALANUVCHILAR ====================

    async def add_user(self, chat_id, ism, familya, username, telefon):
        sql = (
            "INSERT INTO users (chat_id, ism, familya, username, telefon) "
            "VALUES ($1, $2, $3, $4, $5) "
            "ON CONFLICT (chat_id) DO UPDATE "
            "SET ism = $2, familya = $3, username = $4, telefon = $5"
        )
        async with self.pool.acquire() as conn:
            await conn.execute(sql, chat_id, ism, familya, username, telefon)

    async def get_user(self, chat_id):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM users WHERE chat_id = $1", chat_id)

    async def get_user_by_username(self, username):
        username = username.lstrip("@")
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)

    async def update_parol(self, chat_id, parol_hash):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET parol_hash = $1, parol_vaqt = NOW() WHERE chat_id = $2",
                parol_hash, chat_id
            )

    async def update_profil_rasm(self, chat_id, rasm_url):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE users SET profil_rasm = $1 WHERE chat_id = $2", rasm_url, chat_id)

    async def update_tungi_rejim(self, chat_id, holat):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE users SET tungi_rejim = $1 WHERE chat_id = $2", holat, chat_id)

    async def get_all_users(self):
        """Admin uchun — BARCHA ma'lumotlar"""
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM users ORDER BY sana DESC")

    async def update_oxirgi_faollik(self, chat_id):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE users SET oxirgi_faollik = NOW() WHERE chat_id = $1", chat_id)

    async def set_online(self, chat_id, online: bool):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET online = $1, oxirgi_faollik = NOW() WHERE chat_id = $2",
                online, chat_id
            )

    async def update_profile(self, chat_id, ism=None, familya=None, tugilgan_kun=None, bio=None):
        updates = []
        params = []
        i = 1
        if ism is not None: updates.append(f"ism = ${i}"); params.append(ism); i += 1
        if familya is not None: updates.append(f"familya = ${i}"); params.append(familya); i += 1
        if tugilgan_kun is not None: updates.append(f"tugilgan_kun = ${i}"); params.append(tugilgan_kun); i += 1
        if bio is not None: updates.append(f"bio = ${i}"); params.append(bio); i += 1
        if not updates: return
        params.append(chat_id)
        sql = f"UPDATE users SET {', '.join(updates)} WHERE chat_id = ${i}"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, *params)

    # ⚡ YANGI: Admin uchun statistika
    async def get_stats(self):
        """Umumiy statistika"""
        async with self.pool.acquire() as conn:
            users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
            messages_count = await conn.fetchval("SELECT COUNT(*) FROM messages WHERE ochirilgan = FALSE")
            groups_count = await conn.fetchval("SELECT COUNT(*) FROM groups")
            online_count = await conn.fetchval("SELECT COUNT(*) FROM users WHERE online = TRUE")
            with_parol = await conn.fetchval("SELECT COUNT(*) FROM users WHERE parol_hash IS NOT NULL")
            return {
                "users": users_count,
                "messages": messages_count,
                "groups": groups_count,
                "online": online_count,
                "with_parol": with_parol
            }

    # ==================== XABARLAR ====================

    async def add_message(self, from_chat, to_chat, matn=None,
                          rasm_url=None, stiker_id=None, xabar_turi='text',
                          ovoz_url=None, ovoz_davomiyligi=None,
                          video_url=None, video_davomiyligi=None,
                          fayl_url=None, fayl_nom=None, fayl_hajm=None,
                          reply_to_id=None, group_id=None):
        sql = (
            "INSERT INTO messages "
            "(from_chat, to_chat, group_id, matn, rasm_url, stiker_id, xabar_turi, "
            "ovoz_url, ovoz_davomiyligi, video_url, video_davomiyligi, "
            "fayl_url, fayl_nom, fayl_hajm, reply_to_id) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15) "
            "RETURNING id"
        )
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                sql, from_chat, to_chat, group_id, matn, rasm_url, stiker_id, xabar_turi,
                ovoz_url, ovoz_davomiyligi, video_url, video_davomiyligi,
                fayl_url, fayl_nom, fayl_hajm, reply_to_id
            )

    async def get_messages(self, chat1, chat2, limit=50, offset=0):
        sql = (
            "SELECT * FROM messages "
            "WHERE ((from_chat = $1 AND to_chat = $2) OR (from_chat = $2 AND to_chat = $1)) "
            "  AND group_id IS NULL AND ochirilgan = FALSE "
            "ORDER BY vaqt DESC LIMIT $3 OFFSET $4"
        )
        async with self.pool.acquire() as conn:
            return await conn.fetch(sql, chat1, chat2, limit, offset)

    async def get_group_messages(self, group_id, limit=50, offset=0):
        sql = (
            "SELECT * FROM messages WHERE group_id = $1 AND ochirilgan = FALSE "
            "ORDER BY vaqt DESC LIMIT $2 OFFSET $3"
        )
        async with self.pool.acquire() as conn:
            return await conn.fetch(sql, group_id, limit, offset)

    async def get_message_by_id(self, msg_id):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM messages WHERE id = $1", msg_id)

    async def delete_message(self, msg_id, chat_id):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "UPDATE messages SET ochirilgan = TRUE WHERE id = $1 AND from_chat = $2 RETURNING *",
                msg_id, chat_id
            )

    async def edit_message(self, msg_id, chat_id, yangi_matn):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "UPDATE messages SET matn = $1, tahrirlangan = TRUE WHERE id = $2 AND from_chat = $3 RETURNING *",
                yangi_matn, msg_id, chat_id
            )

    async def mark_as_read(self, from_chat, to_chat):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE messages SET kurilgan = TRUE WHERE from_chat = $1 AND to_chat = $2 AND kurilgan = FALSE",
                from_chat, to_chat
            )

    async def get_unread_count(self, from_chat, to_chat):
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM messages WHERE from_chat = $1 AND to_chat = $2 AND kurilgan = FALSE AND ochirilgan = FALSE",
                from_chat, to_chat
            )

    async def pin_message(self, msg_id, chat_id):
        async with self.pool.acquire() as conn:
            msg = await conn.fetchrow("SELECT * FROM messages WHERE id = $1", msg_id)
            if not msg: return None
            if msg['group_id']:
                await conn.execute("UPDATE messages SET pinned = FALSE WHERE group_id = $1 AND pinned = TRUE", msg['group_id'])
            else:
                await conn.execute(
                    "UPDATE messages SET pinned = FALSE WHERE ((from_chat = $1 AND to_chat = $2) OR (from_chat = $2 AND to_chat = $1)) AND pinned = TRUE",
                    msg['from_chat'], msg['to_chat']
                )
            return await conn.fetchrow("UPDATE messages SET pinned = TRUE WHERE id = $1 RETURNING *", msg_id)

    async def unpin_message(self, msg_id, chat_id):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "UPDATE messages SET pinned = FALSE WHERE id = $1 AND from_chat = $2 RETURNING *",
                msg_id, chat_id
            )

    async def get_pinned_message(self, chat1, chat2):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM messages WHERE ((from_chat = $1 AND to_chat = $2) OR (from_chat = $2 AND to_chat = $1)) AND pinned = TRUE AND ochirilgan = FALSE LIMIT 1",
                chat1, chat2
            )

    async def get_group_pinned_message(self, group_id):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM messages WHERE group_id = $1 AND pinned = TRUE AND ochirilgan = FALSE LIMIT 1",
                group_id
            )

    # ==================== RASMLAR ====================

    async def add_photo(self, chat_id, rasm_url, nom=None):
        async with self.pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM photos WHERE chat_id = $1", chat_id)
            if count >= config.MAX_PHOTOS_PER_USER: return None
            return await conn.fetchrow(
                "INSERT INTO photos (chat_id, rasm_url, nom) VALUES ($1, $2, $3) RETURNING id",
                chat_id, rasm_url, nom
            )

    async def get_photos(self, chat_id):
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM photos WHERE chat_id = $1 ORDER BY vaqt DESC", chat_id)

    async def delete_photo(self, photo_id, chat_id):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("DELETE FROM photos WHERE id = $1 AND chat_id = $2 RETURNING *", photo_id, chat_id)

    # ==================== BLOKLAR ====================

    async def block_user(self, chat_id, blocked_chat):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO blocks (chat_id, blocked_chat) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                chat_id, blocked_chat
            )

    async def unblock_user(self, chat_id, blocked_chat):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM blocks WHERE chat_id = $1 AND blocked_chat = $2", chat_id, blocked_chat)

    async def is_blocked(self, chat_id, blocked_chat):
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT COUNT(*) FROM blocks WHERE chat_id = $1 AND blocked_chat = $2",
                chat_id, blocked_chat
            )
            return result > 0

    async def get_blocked_list(self, chat_id):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                "SELECT b.blocked_chat, u.ism, u.familya, u.username "
                "FROM blocks b JOIN users u ON u.chat_id = b.blocked_chat WHERE b.chat_id = $1",
                chat_id
            )

    # ==================== SESSIONS ====================

    async def save_session(self, token, chat_id, ip=None):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO sessions (token, chat_id, ip) VALUES ($1, $2, $3) "
                "ON CONFLICT (token) DO UPDATE SET chat_id = EXCLUDED.chat_id, vaqt = NOW(), ip = EXCLUDED.ip",
                token, chat_id, ip
            )

    async def delete_session(self, token):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM sessions WHERE token = $1", token)

    async def clear_user_sessions(self, chat_id):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM sessions WHERE chat_id = $1", chat_id)

    # ==================== REACTIONS ====================

    async def add_reaction(self, msg_id, chat_id, emoji):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO reactions (msg_id, chat_id, emoji) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                msg_id, chat_id, emoji
            )

    async def remove_reaction(self, msg_id, chat_id, emoji):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM reactions WHERE msg_id = $1 AND chat_id = $2 AND emoji = $3", msg_id, chat_id, emoji)

    async def get_reactions(self, msg_id):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                "SELECT emoji, COUNT(*) as count, array_agg(chat_id) as chat_ids FROM reactions WHERE msg_id = $1 GROUP BY emoji",
                msg_id
            )

    async def get_reactions_for_messages(self, msg_ids):
        if not msg_ids: return {}
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT msg_id, emoji, COUNT(*) as count, array_agg(chat_id) as chat_ids FROM reactions WHERE msg_id = ANY($1) GROUP BY msg_id, emoji",
                msg_ids
            )
        result = {}
        for r in rows:
            if r['msg_id'] not in result: result[r['msg_id']] = []
            result[r['msg_id']].append({'emoji': r['emoji'], 'count': r['count'], 'chat_ids': list(r['chat_ids'])})
        return result

    # ==================== GROUPS ====================

    async def create_group(self, nom, yaratuvchi, username=None, rasm=None):
        async with self.pool.acquire() as conn:
            group = await conn.fetchrow(
                "INSERT INTO groups (nom, username, yaratuvchi, rasm) VALUES ($1, $2, $3, $4) RETURNING *",
                nom, username, yaratuvchi, rasm
            )
            await conn.execute(
                "INSERT INTO group_members (group_id, chat_id, rol) VALUES ($1, $2, 'admin')",
                group['id'], yaratuvchi
            )
            return group

    async def get_group(self, group_id):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM groups WHERE id = $1", group_id)

    async def get_group_by_username(self, username):
        username = username.lstrip("@")
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM groups WHERE username = $1", username)

    async def username_exists(self, username, exclude_group_id=None):
        username = username.lstrip("@")
        async with self.pool.acquire() as conn:
            if exclude_group_id:
                result = await conn.fetchval("SELECT COUNT(*) FROM groups WHERE username = $1 AND id != $2", username, exclude_group_id)
            else:
                result = await conn.fetchval("SELECT COUNT(*) FROM groups WHERE username = $1", username)
            return result > 0

    async def get_user_groups(self, chat_id):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                "SELECT g.*, gm.rol FROM groups g JOIN group_members gm ON gm.group_id = g.id WHERE gm.chat_id = $1 ORDER BY g.vaqt DESC",
                chat_id
            )

    async def add_group_member(self, group_id, chat_id, rol='member'):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO group_members (group_id, chat_id, rol) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                group_id, chat_id, rol
            )

    async def remove_group_member(self, group_id, chat_id):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM group_members WHERE group_id = $1 AND chat_id = $2", group_id, chat_id)

    async def get_group_members(self, group_id):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                "SELECT gm.*, u.ism, u.familya, u.username, u.profil_rasm, u.online "
                "FROM group_members gm JOIN users u ON u.chat_id = gm.chat_id WHERE gm.group_id = $1",
                group_id
            )

    async def is_group_member(self, group_id, chat_id):
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT COUNT(*) FROM group_members WHERE group_id = $1 AND chat_id = $2",
                group_id, chat_id
            )
            return result > 0

    async def is_group_admin(self, group_id, chat_id):
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT rol FROM group_members WHERE group_id = $1 AND chat_id = $2",
                group_id, chat_id
            )
            return result == 'admin'

    async def delete_group(self, group_id):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM group_members WHERE group_id = $1", group_id)
            await conn.execute("DELETE FROM messages WHERE group_id = $1", group_id)
            await conn.execute("DELETE FROM groups WHERE id = $1", group_id)

    # ==================== CHAT SETTINGS ====================

    async def set_chat_fon(self, chat_id, other_chat, fon_url):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chat_settings (chat_id, other_chat, fon_url) VALUES ($1, $2, $3) "
                "ON CONFLICT (chat_id, other_chat) DO UPDATE SET fon_url = EXCLUDED.fon_url",
                chat_id, other_chat, fon_url
            )

    async def get_chat_fon(self, chat_id, other_chat):
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT fon_url FROM chat_settings WHERE chat_id = $1 AND other_chat = $2", chat_id, other_chat)

    async def delete_chat_fon(self, chat_id, other_chat):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM chat_settings WHERE chat_id = $1 AND other_chat = $2", chat_id, other_chat)

    # ==================== ADMIN ====================

    async def log_admin_action(self, admin_id, harakat, tafsilot=None):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO admin_logs (admin_id, harakat, tafsilot) VALUES ($1, $2, $3)",
                admin_id, harakat, tafsilot
            )

    async def close(self):
        if self.pool:
            await self.pool.close()


db = Database()
