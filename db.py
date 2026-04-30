import os
import aiosqlite
from config import DB_PATH


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id         INTEGER PRIMARY KEY,
            username        TEXT,
            first_name      TEXT,
            lang            TEXT DEFAULT NULL,
            joined_at       TEXT,
            is_blocked      INTEGER DEFAULT 0,
            is_vip          INTEGER DEFAULT 0,
            used_konami     INTEGER DEFAULT 0,
            used_matrix     INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS admins (
            user_id             INTEGER PRIMARY KEY,
            can_add_movie       INTEGER DEFAULT 0,
            can_delete_movie    INTEGER DEFAULT 0,
            can_change_title    INTEGER DEFAULT 0,
            can_manage_channels INTEGER DEFAULT 0,
            can_manage_admins   INTEGER DEFAULT 0,
            can_broadcast       INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS movies (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            type            TEXT DEFAULT 'movie',
            title_uz        TEXT NOT NULL,
            title_ru        TEXT NOT NULL,
            title_en        TEXT NOT NULL,
            file_id         TEXT,
            code            TEXT UNIQUE NOT NULL,
            added_by        INTEGER,
            request_count   INTEGER DEFAULT 0,
            added_at        TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS episodes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_code  TEXT NOT NULL,
            episode_num INTEGER NOT NULL,
            file_id     TEXT NOT NULL,
            UNIQUE(movie_code, episode_num)
        );
        CREATE TABLE IF NOT EXISTS mandatory_channels (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_username    TEXT UNIQUE NOT NULL,
            is_private          INTEGER DEFAULT 0,
            invite_link         TEXT
        );
        CREATE TABLE IF NOT EXISTS settings (
            key     TEXT PRIMARY KEY,
            value   TEXT
        );
        """)
        migrations = [
            "ALTER TABLE users ADD COLUMN is_vip INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN used_konami INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN used_matrix INTEGER DEFAULT 0",
            "ALTER TABLE movies ADD COLUMN type TEXT DEFAULT 'movie'",
            "ALTER TABLE movies ADD COLUMN title_en TEXT",
            "ALTER TABLE movies ADD COLUMN request_count INTEGER DEFAULT 0",
            "ALTER TABLE mandatory_channels ADD COLUMN is_private INTEGER DEFAULT 0",
            "ALTER TABLE mandatory_channels ADD COLUMN invite_link TEXT",
        ]
        for m in migrations:
            try:
                await db.execute(m)
            except:
                pass
        # Fill missing title_en from title_uz
        try:
            await db.execute("UPDATE movies SET title_en = title_uz WHERE title_en IS NULL OR title_en = ''")
        except:
            pass
        await db.commit()


async def db_exec(query, args=()):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(query, args)
        await db.commit()
        return cur.lastrowid


async def db_one(query, args=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(query, args)
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_all(query, args=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(query, args)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_setting(key, default=None):
    row = await db_one("SELECT value FROM settings WHERE key=?", (key,))
    return row["value"] if row else default


async def set_setting(key, value):
    await db_exec("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))


async def get_lang(user_id):
    row = await db_one("SELECT lang FROM users WHERE user_id=?", (user_id,))
    return row["lang"] if row and row.get("lang") else "uz"


async def register_user(user):
    from datetime import datetime
    await db_exec(
        "INSERT OR IGNORE INTO users (user_id, username, first_name, joined_at) VALUES (?,?,?,?)",
        (user.id, user.username or "", user.first_name or "", datetime.now().isoformat())
    )


async def user_has_lang(user_id):
    row = await db_one("SELECT lang FROM users WHERE user_id=?", (user_id,))
    return bool(row and row.get("lang"))


async def is_admin(user_id):
    from config import OWNER_ID
    if user_id == OWNER_ID:
        return True
    return bool(await db_one("SELECT 1 FROM admins WHERE user_id=?", (user_id,)))


async def has_perm(user_id, perm):
    from config import OWNER_ID
    if user_id == OWNER_ID:
        return True
    row = await db_one(f"SELECT {perm} FROM admins WHERE user_id=?", (user_id,))
    return bool(row and row.get(perm))


async def is_vip(user_id):
    from config import OWNER_ID
    if user_id == OWNER_ID:
        return True
    row = await db_one("SELECT is_vip FROM users WHERE user_id=?", (user_id,))
    return bool(row and row.get("is_vip"))


async def check_mandatory(bot, user_id):
    from config import OWNER_ID
    if user_id == OWNER_ID or await is_admin(user_id) or await is_vip(user_id):
        return [], []
    channels = await db_all("SELECT * FROM mandatory_channels")
    not_joined_public = []
    not_joined_private = []
    for ch in channels:
        username = ch["channel_username"]
        try:
            member = await bot.get_chat_member(f"@{username}", user_id)
            if member.status in ["left", "kicked"]:
                if ch.get("is_private"):
                    not_joined_private.append(ch)
                else:
                    not_joined_public.append(username)
        except:
            if ch.get("is_private"):
                not_joined_private.append(ch)
            else:
                not_joined_public.append(username)
    return not_joined_public, not_joined_private


def escape_md(text):
    if not text:
        return ""
    import re
    return re.sub(r'([_*\[\]()~`>#+=|{}.!-])', r'\\\1', str(text))


def get_movie_title(row, lang):
    if lang == "ru":
        return row.get("title_ru") or row.get("title_uz") or "—"
    if lang == "en":
        return row.get("title_en") or row.get("title_uz") or "—"
    return row.get("title_uz") or row.get("title_ru") or "—"
