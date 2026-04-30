from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from langs import LANGS

MOVIES_PER_PAGE = 8
EPISODES_PER_PAGE = 10


def main_keyboard(lang):
    L = LANGS.get(lang, LANGS["uz"])
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(L["btn_enter_code"]), KeyboardButton(L["btn_search"])],
            [KeyboardButton(L["btn_support"]), KeyboardButton(L["btn_language"])],
        ],
        resize_keyboard=True
    )


def cancel_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ]])


def lang_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
    ]])


def add_content_type_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Movie", callback_data="addtype_movie")],
        [InlineKeyboardButton("📺 Serial", callback_data="addtype_serial")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ])


def rename_lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇺🇿 Uzbek", callback_data="renamelang_uz"),
         InlineKeyboardButton("🇷🇺 Russian", callback_data="renamelang_ru"),
         InlineKeyboardButton("🇬🇧 English", callback_data="renamelang_en")],
        [InlineKeyboardButton("🌐 All 3 languages", callback_data="renamelang_all")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ])


def delete_confirm_keyboard(code):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Yes, delete", callback_data=f"confirmdelete_{code}"),
        InlineKeyboardButton("❌ No", callback_data="cancel"),
    ]])


def search_results_keyboard(movies, lang):
    from db import get_movie_title
    buttons = []
    for m in movies:
        title = get_movie_title(m, lang)
        icon = "📺" if m.get("type") == "serial" else "🎬"
        buttons.append([InlineKeyboardButton(f"{icon} {title}", callback_data=f"get_{m['code']}")])
    return InlineKeyboardMarkup(buttons)


def episodes_keyboard(episodes, code, page, total):
    buttons = []
    row = []
    for ep in episodes:
        row.append(InlineKeyboardButton(
            f"▶️ {ep['episode_num']}",
            callback_data=f"ep_{code}_{ep['episode_num']}"
        ))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    nav = []
    total_pages = (total + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"eppage_{code}_{page - 1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
    if (page + 1) * EPISODES_PER_PAGE < total:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"eppage_{code}_{page + 1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons)


def movies_list_keyboard(page, total):
    nav = []
    total_pages = (total + MOVIES_PER_PAGE - 1) // MOVIES_PER_PAGE
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"moviepage_{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
    if (page + 1) * MOVIES_PER_PAGE < total:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"moviepage_{page + 1}"))
    return InlineKeyboardMarkup([nav]) if nav else None


def join_keyboard(not_joined_public, not_joined_private):
    buttons = []
    for u in not_joined_public:
        buttons.append([InlineKeyboardButton(f"📢 @{u}", url=f"https://t.me/{u}")])
    for ch in not_joined_private:
        if ch.get("invite_link"):
            buttons.append([InlineKeyboardButton(
                f"🔒 @{ch['channel_username']} — Join",
                url=ch["invite_link"]
            )])
    buttons.append([InlineKeyboardButton("✅ Check", callback_data="checkjoin")])
    return InlineKeyboardMarkup(buttons)


def matrix_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔴 Red pill", callback_data="matrix_red"),
        InlineKeyboardButton("🔵 Blue pill", callback_data="matrix_blue"),
    ]])


def perm_keyboard(target_id, perms):
    perm_labels = {
        "can_add_movie": "🎬 Add Content",
        "can_delete_movie": "🗑 Delete Content",
        "can_change_title": "✏️ Change Title",
        "can_manage_channels": "📢 Manage Channels",
        "can_manage_admins": "👤 Manage Admins",
        "can_broadcast": "📣 Broadcast",
    }
    rows = []
    for perm, label in perm_labels.items():
        val = perms.get(perm, 0)
        icon = "✅" if val else "❌"
        toggle = 0 if val else 1
        rows.append([InlineKeyboardButton(f"{icon} {label}", callback_data=f"perm_{target_id}_{perm}_{toggle}")])
    rows.append([InlineKeyboardButton("💾 Save", callback_data="perm_done")])
    return InlineKeyboardMarkup(rows)


