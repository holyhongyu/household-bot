"""
/food - guided conversation to log a food place recommendation:
  name -> cuisine -> map link/address -> save
"""
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, filters,
)

from database.crud import get_or_create_user, create_food_place, get_all_food_places

ASK_NAME, ASK_CUISINE, ASK_MAP = range(3)


async def food_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("🍽️ *Add a Food Place*\nWhat is the name of the place?", parse_mode="Markdown")
    return ASK_NAME


async def food_got_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["food_name"] = update.message.text.strip()
    await update.message.reply_text("What kind of food/cuisine is it? (e.g. brunch, Japanese, Italian)")
    return ASK_CUISINE


async def food_got_cuisine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["food_cuisine"] = update.message.text.strip()
    await update.message.reply_text("What is the Google Maps link or address? (or type `skip` to leave blank)")
    return ASK_MAP


async def food_got_map(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    map_link = None if text.lower() == "skip" else text

    tg_user = update.effective_user
    try:
        user = get_or_create_user(telegram_id=tg_user.id, display_name=tg_user.first_name or "User")
        place = create_food_place(
            name=context.user_data["food_name"],
            cuisine=context.user_data["food_cuisine"],
            map_link=map_link,
            added_by_id=user.id,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Something went wrong saving the place: {e}")
        context.user_data.clear()
        return ConversationHandler.END

    map_line = f"\n📍 {place.map_link}" if place.map_link else ""
    await update.message.reply_text(
        f"✅ *Added!*\n🍽️ {place.name}\n🥘 {place.cuisine}{map_line}",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


async def food_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Cancelled.")
    context.user_data.clear()
    return ConversationHandler.END


def build_foodlist_text() -> str:
    places = get_all_food_places()
    if not places:
        return "🍽️ *Food Places*\n_No food places saved yet._"
    lines = ["🍽️ *Food Places*"]
    for p in places:
        map_part = f"\n  📍 {p.map_link}" if p.map_link else ""
        lines.append(f"\n• *{p.name}* — {p.cuisine}{map_part}")
    return "\n".join(lines)


async def list_food(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_foodlist_text(), parse_mode="Markdown")


food_conversation = ConversationHandler(
    entry_points=[CommandHandler("food", food_start)],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, food_got_name)],
        ASK_CUISINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, food_got_cuisine)],
        ASK_MAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, food_got_map)],
    },
    fallbacks=[CommandHandler("cancel", food_cancel)],
    per_user=True,
    per_chat=True,
)
