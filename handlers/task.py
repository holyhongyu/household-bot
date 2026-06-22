"""
/task   - guided conversation: name -> assignee -> due date -> priority -> save
/today  - dashboard of pending tasks grouped by assignee + upcoming reminders
/done   - mark a task complete by keyword match
"""
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from database.crud import (
    get_all_users, get_user_by_telegram_id, get_user_by_id, create_task,
    get_pending_tasks, find_pending_task_by_keyword, complete_task,
    get_reminders_in_range,
)
from database.models import Priority
from keyboards import assignee_keyboard, due_date_keyboard, priority_keyboard, cancel_keyboard
from config import GOOGLE_CALENDAR_ENABLED, GOOGLE_CALENDAR_ID, GOOGLE_CALENDAR_USER, TIMEZONE

# Conversation states
ASK_NAME, ASK_ASSIGNEE, ASK_DUE, ASK_PRIORITY = range(4)


def _both_users_registered() -> tuple | None:
    """Returns (me, wife) Users if exactly 2 are registered, else None."""
    users = get_all_users()
    if len(users) < 2:
        return None
    return users[0], users[1]


async def task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pair = _both_users_registered()
    if not pair:
        await update.message.reply_text(
            "⚠️ Both household members need to run /start in this chat first "
            "before tasks can be assigned."
        )
        return ConversationHandler.END

    await update.message.reply_text("📝 *Create New Task*\nWhat is the task?", parse_mode="Markdown")
    return ASK_NAME


async def task_got_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["task_description"] = update.message.text
    pair = _both_users_registered()
    me, wife = pair

    await update.message.reply_text(
        f"📝 *New Task*\nTask: {update.message.text}\nAssign to:",
        parse_mode="Markdown",
        reply_markup=assignee_keyboard(me, wife),
    )
    return ASK_ASSIGNEE


