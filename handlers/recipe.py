"""
/recipe  - guided conversation: name -> tag -> description/link -> save
/recipes - list all saved recipes grouped by tag
"""
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters,
)

from database.crud import get_or_create_user, create_recipe, get_all_recipes
from keyboards import recipe_tag_keyboard, BUILTIN_TAGS

ASK_NAME, ASK_TAG, ASK_CUSTOM_TAG, ASK_DESC = range(4)

_TAG_EMOJI = {"Main Meal": "🥘", "Snack": "🍿", "Drink": "☕"}


def _tag_emoji(tag: str) -> str:
    return _TAG_EMOJI.get(tag, "🏷️")


async def recipe_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("📖 *Add a Recipe*\nWhat is the name of the recipe?", parse_mode="Markdown")
    return ASK_NAME


async def recipe_got_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["recipe_name"] = update.message.text.strip()
    await update.message.reply_text("What kind of recipe is it?", reply_markup=recipe_tag_keyboard())
    return ASK_TAG


async def recipe_got_tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    tag = query.data.split(":", 1)[1]

    if tag == "__custom__":
        await query.edit_message_text("Type your custom tag:")
        return ASK_CUSTOM_TAG

    context.user_data["recipe_tag"] = tag
    await query.edit_message_text(
        "Add a description or link (or type `skip` to leave blank):",
        parse_mode="Markdown",
    )
    return ASK_DESC


async def recipe_got_custom_tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["recipe_tag"] = update.message.text.strip()
    await update.message.reply_text(
        "Add a description or link (or type `skip` to leave blank):",
        parse_mode="Markdown",
    )
    return ASK_DESC


async def recipe_got_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    link_or_desc = None if text.lower() == "skip" else text

    tg_user = update.effective_user
    try:
        user = get_or_create_user(telegram_id=tg_user.id, display_name=tg_user.first_name or "User")
        recipe = create_recipe(
            name=context.user_data["recipe_name"],
            tag=context.user_data["recipe_tag"],
            link_or_desc=link_or_desc,
            added_by_id=user.id,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Something went wrong saving the recipe: {e}")
        context.user_data.clear()
        return ConversationHandler.END

    extra = f"\n🔗 {recipe.link_or_desc}" if recipe.link_or_desc else ""
    await update.message.reply_text(
        f"✅ *Saved!*\n{_tag_emoji(recipe.tag)} [{recipe.tag}] *{recipe.name}*{extra}",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


async def recipe_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Cancelled.")
    context.user_data.clear()
    return ConversationHandler.END


def build_recipes_text() -> str:
    recipes = get_all_recipes()
    if not recipes:
        return "📖 *Recipes*\n_No recipes saved yet._"

    groups: dict[str, list] = {}
    for r in recipes:
        groups.setdefault(r.tag, []).append(r)

    ordered_tags = [t for t in BUILTIN_TAGS if t in groups]
    ordered_tags += sorted(t for t in groups if t not in BUILTIN_TAGS)

    lines = ["📖 *Recipes*"]
    for tag in ordered_tags:
        lines.append(f"\n{_tag_emoji(tag)} *{tag}*")
        for r in groups[tag]:
            extra = f" — {r.link_or_desc}" if r.link_or_desc else ""
            lines.append(f"• {r.name}{extra}")
    return "\n".join(lines)


async def list_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_recipes_text(), parse_mode="Markdown")


recipe_conversation = ConversationHandler(
    entry_points=[CommandHandler("recipe", recipe_start)],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, recipe_got_name)],
        ASK_TAG: [CallbackQueryHandler(recipe_got_tag, pattern="^recipetag:")],
        ASK_CUSTOM_TAG: [MessageHandler(filters.TEXT & ~filters.COMMAND, recipe_got_custom_tag)],
        ASK_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, recipe_got_desc)],
    },
    fallbacks=[CommandHandler("cancel", recipe_cancel)],
    per_user=True,
    per_chat=True,
)
