import time
import logging
from telegram import Update, ChatMemberUpdated
from telegram.ext import ContextTypes

from db import (
    get_lang, register_user, user_has_lang, check_mandatory,
    db_one, db_all, db_exec, get_setting, is_vip, get_movie_title, is_admin, escape_md
)
from langs import LANGS, get_text
from handlers.keyboards import (
    main_keyboard, cancel_keyboard, lang_keyboard,
    search_results_keyboard, join_keyboard, episodes_keyboard
)
from config import SECRET_BYPASS_CODE, KONAMI_SEQUENCE
from flood import check_message_flood, check_callback_flood, is_temp_banned, get_ban_remaining

EPISODES_PER_PAGE = 10

# ── Konami progress per user ──
konami_progress = {}


async def send_movie_or_serial(bot, chat_id, row, lang):
    title = escape_md(get_movie_title(row, lang))
    if row.get("type") == "serial":
        episodes = await db_all(
            "SELECT episode_num FROM episodes WHERE movie_code=? ORDER BY episode_num LIMIT ?",
            (row["code"], EPISODES_PER_PAGE)
        )
        total_row = await db_one("SELECT COUNT(*) as c FROM episodes WHERE movie_code=?", (row["code"],))
        total = total_row["c"] if total_row else 0
        if not episodes:
            await bot.send_message(chat_id, get_text(lang, "serial_no_episodes"))
            return
        await bot.send_message(
            chat_id,
            f"📺 *{title}*",
            reply_markup=episodes_keyboard(episodes, row["code"], 0, total),
            parse_mode="MarkdownV2"
        )
    else:
        await db_exec("UPDATE movies SET request_count = request_count + 1 WHERE code=?", (row["code"],))
        await bot.send_video(
            chat_id, row["file_id"],
            caption=f"🎬 *{title}*",
            parse_mode="MarkdownV2"
        )


async def _show_dev_mode(msg, uid):
    movies = await db_all("SELECT type, title_uz, code, file_id FROM movies ORDER BY added_at DESC LIMIT 20")
    if not movies:
        await msg.reply_text("🔧 *Developer Mode*\n\nNo content yet.", parse_mode="Markdown")
        return
    lines = ["🔧 *Developer Mode — Content List*\n"]
    for m in movies:
        icon = "📺" if m["type"] == "serial" else "🎬"
        fid = m.get("file_id") or "(serial — no file_id)"
        lines.append(f"{icon} *{m['title_uz']}*\n🔑 `{m['code']}`\n📎 `{fid}`\n")
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    await msg.reply_text(text, parse_mode="Markdown")


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user)
    if not await user_has_lang(user.id):
        await update.message.reply_text(
            "🌐 Choose language / Tilni tanlang / Выберите язык:",
            reply_markup=lang_keyboard()
        )
    else:
        lang = await get_lang(user.id)
        await update.message.reply_text(
            get_text(lang, "welcome"),
            reply_markup=main_keyboard(lang),
            parse_mode="Markdown"
        )


async def cmd_setlang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌐 Choose language / Tilni tanlang / Выберите язык:",
        reply_markup=lang_keyboard()
    )


async def cmd_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = await get_lang(uid)
    start = time.time()
    msg = await update.message.reply_text("🏓 Pinging...")
    ms = round((time.time() - start) * 1000)
    await msg.edit_text(get_text(lang, "ping_reply", ms=ms), parse_mode="Markdown")


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = await get_lang(uid)
    if "states" in ctx.bot_data and uid in ctx.bot_data["states"]:
        del ctx.bot_data["states"][uid]
    await update.message.reply_text(get_text(lang, "cancelled"), reply_markup=main_keyboard(lang))


