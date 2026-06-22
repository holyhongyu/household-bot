"""
/summary - sends two messages:
  1. /today output + all active reminders
  2. food places + recipes
"""
from telegram import Update
from telegram.ext import ContextTypes

from handlers.task import build_today_message
from handlers.reminder import build_reminders_text
from handlers.food import build_foodlist_text
from handlers.recipe import build_recipes_text


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg1 = build_today_message() + "\n\n" + build_reminders_text()
    msg2 = build_foodlist_text() + "\n\n" + build_recipes_text()
    await update.message.reply_text(msg1, parse_mode="Markdown")
    await update.message.reply_text(msg2, parse_mode="Markdown")
