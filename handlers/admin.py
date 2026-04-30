import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

from db import db_one, db_all, db_exec, get_setting, set_setting, get_lang, is_admin, has_perm
from langs import get_text
from handlers.keyboards import (
    owner_keyboard, build_admin_keyboard, cancel_keyboard,
    add_content_type_keyboard, rename_lang_keyboard,
    delete_confirm_keyboard, movies_list_keyboard,
    perm_keyboard
)
from config import OWNER_ID

MOVIES_PER_PAGE = 8


async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await is_admin(uid):
        lang = await get_lang(uid)
        return await update.message.reply_text(get_text(lang, "not_admin"))
    if uid == OWNER_ID:
        await update.message.reply_text("⚙️ *Admin Panel*", reply_markup=owner_keyboard(), parse_mode="Markdown")
    else:
        row = await db_one("SELECT * FROM admins WHERE user_id=?", (uid,))
        await update.message.reply_text("⚙️ *Admin Panel*", reply_markup=build_admin_keyboard(row or {}), parse_mode="Markdown")


async def cb_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    action = query.data[4:]
    await query.answer()

    if "states" not in ctx.bot_data:
        ctx.bot_data["states"] = {}
    if uid in ctx.bot_data["states"]:
        del ctx.bot_data["states"][uid]

    if action.startswith("listmovies_"):
        page = int(action.split("_")[1])
        await _send_content_page(query.message, page, "movie")
        return

    if action.startswith("listserials_"):
        page = int(action.split("_")[1])
        await _send_content_page(query.message, page, "serial")
        return

    if action == "stats":
        total = (await db_one("SELECT COUNT(*) as c FROM users"))["c"]
        movies = (await db_one("SELECT COUNT(*) as c FROM movies WHERE type='movie'"))["c"]
        serials = (await db_one("SELECT COUNT(*) as c FROM movies WHERE type='serial'"))["c"]
        admins = (await db_one("SELECT COUNT(*) as c FROM admins"))["c"]
        uz = (await db_one("SELECT COUNT(*) as c FROM users WHERE lang='uz'"))["c"]
        ru = (await db_one("SELECT COUNT(*) as c FROM users WHERE lang='ru'"))["c"]
        en = (await db_one("SELECT COUNT(*) as c FROM users WHERE lang='en'"))["c"]
        blocked = (await db_one("SELECT COUNT(*) as c FROM users WHERE is_blocked=1"))["c"]
        vip = (await db_one("SELECT COUNT(*) as c FROM users WHERE is_vip=1"))["c"]
        top = await db_all("SELECT title_uz, request_count FROM movies ORDER BY request_count DESC LIMIT 3")
        top_text = "\n".join([f"  {i+1}. {r['title_uz']} ({r['request_count']}x)" for i, r in enumerate(top)]) or "  —"
        text = (
            f"📊 *Statistics*\n\n"
            f"👥 Total users: `{total}`\n"
            f"🇺🇿 Uzbek: `{uz}`\n"
            f"🇷🇺 Russian: `{ru}`\n"
            f"🇬🇧 English: `{en}`\n"
            f"🎬 Movies: `{movies}`\n"
            f"📺 Serials: `{serials}`\n"
            f"👤 Admins: `{admins}`\n"
            f"⭐️ VIP: `{vip}`\n"
            f"🚫 Blocked: `{blocked}`\n\n"
            f"🔥 *Top 3:*\n{top_text}"
        )
        await query.message.reply_text(text, parse_mode="Markdown")

    elif action == "listadmins":
        admin_rows = await db_all("SELECT * FROM admins")
        lines = [f"👑 *Owner:* `{OWNER_ID}`"]
        if admin_rows:
            lines.append("\n👥 *Admins:*")
            for a in admin_rows:
                user = await db_one("SELECT first_name, username FROM users WHERE user_id=?", (a["user_id"],))
                name = (user.get("first_name") or "") if user else ""
                if user and user.get("username"):
                    name += f" (@{user['username']})"
                if not name:
                    name = f"ID: {a['user_id']}"
                icons = "".join([
                    "🎬" if a.get("can_add_movie") else "",
                    "🗑" if a.get("can_delete_movie") else "",
                    "✏️" if a.get("can_change_title") else "",
                    "📢" if a.get("can_manage_channels") else "",
                    "👤" if a.get("can_manage_admins") else "",
                    "📣" if a.get("can_broadcast") else "",
                ])
                lines.append(f"• [{name}](tg://user?id={a['user_id']}) {icons}")
        else:
            lines.append("\nNo admins yet.")
        await query.message.reply_text("\n".join(lines), parse_mode="Markdown")

    elif action == "listchannels":
        rows = await db_all("SELECT * FROM mandatory_channels")
        if not rows:
            return await query.message.reply_text("No mandatory channels set.")
        lines = ["📢 *Mandatory Channels:*\n"]
        for r in rows:
            icon = "🔒" if r.get("is_private") else "📢"
            lines.append(f"{icon} @{r['channel_username']}")
        await query.message.reply_text("\n".join(lines), parse_mode="Markdown")

    elif action == "addcontent":
        if not await has_perm(uid, "can_add_movie"):
            return await query.message.reply_text("🚫 No permission.")
        await query.message.reply_text("🎬 What are you adding?", reply_markup=add_content_type_keyboard())

    elif action == "addepisode":
        if not await has_perm(uid, "can_add_movie"):
            return await query.message.reply_text("🚫 No permission.")
        ctx.bot_data["states"][uid] = {"state": "admin_awaiting_episode_code"}
        await query.message.reply_text("📺 Send the serial code:\n\n/cancel to stop", reply_markup=cancel_keyboard())

    elif action == "delmovie":
        if not await has_perm(uid, "can_delete_movie"):
            return await query.message.reply_text("🚫 No permission.")
        ctx.bot_data["states"][uid] = {"state": "admin_awaiting_delete_code"}
        await query.message.reply_text("🗑 Send the code to delete:\n\n/cancel to stop", reply_markup=cancel_keyboard())

    elif action == "changetitle":
        if not await has_perm(uid, "can_change_title"):
            return await query.message.reply_text("🚫 No permission.")
        ctx.bot_data["states"][uid] = {"state": "admin_awaiting_rename_code"}
        await query.message.reply_text("✏️ Send the code to rename:\n\n/cancel to stop", reply_markup=cancel_keyboard())

    elif action == "addchannel":
        if not await has_perm(uid, "can_manage_channels"):
            return await query.message.reply_text("🚫 No permission.")
        ctx.bot_data["states"][uid] = {"state": "admin_awaiting_add_channel", "data": {"is_private": False}}
        await query.message.reply_text(
            "📢 Send channel username (without @):\n⚠️ Bot must be admin in that channel!\n\n/cancel to stop",
            reply_markup=cancel_keyboard()
        )

    elif action == "removechannel":
        if not await has_perm(uid, "can_manage_channels"):
            return await query.message.reply_text("🚫 No permission.")
        ctx.bot_data["states"][uid] = {"state": "admin_awaiting_rm_channel"}
        await query.message.reply_text("❌ Send channel username to remove (without @):\n\n/cancel to stop", reply_markup=cancel_keyboard())

    elif action == "addadmin":
        if not await has_perm(uid, "can_manage_admins"):
            return await query.message.reply_text("🚫 No permission.")
        ctx.bot_data["states"][uid] = {"state": "admin_awaiting_new_admin"}
        await query.message.reply_text("👤 Send user ID:\n\n/cancel to stop", reply_markup=cancel_keyboard())

    elif action == "removeadmin":
        if not await has_perm(uid, "can_manage_admins"):
            return await query.message.reply_text("🚫 No permission.")
        ctx.bot_data["states"][uid] = {"state": "admin_awaiting_rm_admin"}
        await query.message.reply_text("🗑 Send admin ID to remove:\n\n/cancel to stop", reply_markup=cancel_keyboard())

    elif action == "broadcast":
        if not await has_perm(uid, "can_broadcast"):
            return await query.message.reply_text("🚫 No permission.")
        ctx.bot_data["states"][uid] = {"state": "admin_awaiting_broadcast"}
        await query.message.reply_text("📢 Send the broadcast message:\n\n/cancel to stop", reply_markup=cancel_keyboard())

    elif action == "setsupport":
        ctx.bot_data["states"][uid] = {"state": "admin_awaiting_support_uz"}
        await query.message.reply_text(
            "📝 Step 1/3: Send *Uzbek* support message:\n\n/cancel to stop",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown"
        )