async def cmd_secret(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Matrix easter egg"""
    uid = update.effective_user.id
    lang = await get_lang(uid)
    user_row = await db_one("SELECT used_matrix FROM users WHERE user_id=?", (uid,))
    if user_row and user_row.get("used_matrix"):
        await update.message.reply_text(get_text(lang, "matrix_used"), parse_mode="Markdown")
        return
    from handlers.keyboards import matrix_keyboard
    await update.message.reply_text(
        get_text(lang, "matrix_msg"),
        reply_markup=matrix_keyboard(),
        parse_mode="Markdown"
    )


async def handle_group_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Bot added to group — say goodbye and leave"""
    if not update.my_chat_member:
        return
    chat = update.my_chat_member.chat
    new_status = update.my_chat_member.new_chat_member.status
    if chat.type in ["group", "supergroup"] and new_status in ["member", "administrator"]:
        try:
            await ctx.bot.send_message(
                chat.id,
                "🤖 Sorry, I'm not a group bot! I only work in private chats.\n\n"
                "🤖 Kechirasiz, men guruh boti emasman! Faqat shaxsiy chatda ishlayman.\n\n"
                "🤖 Извините, я не групповой бот! Работаю только в личных чатах."
            )
        except:
            pass
        try:
            await ctx.bot.leave_chat(chat.id)
        except:
            pass


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # Ignore group messages
    if msg.chat.type in ["group", "supergroup"]:
        return

    uid = msg.from_user.id
    text_in = msg.text.strip() if msg.text else ""

    # Init states
    if "states" not in ctx.bot_data:
        ctx.bot_data["states"] = {}
    state_obj = ctx.bot_data["states"].get(uid, {})
    state = state_obj.get("state")

    # ── Lang check FIRST ──
    if not await user_has_lang(uid) and not state:
        await msg.reply_text(
            "🌐 Choose language / Tilni tanlang / Выберите язык:",
            reply_markup=lang_keyboard()
        )
        return

    lang = await get_lang(uid)
    L = LANGS.get(lang, LANGS["uz"])

    # ── Temp ban check ──
    banned, remaining = is_temp_banned(uid)
    if banned:
        # Only warn if this is first message after ban (not every message)
        warned_key = f"ban_warned_{uid}"
        if not ctx.bot_data.get(warned_key):
            ctx.bot_data[warned_key] = True
            mins = remaining // 60
            secs = remaining % 60
            await msg.reply_text(
                f"🚫 You are temporarily banned for 10 minutes!\n"
                f"Try again in: {mins}m {secs}s"
            )
        return

    # ── Clear ban warned flag if ban expired ──
    if not is_temp_banned(uid)[0]:
        ctx.bot_data.pop(f"ban_warned_{uid}", None)

    # ── Flood check (skip for admins/owner) ──
    if not await is_admin(uid):
        is_flood, should_ban = check_message_flood(uid)
        if should_ban:
            await msg.reply_text(
                "🚫 *You have been temporarily banned for 10 minutes!*\n"
                "Reason: Excessive flooding.",
                parse_mode="Markdown"
            )
            return
        if is_flood:
            await msg.reply_text(get_text(lang, "flood_warning"))
            return

    # ── Dev mode code ──
    from config import DEV_MODE_CODE, OWNER_ID as _OWNER_ID
    if text_in == DEV_MODE_CODE:
        user_row = await db_one("SELECT used_konami FROM users WHERE user_id=?", (uid,))
        has_access = (uid == _OWNER_ID) or (user_row is not None and user_row.get("used_konami") == 1)
        if has_access:
            await _show_dev_mode(msg, uid)
        return

    # ── Konami code check ──
    if msg.text:
        progress = konami_progress.get(uid, 0)
        if text_in == KONAMI_SEQUENCE[progress]:
            konami_progress[uid] = progress + 1
            if konami_progress[uid] == len(KONAMI_SEQUENCE):
                konami_progress[uid] = 0
                user_row = await db_one("SELECT used_konami FROM users WHERE user_id=?", (uid,))
                if user_row and user_row.get("used_konami"):
                    await msg.reply_text(get_text(lang, "konami_used"), parse_mode="Markdown")
                else:
                    await db_exec("UPDATE users SET is_vip=1, used_konami=1 WHERE user_id=?", (uid,))
                    await msg.reply_text(get_text(lang, "konami_activated"), parse_mode="Markdown")
                return
        else:
            konami_progress[uid] = 1 if text_in == KONAMI_SEQUENCE[0] else 0

    # ── Secret bypass code ──
    if text_in == SECRET_BYPASS_CODE:
        user_row = await db_one("SELECT is_vip FROM users WHERE user_id=?", (uid,))
        if user_row and user_row.get("is_vip"):
            await msg.reply_text(get_text(lang, "bypass_already"), parse_mode="Markdown")
        else:
            await db_exec("UPDATE users SET is_vip=1 WHERE user_id=?", (uid,))
            await msg.reply_text(get_text(lang, "bypass_activated"), parse_mode="Markdown")
        return

    # ── Bottom keyboard buttons ──
    if text_in == L["btn_enter_code"]:
        ctx.bot_data["states"][uid] = {"state": "awaiting_direct_code"}
        await msg.reply_text(L["send_code_prompt"], reply_markup=cancel_keyboard())
        return

    if text_in == L["btn_search"]:
        ctx.bot_data["states"][uid] = {"state": "awaiting_search"}
        await msg.reply_text(L["send_search_query"], reply_markup=cancel_keyboard())
        return

    if text_in == L["btn_support"]:
        lang_key = f"support_message_{lang}"
        support_msg = await get_setting(lang_key) or await get_setting("support_message_uz")
        await msg.reply_text(support_msg if support_msg else get_text(lang, "support_not_set"))
        return

    if text_in == L["btn_language"]:
        await msg.reply_text(
            "🌐 Choose language / Tilni tanlang / Выберите язык:",
            reply_markup=lang_keyboard()
        )
        return

    # ── Admin states ──
    if state and state.startswith("admin_"):
        from handlers.admin import handle_admin_state
        await handle_admin_state(update, ctx, state, state_obj, text_in, lang)
        return

    # ── User states ──
    if state == "awaiting_direct_code":
        if not msg.text:
            return
        del ctx.bot_data["states"][uid]
        await _handle_code(msg, ctx, uid, text_in, lang)
        return

    elif state == "awaiting_search":
        if not msg.text:
            return
        del ctx.bot_data["states"][uid]
        await _do_search(msg, ctx, uid, text_in, lang)
        return

    # ── Direct text ──
    if msg.text and not msg.text.startswith("/"):
        await _handle_code_or_search(msg, ctx, uid, text_in, lang)


async def _handle_code(msg, ctx, uid, text_in, lang):
    not_joined_pub, not_joined_priv = await check_mandatory(ctx.bot, uid)
    if not_joined_pub or not_joined_priv:
        return await msg.reply_text(
            get_text(lang, "join_required"),
            reply_markup=join_keyboard(not_joined_pub, not_joined_priv)
        )
    row = await db_one("SELECT * FROM movies WHERE code=?", (text_in,))
    if not row:
        return await msg.reply_text(get_text(lang, "invalid_code"))
    await send_movie_or_serial(ctx.bot, msg.chat.id, row, lang)


async def _handle_code_or_search(msg, ctx, uid, text_in, lang):
    not_joined_pub, not_joined_priv = await check_mandatory(ctx.bot, uid)
    if not_joined_pub or not_joined_priv:
        return await msg.reply_text(
            get_text(lang, "join_required"),
            reply_markup=join_keyboard(not_joined_pub, not_joined_priv)
        )
    row = await db_one("SELECT * FROM movies WHERE code=?", (text_in,))
    if row:
        return await send_movie_or_serial(ctx.bot, msg.chat.id, row, lang)
    await _do_search(msg, ctx, uid, text_in, lang)


async def _do_search(msg, ctx, uid, text_in, lang):
    not_joined_pub, not_joined_priv = await check_mandatory(ctx.bot, uid)
    if not_joined_pub or not_joined_priv:
        return await msg.reply_text(
            get_text(lang, "join_required"),
            reply_markup=join_keyboard(not_joined_pub, not_joined_priv)
        )
    results = await db_all(
        "SELECT * FROM movies WHERE title_uz LIKE ? OR title_ru LIKE ? OR title_en LIKE ? ORDER BY title_uz LIMIT 10",
        (f"%{text_in}%", f"%{text_in}%", f"%{text_in}%")
    )
    if not results:
        return await msg.reply_text(get_text(lang, "search_not_found", query=text_in), parse_mode="Markdown")
    if len(results) == 1:
        await send_movie_or_serial(ctx.bot, msg.chat.id, results[0], lang)
    else:
        await msg.reply_text(
            get_text(lang, "search_results"),
            reply_markup=search_results_keyboard(results, lang),
            parse_mode="Markdown"
        )
