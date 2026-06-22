"""
Entry point. Run with: python bot.py

Sets up the database, registers all command/conversation handlers, starts
the reminder scheduler, then runs polling (no public URL needed).
"""
import logging
import time

from telegram.ext import Application, CommandHandler

from config import BOT_TOKEN, GROUP_CHAT_ID
from database.session import init_db
from handlers.start import start, help_command, chatid
from handlers.task import task_conversation, today, done
from handlers.reminder import reminder_conversation, list_reminders
from handlers.food import food_conversation, list_food
from handlers.delete import delete_conversation
from scheduler.jobs import start_scheduler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    """Runs once after the bot starts - good place to kick off the scheduler."""
    start_scheduler(application)
    logger.info("Reminder scheduler started.")

    # Because drop_pending_updates=True discards anything sent while the
    # bot was offline (see run_polling below), people have no way to tell
    # whether a /task or /reminder they sent actually went through. This
    # message closes that gap: it tells them explicitly to resend, rather
    # than leaving them guessing why nothing happened.
    if GROUP_CHAT_ID:
        try:
            await application.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text="👋 I'm back online. If you sent /task, /reminder, or "
                     "anything else while I was offline, please send it again.",
            )
        except Exception:
            logger.exception("Couldn't send the back-online notice to the group.")


def build_app() -> Application:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        # How long the underlying HTTP client waits for a long-poll
        # response to actually arrive before raising a timeout and
        # retrying. Setting this explicitly (rather than relying on
        # defaults) ensures a half-dead connection gets torn down and
        # retried instead of silently hanging.
        .get_updates_read_timeout(40)
        .get_updates_connect_timeout(15)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("chatid", chatid))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("reminders", list_reminders))
    app.add_handler(CommandHandler("foodlist", list_food))
    app.add_handler(task_conversation)
    app.add_handler(reminder_conversation)
    app.add_handler(food_conversation)
    app.add_handler(delete_conversation)
    return app


def main():
    init_db()
    logger.info("Database ready.")

    # If the process gets killed/crashes unexpectedly (network blip, laptop
    # sleep/wake, etc.), restart the whole polling loop rather than dying
    # silently. This is a coarse safety net - Railway's process manager
    # would also restart a crashed process, but this keeps local runs
    # resilient too, and avoids relying solely on a separate supervisor.
    while True:
        try:
            app = build_app()
            logger.info("Bot starting (polling mode)...")
            app.run_polling(
                allowed_updates=["message", "callback_query"],
                # How long a single long-poll request waits for a reply
                # from Telegram before giving up and retrying. Too short
                # wastes requests; too long makes a dead connection look
                # alive for a long time before anything notices.
                timeout=30,
                # Discard any updates that piled up while the bot wasn't
                # running, instead of replaying a backlog all at once on
                # startup (which is what caused the "skipped buttons"
                # behaviour we saw during testing).
                drop_pending_updates=True,
            )
        except KeyboardInterrupt:
            logger.info("Stopped by user (Ctrl+C).")
            break
        except Exception:
            logger.exception("Bot crashed unexpectedly. Restarting in 10 seconds...")
            time.sleep(10)
            continue
        else:
            # run_polling returned normally (e.g. clean shutdown) - don't loop forever.
            break


if __name__ == "__main__":
    main()