async def cb_addtype(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    content_type = query.data.split("_")[1]
    await query.answer()
    if "states" not in ctx.bot_data:
        ctx.bot_data["states"] = {}
    if content_type == "serial":
        # Serial: just ask for titles and code, no video
        ctx.bot_data["states"][uid] = {"state": "admin_awaiting_title_uz", "data": {"type": "serial"}}
        await query.edit_message_text(
            "📺 *New Serial*\n\n"
            "🇺🇿 Step 1/3: Send *Uzbek* title:\n\n/cancel to stop",
            parse_mode="Markdown"
        )
    else:
        ctx.bot_data["states"][uid] = {"state": "admin_awaiting_video", "data": {"type": "movie"}}
        await query.edit_message_text("🎬 *New Movie*\n\nSend the video file:\n\n/cancel to stop", parse_mode="Markdown")


async def cb_chantype(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    chan_type = query.data.split("_")[1]
    await query.answer()
    if "states" not in ctx.bot_data:
        ctx.bot_data["states"] = {}
    ctx.bot_data["states"][uid] = {"state": "admin_awaiting_add_channel", "data": {"is_private": chan_type == "private"}}
    if chan_type == "private":
        await query.edit_message_text("🔒 Send private channel username (without @):\n⚠️ Bot must be admin!\n\n/cancel to stop")
    else:
        await query.edit_message_text("📢 Send public channel username (without @):\n⚠️ Bot must be admin!\n\n/cancel to stop")


async def cb_renamelang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    choice = query.data.split("_")[1]
    if "states" not in ctx.bot_data:
        ctx.bot_data["states"] = {}
    state_obj = ctx.bot_data["states"].get(uid, {})
    if state_obj.get("state") != "admin_awaiting_new_title_lang":
        await query.answer()
        return
    await query.answer()
    if choice == "all":
        ctx.bot_data["states"][uid]["state"] = "admin_awaiting_new_title_uz"
        ctx.bot_data["states"][uid]["data"]["rename_all"] = True
        await query.edit_message_text("🇺🇿 Send new Uzbek title:\n\n/cancel to stop")
    elif choice == "uz":
        ctx.bot_data["states"][uid]["state"] = "admin_awaiting_new_title_uz"
        ctx.bot_data["states"][uid]["data"]["rename_all"] = False
        await query.edit_message_text("🇺🇿 Send new Uzbek title:\n\n/cancel to stop")
    elif choice == "ru":
        ctx.bot_data["states"][uid]["state"] = "admin_awaiting_new_title_ru_only"
        await query.edit_message_text("🇷🇺 Send new Russian title:\n\n/cancel to stop")
    elif choice == "en":
        ctx.bot_data["states"][uid]["state"] = "admin_awaiting_new_title_en_only"
        await query.edit_message_text("🇬🇧 Send new English title:\n\n/cancel to stop")


async def cb_confirm_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    code = query.data.split("_", 1)[1]
    await db_exec("DELETE FROM episodes WHERE movie_code=?", (code,))
    await db_exec("DELETE FROM movies WHERE code=?", (code,))
    await query.answer("✅ Deleted!")
    await query.edit_message_text("✅ Deleted successfully.")


async def cb_perm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "perm_done":
        await query.answer("✅ Saved!")
        await query.edit_message_reply_markup(reply_markup=None)
        return
    parts = query.data.split("_")
    target_id = int(parts[1])
    perm = "_".join(parts[2:-1])
    val = int(parts[-1])
    await db_exec(f"UPDATE admins SET {perm}=? WHERE user_id=?", (val, target_id))
    await query.answer("✅ Updated!")
    row = await db_one("SELECT * FROM admins WHERE user_id=?", (target_id,))
    await query.edit_message_reply_markup(reply_markup=perm_keyboard(target_id, row or {}))


async def cb_moviepage(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    page = int(query.data.split("_")[1])
    await query.answer()
    await _send_content_page(query.message, page, "movie", edit=True, original_query=query)


async def handle_admin_state(update, ctx, state, state_obj, text_in, lang):
    msg = update.message
    uid = msg.from_user.id
    states = ctx.bot_data["states"]

    # ── Add video ──
    if state == "admin_awaiting_video":
        if msg.video or msg.document:
            file_id = msg.video.file_id if msg.video else msg.document.file_id
            states[uid]["data"]["file_id"] = file_id
            states[uid]["state"] = "admin_awaiting_title_uz"
            content_type = states[uid]["data"].get("type", "movie")
            label = "Movie 🎬" if content_type == "movie" else "Serial 📺"
            await msg.reply_text(
                f"✅ Video received!\n\n🇺🇿 Step 1/3: Send *Uzbek* title for this {label}:\n\n/cancel to stop",
                reply_markup=cancel_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await msg.reply_text("🎬 Send video file:\n\n/cancel to stop", reply_markup=cancel_keyboard())
        return

    # ── Titles: 3 steps ──
    elif state == "admin_awaiting_title_uz":
        if not msg.text: return
        states[uid]["data"]["title_uz"] = text_in
        states[uid]["state"] = "admin_awaiting_title_ru"
        await msg.reply_text("🇷🇺 Step 2/3: Send *Russian* title:\n\n/cancel to stop", reply_markup=cancel_keyboard(), parse_mode="Markdown")
        return

    elif state == "admin_awaiting_title_ru":
        if not msg.text: return
        states[uid]["data"]["title_ru"] = text_in
        states[uid]["state"] = "admin_awaiting_title_en"
        await msg.reply_text("🇬🇧 Step 3/3: Send *English* title:\n\n/cancel to stop", reply_markup=cancel_keyboard(), parse_mode="Markdown")
        return

    elif state == "admin_awaiting_title_en":
        if not msg.text: return
        states[uid]["data"]["title_en"] = text_in
        states[uid]["state"] = "admin_awaiting_code"
        await msg.reply_text("🔑 Send a unique code:\n\n/cancel to stop", reply_markup=cancel_keyboard())
        return

    # ── Code ──
    elif state == "admin_awaiting_code":
        if not msg.text: return
        if await db_one("SELECT 1 FROM movies WHERE code=?", (text_in,)):
            await msg.reply_text("⚠️ Code already taken! Try another:", reply_markup=cancel_keyboard())
            return
        data = states[uid]["data"]
        content_type = data.get("type", "movie")
        await db_exec(
            "INSERT INTO movies (type, title_uz, title_ru, title_en, file_id, code, added_by) VALUES (?,?,?,?,?,?,?)",
            (content_type, data["title_uz"], data["title_ru"], data.get("title_en", data["title_uz"]), data.get("file_id"), text_in, uid)
        )
        del states[uid]
        key = "serial_added" if content_type == "serial" else "movie_added"
        await msg.reply_text(
            get_text(lang, key, title_uz=data["title_uz"], title_ru=data["title_ru"], title_en=data.get("title_en", ""), code=text_in),
            parse_mode="Markdown"
        )
        return

    # ── Add episode ──
    elif state == "admin_awaiting_episode_code":
        if not msg.text: return
        row = await db_one("SELECT * FROM movies WHERE code=? AND type='serial'", (text_in,))
        if not row:
            await msg.reply_text("❌ Serial not found.", reply_markup=cancel_keyboard())
            return
        last = await db_one("SELECT MAX(episode_num) as last FROM episodes WHERE movie_code=?", (text_in,))
        next_ep = (last["last"] or 0) + 1
        states[uid] = {"state": "admin_awaiting_episode_video", "data": {"serial_code": text_in, "episode_num": next_ep}}
        await msg.reply_text(
            f"📺 *{row['title_uz']}*\n\n▶️ Next episode: *{next_ep}*\nSend the video file:\n\n/cancel to stop",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown"
        )
        return

    elif state == "admin_awaiting_episode_video":
        if msg.video or msg.document:
            serial_code = states[uid]["data"]["serial_code"]
            ep_num = states[uid]["data"]["episode_num"]
            file_id = msg.video.file_id if msg.video else msg.document.file_id
            await db_exec(
                "INSERT OR REPLACE INTO episodes (movie_code, episode_num, file_id) VALUES (?,?,?)",
                (serial_code, ep_num, file_id)
            )
            # Ask for next episode or done
            del states[uid]
            last = await db_one("SELECT COUNT(*) as c FROM episodes WHERE movie_code=?", (serial_code,))
            total = last["c"] if last else ep_num
            await msg.reply_text(
                f"✅ Episode {ep_num} added! (Total: {total})\n\nTo add more episodes, press 📺 Add Episode again."
            )
        else:
            await msg.reply_text("🎬 Send video file:\n\n/cancel to stop", reply_markup=cancel_keyboard())
        return

    # ── Delete ──
    elif state == "admin_awaiting_delete_code":
        if not msg.text: return
        row = await db_one("SELECT title_uz, title_ru, type FROM movies WHERE code=?", (text_in,))
        if not row:
            await msg.reply_text("❌ Not found.", reply_markup=cancel_keyboard())
        else:
            title = f"{row['title_uz']} / {row['title_ru']}"
            del states[uid]
            if row.get("type") == "serial":
                from handlers.keyboards import serial_delete_keyboard
                await msg.reply_text(
                    f"📺 *{title}*\n\nWhat do you want to delete?",
                    reply_markup=serial_delete_keyboard(text_in),
                    parse_mode="Markdown"
                )
            else:
                await msg.reply_text(
                    get_text(lang, "delete_confirm", title=title),
                    reply_markup=delete_confirm_keyboard(text_in),
                    parse_mode="Markdown"
                )
        return

    # ── Rename ──
    elif state == "admin_awaiting_rename_code":
        if not msg.text: return
        if not await db_one("SELECT 1 FROM movies WHERE code=?", (text_in,)):
            await msg.reply_text("❌ Not found.", reply_markup=cancel_keyboard())
            return
        states[uid] = {"state": "admin_awaiting_new_title_lang", "data": {"code": text_in}}
        await msg.reply_text("🌐 Which title(s) to change?", reply_markup=rename_lang_keyboard())
        return

    elif state == "admin_awaiting_new_title_uz":
        if not msg.text: return
        code = states[uid]["data"]["code"]
        await db_exec("UPDATE movies SET title_uz=? WHERE code=?", (text_in, code))
        if states[uid]["data"].get("rename_all"):
            states[uid]["state"] = "admin_awaiting_new_title_ru"
            await msg.reply_text("🇷🇺 Now Russian title:\n\n/cancel to stop", reply_markup=cancel_keyboard())
        else:
            del states[uid]
            await msg.reply_text("✅ Title updated.")
        return

    elif state == "admin_awaiting_new_title_ru":
        if not msg.text: return
        code = states[uid]["data"]["code"]
        await db_exec("UPDATE movies SET title_ru=? WHERE code=?", (text_in, code))
        if states[uid]["data"].get("rename_all"):
            states[uid]["state"] = "admin_awaiting_new_title_en"
            await msg.reply_text("🇬🇧 Now English title:\n\n/cancel to stop", reply_markup=cancel_keyboard())
        else:
            del states[uid]
            await msg.reply_text("✅ Title updated.")
        return

    elif state == "admin_awaiting_new_title_en":
        if not msg.text: return
        code = states[uid]["data"]["code"]
        await db_exec("UPDATE movies SET title_en=? WHERE code=?", (text_in, code))
        del states[uid]
        await msg.reply_text("✅ All titles updated.")
        return

    elif state == "admin_awaiting_new_title_ru_only":
        if not msg.text: return
        code = states[uid]["data"]["code"]
        await db_exec("UPDATE movies SET title_ru=? WHERE code=?", (text_in, code))
        del states[uid]
        await msg.reply_text("✅ Russian title updated.")
        return

    elif state == "admin_awaiting_new_title_en_only":
        if not msg.text: return
        code = states[uid]["data"]["code"]
        await db_exec("UPDATE movies SET title_en=? WHERE code=?", (text_in, code))
        del states[uid]
        await msg.reply_text("✅ English title updated.")
        return

    # ── Private channel ID/username ──
    elif state == "admin_awaiting_private_channel_id":
        if not msg.text: return
        chan_input = text_in.strip()
        # Try as ID first, then as username
        try:
            chat_id = int(chan_input)
            chat_identifier = chat_id
        except ValueError:
            chat_identifier = f"@{chan_input.lstrip('@')}"
        try:
            bot_member = await ctx.bot.get_chat_member(chat_identifier, ctx.bot.id)
            if bot_member.status not in ["administrator", "creator"]:
                await msg.reply_text("❌ Bot is not admin in that channel.", reply_markup=cancel_keyboard())
                return
            chat = await ctx.bot.get_chat(chat_identifier)
            display_name = chat.username or str(chat.id)
        except Exception as e:
            await msg.reply_text(f"❌ Channel not found or bot is not admin.\nError: {e}", reply_markup=cancel_keyboard())
            return
        states[uid]["data"]["channel_id"] = str(chat_identifier)
        states[uid]["data"]["display_name"] = display_name
        states[uid]["state"] = "admin_awaiting_invite_link"
        await msg.reply_text(
            f"✅ Channel found: *{display_name}*\n\n🔗 Now send the invite link for users to join:\n\n/cancel to stop",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown"
        )
        return

    # ── Channels ──
    elif state == "admin_awaiting_add_channel":
        if not msg.text: return
        username = text_in.lstrip("@")
        is_private = states[uid]["data"].get("is_private", False)
        try:
            bot_member = await ctx.bot.get_chat_member(f"@{username}", ctx.bot.id)
            if bot_member.status not in ["administrator", "creator"]:
                await msg.reply_text(f"❌ Bot is not admin in @{username}.", reply_markup=cancel_keyboard())
                return
        except:
            await msg.reply_text("❌ Channel not found.", reply_markup=cancel_keyboard())
            return
        if is_private:
            states[uid]["data"]["username"] = username
            states[uid]["state"] = "admin_awaiting_invite_link"
            await msg.reply_text("🔗 Now send the invite link:\n\n/cancel to stop", reply_markup=cancel_keyboard())
        else:
            await db_exec("INSERT OR IGNORE INTO mandatory_channels (channel_username, is_private) VALUES (?,0)", (username,))
            del states[uid]
            await msg.reply_text(f"✅ Public channel @{username} added.")
        return

    elif state == "admin_awaiting_invite_link":
        if not msg.text: return
        channel_id = states[uid]["data"].get("channel_id", states[uid]["data"].get("username", "unknown"))
        display_name = states[uid]["data"].get("display_name", channel_id)
        await db_exec(
            "INSERT OR IGNORE INTO mandatory_channels (channel_username, is_private, invite_link) VALUES (?,1,?)",
            (str(channel_id), text_in)
        )
        del states[uid]
        await msg.reply_text(f"✅ Private channel *{display_name}* added with invite link.", parse_mode="Markdown")
        return

    elif state == "admin_awaiting_rm_channel":
        if not msg.text: return
        username = text_in.lstrip("@")
        await db_exec("DELETE FROM mandatory_channels WHERE channel_username=?", (username,))
        del states[uid]
        await msg.reply_text("✅ Channel removed.")
        return

    # ── Admins ──
    elif state == "admin_awaiting_new_admin":
        if not msg.text: return
        try:
            target_id = int(text_in)
        except ValueError:
            await msg.reply_text("⚠️ Invalid ID. Numbers only.", reply_markup=cancel_keyboard())
            return
        if target_id == OWNER_ID:
            await msg.reply_text("🚫 Cannot add owner.")
            return
        await db_exec(
            "INSERT OR IGNORE INTO admins (user_id, can_add_movie, can_delete_movie, can_change_title, can_manage_channels, can_manage_admins, can_broadcast) VALUES (?,0,0,0,0,0,0)",
            (target_id,)
        )
        del states[uid]
        row = await db_one("SELECT * FROM admins WHERE user_id=?", (target_id,))
        await msg.reply_text("✅ Admin added. Set permissions:", reply_markup=perm_keyboard(target_id, row or {}))
        return

    elif state == "admin_awaiting_rm_admin":
        if not msg.text: return
        try:
            target_id = int(text_in)
        except ValueError:
            await msg.reply_text("⚠️ Invalid ID.", reply_markup=cancel_keyboard())
            return
        if target_id == OWNER_ID:
            await msg.reply_text("🚫 Cannot remove owner.")
            return
        await db_exec("DELETE FROM admins WHERE user_id=?", (target_id,))
        del states[uid]
        await msg.reply_text("✅ Admin removed.")
        return

    # ── Broadcast ──
    elif state == "admin_awaiting_broadcast":
        del states[uid]
        all_users = await db_all("SELECT user_id FROM users WHERE is_blocked=0")
        count = 0
        for u in all_users:
            try:
                await ctx.bot.copy_message(
                    chat_id=u["user_id"],
                    from_chat_id=msg.chat.id,
                    message_id=msg.message_id
                )
                count += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                err = str(e).lower()
                if "blocked" in err or "deactivated" in err or "not found" in err:
                    await db_exec("UPDATE users SET is_blocked=1 WHERE user_id=?", (u["user_id"],))
        await msg.reply_text(get_text(lang, "broadcast_done", count=count))
        return

    # ── Support (3 languages) ──
    elif state == "admin_awaiting_support_uz":
        if not msg.text: return
        states[uid] = {"state": "admin_awaiting_support_ru", "data": {"uz": text_in}}
        await msg.reply_text("📝 Step 2/3: Send *Russian* support message:\n\n/cancel to stop", reply_markup=cancel_keyboard(), parse_mode="Markdown")
        return

    elif state == "admin_awaiting_support_ru":
        if not msg.text: return
        states[uid]["data"]["ru"] = text_in
        states[uid]["state"] = "admin_awaiting_support_en"
        await msg.reply_text("📝 Step 3/3: Send *English* support message:\n\n/cancel to stop", reply_markup=cancel_keyboard(), parse_mode="Markdown")
        return

    elif state == "admin_awaiting_support_en":
        if not msg.text: return
        await set_setting("support_message_uz", states[uid]["data"]["uz"])
        await set_setting("support_message_ru", states[uid]["data"]["ru"])
        await set_setting("support_message_en", text_in)
        del states[uid]
        await msg.reply_text("✅ Support messages saved!\n🇺🇿 Uzbek ✅\n🇷🇺 Russian ✅\n🇬🇧 English ✅")
        return


async def _send_content_page(target, page, content_type="movie", edit=False, original_query=None):
    total_row = await db_one("SELECT COUNT(*) as c FROM movies WHERE type=?", (content_type,))
    total = total_row["c"] if total_row else 0
    if total == 0:
        await target.reply_text(f"No {'movies' if content_type == 'movie' else 'serials'} yet.")
        return
    rows = await db_all(
        "SELECT title_uz, title_ru, title_en, code FROM movies WHERE type=? ORDER BY added_at DESC LIMIT ? OFFSET ?",
        (content_type, MOVIES_PER_PAGE, page * MOVIES_PER_PAGE)
    )
    total_pages = (total + MOVIES_PER_PAGE - 1) // MOVIES_PER_PAGE
    icon = "📺" if content_type == "serial" else "🎬"
    text = f"{icon} *{'Serials' if content_type == 'serial' else 'Movies'}* (Page {page + 1}/{total_pages}, Total: {total})\n\n"
    for r in rows:
        text += f"• 🇺🇿 {r['title_uz']} | 🇷🇺 {r['title_ru']} | 🇬🇧 {r.get('title_en', '—')} — `{r['code']}`\n"
    kb = movies_list_keyboard(page, total)
    if edit and original_query:
        await original_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await target.reply_text(text, reply_markup=kb, parse_mode="Markdown")
