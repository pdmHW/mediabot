import logging
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ChatMemberHandler, filters
)
from config import BOT_TOKEN, SECRET_COMMAND
from db import init_db

from handlers.user import cmd_start, cmd_setlang, cmd_ping, cmd_cancel, cmd_secret, handle_message, handle_group_join
from handlers.admin import (
    cmd_admin, cb_admin, cb_addtype, cb_chantype,
    cb_renamelang, cb_confirm_delete, cb_perm, cb_moviepage
)
from handlers.callbacks import (
    cb_noop, cb_cancel, cb_lang, cb_get,
    cb_episode, cb_eppage, cb_checkjoin, cb_matrix,
    cb_delep, cb_confirmdepep
)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


async def error_handler(update, ctx):
    err = str(ctx.error)
    ignored = ["Query is too old", "Bad Gateway", "Message is not modified", "Timed out", "ConnectTimeout"]
    if any(e in err for e in ignored):
        return
    logging.warning(f"⚠️ Error: {ctx.error}")


def main():
    async def post_init(app):
        await init_db()
        logging.warning("✅ MediaBot v2 started!")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("setlang", cmd_setlang))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler(SECRET_COMMAND, cmd_secret))

    app.add_handler(CallbackQueryHandler(cb_noop, pattern="^noop$"))
    app.add_handler(CallbackQueryHandler(cb_cancel, pattern="^cancel$"))
    app.add_handler(CallbackQueryHandler(cb_lang, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(cb_perm, pattern="^perm_"))
    app.add_handler(CallbackQueryHandler(cb_admin, pattern="^adm_"))
    app.add_handler(CallbackQueryHandler(cb_addtype, pattern="^addtype_"))
    app.add_handler(CallbackQueryHandler(cb_chantype, pattern="^chantype_"))
    app.add_handler(CallbackQueryHandler(cb_renamelang, pattern="^renamelang_"))
    app.add_handler(CallbackQueryHandler(cb_confirm_delete, pattern="^confirmdelete_"))
    app.add_handler(CallbackQueryHandler(cb_moviepage, pattern="^moviepage_"))
    app.add_handler(CallbackQueryHandler(cb_get, pattern="^get_"))
    app.add_handler(CallbackQueryHandler(cb_episode, pattern="^ep_"))
    app.add_handler(CallbackQueryHandler(cb_eppage, pattern="^eppage_"))
    app.add_handler(CallbackQueryHandler(cb_checkjoin, pattern="^checkjoin$"))
    app.add_handler(CallbackQueryHandler(cb_matrix, pattern="^matrix_"))
    app.add_handler(CallbackQueryHandler(cb_delep, pattern="^delep_"))
    app.add_handler(CallbackQueryHandler(cb_confirmdepep, pattern="^confirmdepep_"))

    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    app.add_handler(ChatMemberHandler(handle_group_join, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_error_handler(error_handler)

    app.run_polling()


if __name__ == "__main__":
    main()
