"""
/delete - unified delete flow:
  1. Pick type (Tasks / Reminders / Food Places)
  2. Multi-select list — tap items to toggle ✅/◻️
  3. Confirm button deletes all selected at once
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler,
)

from database.crud import (
    get_pending_tasks, get_task_by_id, delete_task,
    get_active_reminders, get_reminder_by_id, delete_reminder,
    get_all_food_places, get_food_place_by_id, delete_food_place,
)

PICK_TYPE, PICK_ITEMS = range(2)

_TYPE_LABELS = {"task": "Task", "reminder": "Reminder", "food": "Food Place"}


def _type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Tasks", callback_data="deltype:task")],
        [InlineKeyboardButton("⏰ Reminders", callback_data="deltype:reminder")],
        [InlineKeyboardButton("🍽️ Food Places", callback_data="deltype:food")],
        [InlineKeyboardButton("❌ Cancel", callback_data="delcancel")],
    ])


def _item_label(item, item_type: str) -> str:
    if item_type == "task":
        return item.description
    if item_type == "reminder":
        return item.text
    return f"{item.name} ({item.cuisine})"


def _truncate(text: str, n: int = 38) -> str:
    return text if len(text) <= n else text[:n - 1] + "…"


def _list_keyboard(items, item_type: str, selected: set) -> InlineKeyboardMarkup:
    buttons = []
    for item in items:
        tick = "✅" if item.id in selected else "◻️"
        label = _truncate(f"{tick} {_item_label(item, item_type)}")
        buttons.append([InlineKeyboardButton(label, callback_data=f"deltoggle:{item_type}:{item.id}")])

    n = len(selected)
    if n:
        confirm_label = f"🗑 Delete {n} selected"
    else:
        confirm_label = "🗑 Delete selected"

    buttons.append([
        InlineKeyboardButton(confirm_label, callback_data=f"delconfirm:{item_type}"),
        InlineKeyboardButton("❌ Cancel", callback_data="delcancel"),
    ])
    return InlineKeyboardMarkup(buttons)


def _load_items(item_type: str):
    if item_type == "task":
        return get_pending_tasks()
    if item_type == "reminder":
        return get_active_reminders()
    return get_all_food_places()


async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("del_selected", None)
    await update.message.reply_text("🗑 *Delete*\nWhat do you want to delete?",
                                    parse_mode="Markdown", reply_markup=_type_keyboard())
    return PICK_TYPE


async def delete_got_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    item_type = query.data.split(":", 1)[1]

    items = _load_items(item_type)
    if not items:
        await query.edit_message_text(f"No {_TYPE_LABELS[item_type].lower()}s to delete.")
        return ConversationHandler.END

    context.user_data["del_selected"] = set()
    context.user_data["del_type"] = item_type
    await query.edit_message_text(
        f"Tap to select, then press *Delete selected*:",
        parse_mode="Markdown",
        reply_markup=_list_keyboard(items, item_type, set()),
    )
    return PICK_ITEMS


async def delete_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    _, item_type, item_id = query.data.split(":")
    item_id = int(item_id)

    selected: set = context.user_data.get("del_selected", set())
    if item_id in selected:
        selected.discard(item_id)
    else:
        selected.add(item_id)
    context.user_data["del_selected"] = selected

    items = _load_items(item_type)
    await query.edit_message_reply_markup(reply_markup=_list_keyboard(items, item_type, selected))
    return PICK_ITEMS


async def delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    item_type = query.data.split(":", 1)[1]
    selected: set = context.user_data.get("del_selected", set())

    if not selected:
        await query.answer("Nothing selected.", show_alert=True)
        return PICK_ITEMS

    deleted = 0
    for item_id in selected:
        if item_type == "task":
            deleted += delete_task(item_id)
        elif item_type == "reminder":
            deleted += delete_reminder(item_id)
        else:
            deleted += delete_food_place(item_id)

    label = _TYPE_LABELS[item_type].lower()
    await query.edit_message_text(f"🗑 Deleted {deleted} {label}{'s' if deleted != 1 else ''}.")
    context.user_data.pop("del_selected", None)
    return ConversationHandler.END


async def delete_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Cancelled — nothing deleted.")
    context.user_data.pop("del_selected", None)
    return ConversationHandler.END


delete_conversation = ConversationHandler(
    entry_points=[CommandHandler("delete", delete_start)],
    states={
        PICK_TYPE: [
            CallbackQueryHandler(delete_got_type, pattern="^deltype:"),
            CallbackQueryHandler(delete_cancel, pattern="^delcancel$"),
        ],
        PICK_ITEMS: [
            CallbackQueryHandler(delete_toggle, pattern="^deltoggle:"),
            CallbackQueryHandler(delete_confirm, pattern="^delconfirm:"),
            CallbackQueryHandler(delete_cancel, pattern="^delcancel$"),
        ],
    },
    fallbacks=[CallbackQueryHandler(delete_cancel, pattern="^delcancel$")],
    per_user=True,
    per_chat=True,
)