async def task_got_assignee(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    value = query.data.split(":", 1)[1]  # "both" or a user id

    if value == "both":
        context.user_data["assigned_both"] = True
        context.user_data["assigned_to_id"] = None
        assignee_label = "👫 Both"
    else:
        context.user_data["assigned_both"] = False
        context.user_data["assigned_to_id"] = int(value)
        assigned_user = get_user_by_id(int(value))
        assignee_label = assigned_user.display_name

    description = context.user_data["task_description"]
    await query.edit_message_text(
        f"📝 *New Task*\nTask: {description}\nAssigned: {assignee_label}\n\nChoose due date:",
        parse_mode="Markdown",
        reply_markup=due_date_keyboard(),
    )
    return ASK_DUE


async def task_got_due(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    value = query.data.split(":", 1)[1]

    now = datetime.utcnow()
    due_map = {
        "today": now.replace(hour=18, minute=0, second=0, microsecond=0),
        "tomorrow": (now + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0),
        "weekend": _next_saturday(now),
        "none": None,
    }

    if value == "custom":
        await query.edit_message_text(
            "📅 When is it due? e.g. `25 Jun`, `Jun 25`, `25/6`, `2026-06-25`",
            parse_mode="Markdown",
        )
        return ASK_DUE

    context.user_data["due_date"] = due_map[value]
    await query.edit_message_text(
        f"📝 *New Task*\nDue: {value.capitalize()}\n\nPriority:",
        parse_mode="Markdown",
        reply_markup=priority_keyboard(),
    )
    return ASK_PRIORITY


async def task_got_custom_due(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    parsed = _try_parse_date(text)
    if not parsed:
        await update.message.reply_text(
            "Couldn't parse that. Try `25 Jun`, `Jun 25`, `25/6`, or `2026-06-25`.",
            parse_mode="Markdown",
        )
        return ASK_DUE

    context.user_data["due_date"] = parsed
    await update.message.reply_text(
        f"📝 *New Task*\nDue: {parsed.strftime('%d %b %Y')}\n\nPriority:",
        parse_mode="Markdown",
        reply_markup=priority_keyboard(),
    )
    return ASK_PRIORITY


async def task_got_priority(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    value = query.data.split(":", 1)[1]
    priority = Priority(value)

    tg_user = update.effective_user
    creator = get_user_by_telegram_id(tg_user.id)

    task = create_task(
        description=context.user_data["task_description"],
        created_by_id=creator.id,
        assigned_to_id=context.user_data.get("assigned_to_id"),
        assigned_both=context.user_data.get("assigned_both", False),
        due_date=context.user_data.get("due_date"),
        priority=priority,
    )

    assignee_label = "👫 Both" if task.assigned_both else get_user_by_id(task.assigned_to_id).display_name
    due_label = task.due_date.strftime("%d %b") if task.due_date else "No due date"
    priority_emoji = {"high": "🔥", "normal": "🟡", "low": "🟢"}[priority.value]

    await query.edit_message_text(
        f"✅ *Task Created*\n"
        f"🛒 {task.description}\n"
        f"Assigned: {assignee_label}\n"
        f"Due: {due_label}\n"
        f"Priority: {priority_emoji} {priority.value.capitalize()}",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


async def task_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("❌ Task creation cancelled.")
    else:
        await update.message.reply_text("❌ Task creation cancelled.")
    context.user_data.clear()
    return ConversationHandler.END


def _next_saturday(now: datetime) -> datetime:
    days_ahead = (5 - now.weekday()) % 7  # Saturday = 5
    days_ahead = days_ahead if days_ahead != 0 else 7
    return (now + timedelta(days=days_ahead)).replace(hour=12, minute=0, second=0, microsecond=0)


def _try_parse_date(text: str) -> datetime | None:
    now = datetime.utcnow()
    for fmt in ("%Y-%m-%d", "%d %B", "%d %b", "%B %d", "%b %d", "%d/%m/%Y", "%d/%m"):
        try:
            parsed = datetime.strptime(text.strip(), fmt)
            if parsed.year == 1900:
                parsed = parsed.replace(year=now.year)
                if parsed.date() < now.date():
                    parsed = parsed.replace(year=now.year + 1)
            return parsed
        except ValueError:
            continue
    return None


task_conversation = ConversationHandler(
    entry_points=[CommandHandler("task", task_start)],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_got_name)],
        ASK_ASSIGNEE: [CallbackQueryHandler(task_got_assignee, pattern="^assignee:")],
        ASK_DUE: [
            CallbackQueryHandler(task_got_due, pattern="^due:"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, task_got_custom_due),
        ],
        ASK_PRIORITY: [CallbackQueryHandler(task_got_priority, pattern="^priority:")],
    },
    fallbacks=[CallbackQueryHandler(task_cancel, pattern="^cancel$"), CommandHandler("cancel", task_cancel)],
    # per_user=True is essential in a group chat: without it, the bot tracks
    # ONE /task conversation per chat, not per person. With two people in
    # the same group both able to run /task, their conversations collide
    # and replies get silently dropped or misattributed.
    per_user=True,
    per_chat=True,
)


# ---------- /today ----------

_PRIORITY_EMOJI = {Priority.HIGH: "🔥", Priority.NORMAL: "🟡", Priority.LOW: "🟢"}
_PRIORITY_LABEL = {Priority.HIGH: "High", Priority.NORMAL: "Normal", Priority.LOW: "Low"}

# Fixed personal nickname override. Matched by display_name exactly as
# set during /start - if that name ever changes, this stops applying.
_NICKNAMES = {"Hongyu": "Hongyu the Chubby"}


def _section_title(name: str) -> str:
    return _NICKNAMES.get(name, name)


def _format_task_line(task) -> str:
    """One line for a task: bullet, description, due date (priority shown via the section header instead)."""
    due = f" (due {task.due_date.strftime('%d %b')})" if task.due_date else ""
    return f"• {task.description}{due}"


def _render_section(title: str, section_tasks: list) -> list[str]:
    """
    Renders one person/shared section with priority sub-headers, each
    listing only the priorities that actually have pending tasks -
    matches the requested template but skips empty priority groups
    rather than showing them as blank bullets.
    """
    lines = [f"\n*{title}*"]
    if not section_tasks:
        lines.append("_Nothing pending_")
        return lines

    for priority in (Priority.HIGH, Priority.NORMAL, Priority.LOW):
        group = [t for t in section_tasks if t.priority == priority]
        if not group:
            continue
        lines.append(f"\n{_PRIORITY_EMOJI[priority]} {_PRIORITY_LABEL[priority]}")
        for t in group:
            lines.append(_format_task_line(t))
    return lines


def build_today_message() -> str:
    """Builds the /today message text. Called by both the command handler and the scheduler."""
    tasks = get_pending_tasks()
    users = get_all_users()

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    day_after_start = tomorrow_start + timedelta(days=1)
    reminders_window = get_reminders_in_range(today_start, day_after_start)

    todays_reminders = [r for r in reminders_window if r.remind_at < tomorrow_start]
    tomorrows_reminders = [r for r in reminders_window if r.remind_at >= tomorrow_start]

    lines = ["🏠 *Baboo's Magic Task List*"]

    if GOOGLE_CALENDAR_ENABLED:
        from calendar_client import get_week_events, format_calendar_section
        cal_events = get_week_events(None, GOOGLE_CALENDAR_ID, TIMEZONE)
        lines.extend(format_calendar_section(cal_events, TIMEZONE))

    if todays_reminders or tomorrows_reminders:
        lines.append("\n⏰ *Reminders*")
        for r in todays_reminders:
            lines.append(f"• {r.remind_at.strftime('%a %-d %b, %I:%M%p')}: {r.text}")
        for r in tomorrows_reminders:
            lines.append(f"• {r.remind_at.strftime('%a %-d %b, %I:%M%p')}: {r.text}")

    for user in users:
        user_tasks = [t for t in tasks if t.assigned_to_id == user.id and not t.assigned_both]
        lines.extend(_render_section(_section_title(user.display_name), user_tasks))

    shared_tasks = [t for t in tasks if t.assigned_both]
    lines.extend(_render_section("👫 Shared", shared_tasks))

    return "\n".join(lines)


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_today_message(), parse_mode="Markdown")


# ---------- /done ----------

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /done <keyword>\nExample: /done groceries")
        return

    keyword = " ".join(context.args)
    task = find_pending_task_by_keyword(keyword)

    if not task:
        await update.message.reply_text(f"Couldn't find a pending task matching '{keyword}'.")
        return

    tg_user = update.effective_user
    completer = get_user_by_telegram_id(tg_user.id)
    updated = complete_task(task.id, completer.id)

    await update.message.reply_text(
        f"✅ *Completed*\n{updated.description}\n"
        f"Completed by: {completer.display_name}\n"
        f"Time: {updated.completed_at.strftime('%I:%M%p')}",
        parse_mode="Markdown",
    )
