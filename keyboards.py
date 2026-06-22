"""
All InlineKeyboardMarkup builders. Centralised so button layout/emoji
choices are changed in one place. Callback data format is always
"<namespace>:<value>" (e.g. "assignee:both", "priority:high") so the
callback router in handlers/task.py can dispatch cleanly.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import User


def assignee_keyboard(me: User, wife: User) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(f"👨 {me.display_name}", callback_data=f"assignee:{me.id}"),
            InlineKeyboardButton(f"👩 {wife.display_name}", callback_data=f"assignee:{wife.id}"),
        ],
        [InlineKeyboardButton("👫 Both", callback_data="assignee:both")],
    ]
    return InlineKeyboardMarkup(buttons)


def due_date_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("Today", callback_data="due:today"),
            InlineKeyboardButton("Tomorrow", callback_data="due:tomorrow"),
        ],
        [InlineKeyboardButton("This Weekend", callback_data="due:weekend")],
        [InlineKeyboardButton("Custom Date", callback_data="due:custom")],
        [InlineKeyboardButton("No due date", callback_data="due:none")],
    ]
    return InlineKeyboardMarkup(buttons)


def priority_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🔥 High", callback_data="priority:high"),
            InlineKeyboardButton("🟡 Normal", callback_data="priority:normal"),
            InlineKeyboardButton("🟢 Low", callback_data="priority:low"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def reminder_time_keyboard() -> InlineKeyboardMarkup:
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    buttons = []
    # Next 6 days as date buttons (skipping today since time hasn't been chosen yet)
    for offset in range(0, 7):
        d = now + timedelta(days=offset)
        label = {0: "Today", 1: "Tomorrow"}.get(offset, d.strftime("%a %d %b"))
        buttons.append([InlineKeyboardButton(label, callback_data=f"reminddate:{d.strftime('%Y-%m-%d')}")])
    buttons.append([InlineKeyboardButton("📅 Other date (type it)", callback_data="reminddate:custom")])
    return InlineKeyboardMarkup(buttons)


def reminder_time_of_day_keyboard(date_str: str) -> InlineKeyboardMarkup:
    """Second step: pick a time for the already-chosen date."""
    times = [("8am", "08:00"), ("9am", "09:00"), ("12pm", "12:00"),
             ("3pm", "15:00"), ("6pm", "18:00"), ("8pm", "20:00"), ("9pm", "21:00")]
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"remindtime:{date_str}T{t}")]
        for label, t in times
    ]
    buttons.append([InlineKeyboardButton("🕐 Other time (type it)", callback_data=f"remindtime:{date_str}Tcustom")])
    return InlineKeyboardMarkup(buttons)


def recurrence_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("Just once", callback_data="recur:once")],
        [
            InlineKeyboardButton("Daily", callback_data="recur:daily"),
            InlineKeyboardButton("Weekly", callback_data="recur:weekly"),
        ],
        [InlineKeyboardButton("Custom interval", callback_data="recur:custom")],
    ]
    return InlineKeyboardMarkup(buttons)


def recurrence_end_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("No end date", callback_data="recurend:never")],
        [InlineKeyboardButton("After N times", callback_data="recurend:count")],
        [InlineKeyboardButton("Until a date", callback_data="recurend:date")],
    ]
    return InlineKeyboardMarkup(buttons)


def reminder_assignee_keyboard(users: list) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(u.display_name, callback_data=f"reminderassignee:{u.id}")]
        for u in users
    ]
    buttons.append([InlineKeyboardButton("👫 Shared", callback_data="reminderassignee:both")])
    return InlineKeyboardMarkup(buttons)


BUILTIN_TAGS = ["Main Meal", "Snack", "Drink"]


def recipe_tag_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("🥘 Main Meal", callback_data="recipetag:Main Meal")],
        [InlineKeyboardButton("🍿 Snack", callback_data="recipetag:Snack")],
        [InlineKeyboardButton("☕ Drink", callback_data="recipetag:Drink")],
        [InlineKeyboardButton("🏷️ Custom (type it)", callback_data="recipetag:__custom__")],
    ]
    return InlineKeyboardMarkup(buttons)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
    )


def _truncate(text: str, max_len: int = 40) -> str:
    """Telegram button labels get unwieldy past ~40 chars - truncate with an ellipsis."""
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def task_delete_list_keyboard(tasks: list) -> InlineKeyboardMarkup:
    """One button per pending task, each carrying its id - tapping leads to a confirm step, not an instant delete."""
    buttons = [
        [InlineKeyboardButton(_truncate(t.description), callback_data=f"deltask:{t.id}")]
        for t in tasks
    ]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="canceldelete")])
    return InlineKeyboardMarkup(buttons)


def reminder_delete_list_keyboard(reminders: list) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(_truncate(r.text), callback_data=f"delreminder:{r.id}")]
        for r in reminders
    ]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="canceldelete")])
    return InlineKeyboardMarkup(buttons)


def confirm_delete_keyboard(item_type: str, item_id: int) -> InlineKeyboardMarkup:
    """item_type is 'task' or 'reminder' - used to route the confirmation to the right delete function."""
    buttons = [
        [
            InlineKeyboardButton("✅ Yes, delete", callback_data=f"confirmdel:{item_type}:{item_id}"),
            InlineKeyboardButton("❌ No, keep it", callback_data="canceldelete"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)
