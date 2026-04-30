from telegram import Update
from telegram.ext import ContextTypes
from db import db_one, db_all, db_exec, get_lang, check_mandatory, get_movie_title, is_admin, escape_md
from langs import get_text, LANGS
from handlers.keyboards import join_keyboard, episodes_keyboard, lang_keyboard, main_keyboard
from handlers.user import send_movie_or_serial
from flood import check_callback_flood, is_temp_banned

EPISODES_PER_PAGE = 10


async def _flood_check(query, uid, lang):
    """Returns True if should stop processing"""
    banned, remaining = is_temp_banned(uid)
    if banned:
        mins = remaining // 60
        secs = remaining % 60
        await query.answer(f"🚫 Banned {mins}m {secs}s", show_alert=True)
        return True
    if not await is_admin(uid):
        is_flood, should_ban = check_callback_flood(uid)
        if should_ban:
            await query.answer("🚫 Banned 10min for flooding!", show_alert=True)
            return True
        if is_flood:
            await query.answer(get_text(lang, "flood_warning"), show_alert=True)
            return True
    return False


async def cb_noop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


async def cb_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    lang = await get_lang(uid)
    if "states" in ctx.bot_data and uid in ctx.bot_data["states"]:
        del ctx.bot_data["states"][uid]
    await query.answer()
    await query.edit_message_text(get_text(lang, "cancelled"))


async def cb_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = query.data.split("_")[1]
    uid = query.from_user.id
    # INSERT OR IGNORE first, then UPDATE to ensure user exists
    from datetime import datetime
    await db_exec(
        "INSERT OR IGNORE INTO users (user_id, username, first_name, joined_at) VALUES (?,?,?,?)",
        (uid, query.from_user.username or "", query.from_user.first_name or "", datetime.now().isoformat())
    )
    await db_exec("UPDATE users SET lang=? WHERE user_id=?", (lang, uid))
    await query.answer()
    await query.edit_message_text(LANGS[lang]["lang_set"])
    await query.message.reply_text(
        LANGS[lang]["welcome"],
        reply_markup=main_keyboard(lang),
        parse_mode="Markdown"
    )


async def cb_get(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    lang = await get_lang(uid)
    if await _flood_check(query, uid, lang):
        return
    code = query.data[4:]
    not_joined_pub, not_joined_priv = await check_mandatory(ctx.bot, uid)
    if not_joined_pub or not_joined_priv:
        await query.answer()
        return await query.message.reply_text(
            get_text(lang, "join_required"),
            reply_markup=join_keyboard(not_joined_pub, not_joined_priv)
        )
    row = await db_one("SELECT * FROM movies WHERE code=?", (code,))
    if not row:
        await query.answer("❌ Not found")
        return
    await query.answer()
    await send_movie_or_serial(ctx.bot, uid, row, lang)


async def cb_episode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    lang = await get_lang(uid)
    if await _flood_check(query, uid, lang):
        return
    parts = query.data.split("_")
    code = parts[1]
    ep_num = int(parts[2])
    ep = await db_one("SELECT file_id FROM episodes WHERE movie_code=? AND episode_num=?", (code, ep_num))
    if not ep:
        await query.answer(get_text(lang, "serial_episode_not_found"), show_alert=True)
        return
    movie = await db_one("SELECT title_uz, title_ru, title_en FROM movies WHERE code=?", (code,))
    title = escape_md(get_movie_title(movie, lang))
    ep_escaped = escape_md(str(ep_num))
    await query.answer()
    await ctx.bot.send_video(
        uid,
        ep["file_id"],
        caption=f"📺 *{title}* — Episode {ep_escaped}",
        parse_mode="MarkdownV2"
    )


async def cb_eppage(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    lang = await get_lang(uid)
    if await _flood_check(query, uid, lang):
        return
    parts = query.data.split("_")
    code = parts[1]
    page = int(parts[2])
    await query.answer()
    movie = await db_one("SELECT title_uz, title_ru, title_en FROM movies WHERE code=?", (code,))
    title = get_movie_title(movie, lang)
    total_row = await db_one("SELECT COUNT(*) as c FROM episodes WHERE movie_code=?", (code,))
    total = total_row["c"] if total_row else 0
    episodes = await db_all(
        "SELECT episode_num FROM episodes WHERE movie_code=? ORDER BY episode_num LIMIT ? OFFSET ?",
        (code, EPISODES_PER_PAGE, page * EPISODES_PER_PAGE)
    )
    await query.edit_message_text(
        get_text(lang, "serial_found", title=title),
        reply_markup=episodes_keyboard(episodes, code, page, total),
        parse_mode="Markdown"
    )


async def cb_checkjoin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    lang = await get_lang(uid)
    not_joined_pub, not_joined_priv = await check_mandatory(ctx.bot, uid)
    if not_joined_pub or not_joined_priv:
        await query.answer(get_text(lang, "not_member"), show_alert=True)
    else:
        await query.answer("✅ Great! You can now get movies.", show_alert=True)
        await query.edit_message_reply_markup(reply_markup=None)


async def cb_matrix(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    lang = await get_lang(uid)
    choice = query.data.split("_")[1]
    await query.answer()
    await db_exec("UPDATE users SET used_matrix=1 WHERE user_id=?", (uid,))
    if choice == "red":
        await query.edit_message_text(get_text(lang, "matrix_reveal"), parse_mode="Markdown")
    else:
        await query.edit_message_text(
            "🔵 *You chose the blue pill...*\n\n"
            "`You stay in Wonderland and I show you how deep the rabbit hole goes.`\n\n"
            "Bot continues... 🤖",
            parse_mode="Markdown"
        )


async def cb_delep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    code = query.data.split("_", 1)[1]
    await query.answer()
    episodes = await db_all("SELECT episode_num FROM episodes WHERE movie_code=? ORDER BY episode_num", (code,))
    if not episodes:
        await query.edit_message_text("❌ No episodes found.")
        return
    from handlers.keyboards import episode_delete_keyboard
    await query.edit_message_text(
        "🗑 Select episode to delete:",
        reply_markup=episode_delete_keyboard(code, episodes)
    )


async def cb_confirmdepep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    code = parts[1]
    ep_num = int(parts[2])
    await db_exec("DELETE FROM episodes WHERE movie_code=? AND episode_num=?", (code, ep_num))
    await query.answer("✅ Deleted!")
    await query.edit_message_text(f"✅ Episode {ep_num} deleted.")