def owner_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Add Content", callback_data="adm_addcontent"),
         InlineKeyboardButton("🗑 Delete", callback_data="adm_delmovie")],
        [InlineKeyboardButton("✏️ Change Title", callback_data="adm_changetitle"),
         InlineKeyboardButton("📺 Add Episode", callback_data="adm_addepisode")],
        [InlineKeyboardButton("📋 Movies", callback_data="adm_listmovies_0"),
         InlineKeyboardButton("📋 Serials", callback_data="adm_listserials_0")],
        [InlineKeyboardButton("📢 Add Channel", callback_data="adm_addchannel"),
         InlineKeyboardButton("❌ Remove Channel", callback_data="adm_removechannel")],
        [InlineKeyboardButton("📋 Channels", callback_data="adm_listchannels")],
        [InlineKeyboardButton("👤 Add Admin", callback_data="adm_addadmin"),
         InlineKeyboardButton("🗑 Remove Admin", callback_data="adm_removeadmin")],
        [InlineKeyboardButton("👥 Admins List", callback_data="adm_listadmins")],
        [InlineKeyboardButton("📣 Broadcast", callback_data="adm_broadcast"),
         InlineKeyboardButton("💬 Set Support", callback_data="adm_setsupport")],
        [InlineKeyboardButton("📊 Stats", callback_data="adm_stats")],
    ])


def build_admin_keyboard(perms):
    buttons = []
    if perms.get("can_add_movie"):
        buttons.append([InlineKeyboardButton("🎬 Add Content", callback_data="adm_addcontent"),
                        InlineKeyboardButton("📺 Add Episode", callback_data="adm_addepisode")])
    if perms.get("can_delete_movie"):
        buttons.append([InlineKeyboardButton("🗑 Delete", callback_data="adm_delmovie")])
    if perms.get("can_change_title"):
        buttons.append([InlineKeyboardButton("✏️ Change Title", callback_data="adm_changetitle")])
    if perms.get("can_manage_channels"):
        buttons.append([
            InlineKeyboardButton("📢 Add Channel", callback_data="adm_addchannel"),
            InlineKeyboardButton("❌ Remove Channel", callback_data="adm_removechannel"),
        ])
        buttons.append([InlineKeyboardButton("📋 Channels", callback_data="adm_listchannels")])
    if perms.get("can_manage_admins"):
        buttons.append([
            InlineKeyboardButton("👤 Add Admin", callback_data="adm_addadmin"),
            InlineKeyboardButton("🗑 Remove Admin", callback_data="adm_removeadmin"),
        ])
        buttons.append([InlineKeyboardButton("👥 Admins List", callback_data="adm_listadmins")])
    if perms.get("can_broadcast"):
        buttons.append([InlineKeyboardButton("📣 Broadcast", callback_data="adm_broadcast")])
    buttons.append([InlineKeyboardButton("💬 Set Support", callback_data="adm_setsupport")])
    buttons.append([InlineKeyboardButton("📊 Stats", callback_data="adm_stats")])
    buttons.append([InlineKeyboardButton("📋 Movies", callback_data="adm_listmovies_0")])
    return InlineKeyboardMarkup(buttons)


def serial_delete_keyboard(code):
    """Ask: delete one episode or all episodes"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Delete one episode", callback_data=f"delep_{code}")],
        [InlineKeyboardButton("💥 Delete entire serial", callback_data=f"confirmdelete_{code}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ])


def episode_delete_keyboard(code, episodes):
    """Show episode list to pick one for deletion"""
    buttons = []
    row = []
    for ep in episodes:
        row.append(InlineKeyboardButton(
            f"🗑 {ep['episode_num']}",
            callback_data=f"confirmdepep_{code}_{ep['episode_num']}"
        ))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)

