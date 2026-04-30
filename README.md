# 🎬 MediaBot

A feature-rich Telegram bot for distributing movies and serials, with multi-language support, an admin panel, flood protection, and easter eggs.

---

## ✨ Features

- 🎬 **Movies & Serials** — store and send video files by unique code or title search
- 🌐 **3 Languages** — Uzbek 🇺🇿, Russian 🇷🇺, English 🇬🇧 (user can switch anytime)
- 🔐 **Admin Panel** — granular permissions per admin (add, delete, rename, broadcast, manage channels/admins)
- 📢 **Mandatory Channel Join** — users must join configured channels before accessing content
- ⭐ **VIP System** — bypass mandatory joins with a secret code
- 🛡️ **Flood Protection** — rate limiting on messages and callbacks, with 10-minute temp bans for spammers
- 📊 **Statistics** — total users, language breakdown, top 3 most-requested content
- 🎮 **Easter Eggs** — Konami code and Matrix rabbit hole hidden inside the bot
- 🗃️ **SQLite Database** — lightweight, no external DB required

---

## 📁 Project Structure

```
mediabot/
├── main.py               # Entry point, handler registration
├── db.py                 # Database init, queries, migrations
├── flood.py              # Flood/rate-limit protection
├── langs.py              # All UI strings in uz/ru/en
├── config.py             # Bot token, owner ID, paths (not included)
└── handlers/
    ├── user.py           # User-facing commands and message handling
    ├── admin.py          # Admin panel logic
    ├── callbacks.py      # Inline keyboard callback handlers
    └── keyboards.py      # All keyboard builders
```

---

## ⚙️ Setup

### 1. Clone the repo

```bash
git clone https://github.com/pdmHW/mediabot.git
cd mediabot
```

### 2. Install dependencies

```bash
pip install python-telegram-bot aiosqlite
```

### 3. Create `config.py`

Create a `config.py` file in the `mediabot/` folder:

```python
BOT_TOKEN = "your_bot_token_here"
OWNER_ID = 123456789          # Your Telegram user ID
DB_PATH = "data/mediabot.db"
SECRET_COMMAND = "yoursecret" # Hidden /command for VIP activation
SECRET_BYPASS_CODE = "yourbypasscode"
KONAMI_SEQUENCE = ["⬆️", "⬆️", "⬇️", "⬇️", "⬅️", "➡️", "⬅️", "➡️"]
```

> ⚠️ **Never commit `config.py` to GitHub.** Add it to `.gitignore`.

### 4. Run the bot

```bash
cd mediabot
python main.py
```

---

## 🤖 Commands

| Command | Who | Description |
|---|---|---|
| `/start` | Everyone | Start the bot / select language |
| `/setlang` | Everyone | Change interface language |
| `/ping` | Everyone | Check bot response time |
| `/cancel` | Everyone | Cancel current action |
| `/admin` | Admins | Open the admin panel |

---

## 🛠️ Admin Panel

Accessible via `/admin`. The owner has full access; other admins have only the permissions granted to them:

- Add movies / serials (with UZ, RU, EN titles)
- Delete content
- Rename content titles
- Manage mandatory channels (public & private)
- Manage other admins and their permissions
- Broadcast messages to all users
- View bot statistics

---

## 🗄️ Database

Uses **SQLite** via `aiosqlite`. Tables:

- `users` — registered users, language, VIP/blocked status
- `admins` — admin permissions per user
- `movies` — movies and serials with multi-language titles and codes
- `episodes` — individual serial episodes linked to a movie code
- `mandatory_channels` — channels users must join
- `settings` — key-value store for bot-wide settings

Migrations run automatically on startup — safe to update.

---

## 🌐 Languages

All bot messages are stored in `langs.py` under `uz`, `ru`, and `en` keys. To add a new language, add a new key block in the `LANGS` dict and update the language selection keyboard in `keyboards.py`.

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).

---

## 👤 Author

Made by [@dragnzxm](https://t.me/dragnzxm)
 
