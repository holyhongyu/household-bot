"""
/start  - registers the user calling it (by Telegram ID) as a household member
/help   - lists available commands
/chatid - prints the current chat's ID, used once during setup to fill
          GROUP_CHAT_ID in .env (not required for the bot to function,
          just convenient for the user to know it)
"""
from telegram import Update
from telegram.ext import ContextTypes

from database.crud import get_or_create_user, get_all_users

HELP_TEXT = (
    "🏠 *Household Bot*\n\n"
    "*Tasks*\n"
    "/task - create a new task\n"
    "/today - see today's overview (tasks + reminders due today/tomorrow)\n"
    "/done <keyword> - mark a task complete\n"
    "\n*Reminders*\n"
    "/reminder - set a reminder\n"
    "/reminders - see all active reminders\n"
    "\n*Food Places*\n"
    "/food - add a food place recommendation\n"
    "/foodlist - see all saved food places\n"
    "\n*Other*\n"
    "/delete - delete tasks, reminders, or food places\n"
    "/help - show this message\n"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    user = get_or_create_user(
        telegram_id=tg_user.id,
        display_name=tg_user.first_name or "User",
    )

    existing = get_all_users()
    if len(existing) == 1:
        msg = (
            f"👋 Welcome, {user.display_name}! You're registered.\n\n"
            "Have your partner run /start here too, then you're both set up."
        )
    else:
        msg = f"👋 Welcome back, {user.display_name}! Household has {len(existing)} members registered."

    await update.message.reply_text(msg)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"This chat's ID is: `{update.effective_chat.id}`", parse_mode="Markdown")
