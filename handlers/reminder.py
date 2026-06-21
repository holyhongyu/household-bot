"""
/reminder - guided conversation:
  text -> when -> repeat pattern -> (if repeating) repeat until -> save

Repeat pattern is asked via buttons (Just once / Daily / Weekly / Custom
interval). Custom interval and custom date/time still accept free text
for the unusual cases buttons can't cover.
"""
import re
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters,
)

from database.crud import get_user_by_telegram_id, get_all_users, create_reminder, get_active_reminders
from keyboards import recurrence_keyboard, recurrence_end_keyboard, reminder_assignee_keyboard

ASK_TEXT, ASK_WHEN, ASK_REPEAT, ASK_REPEAT_CUSTOM, ASK_REPEAT_END, ASK_REPEAT_END_VALUE, ASK_ASSIGNEE = range(7)

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


_WHEN_HINT = "When? e.g. `25 Jun 9pm` or `2026-06-25 09:00`"


async def reminder_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.args:
        text = " ".join(context.args)
        context.user_data["reminder_text"] = text
        await update.message.reply_text(
            f"⏰ Reminder: *{text}*\n{_WHEN_HINT}", parse_mode="Markdown"
        )
        return ASK_WHEN

    await update.message.reply_text("⏰ *New Reminder*\nWhat should I remind you about?", parse_mode="Markdown")
    return ASK_TEXT


async def reminder_got_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["reminder_text"] = update.message.text
    await update.message.reply_text(
        f"⏰ Reminder: *{update.message.text}*\n{_WHEN_HINT}", parse_mode="Markdown"
    )
    return ASK_WHEN


async def reminder_got_when(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    parsed = _try_parse_datetime(text)
    if not parsed:
        await update.message.reply_text(
            f"Couldn't parse that. Try `25 Jun 9pm` or `2026-06-25 09:00`.",
            parse_mode="Markdown",
        )
        return ASK_WHEN

    context.user_data["remind_at"] = parsed
    await update.message.reply_text(
        f"⏰ Reminder: *{context.user_data['reminder_text']}*\n"
        f"When: {parsed.strftime('%a %d %b, %I:%M %p')}\n\nRepeat?",
        parse_mode="Markdown",
        reply_markup=recurrence_keyboard(),
    )
    return ASK_REPEAT


async def reminder_got_repeat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    value = query.data.split(":", 1)[1]

    if value == "once":
        context.user_data["recurrence_unit"] = None
        context.user_data["recurrence_interval"] = None
        context.user_data["recurrence_weekday"] = None
        return await _finalize_and_save(update, context, via_callback=True)

    if value == "daily":
        context.user_data["recurrence_unit"] = "day"
        context.user_data["recurrence_interval"] = 1
        context.user_data["recurrence_weekday"] = None
        await query.edit_message_text(
            "Repeat until?", reply_markup=recurrence_end_keyboard()
        )
        return ASK_REPEAT_END

    if value == "weekly":
        remind_at = context.user_data["remind_at"]
        context.user_data["recurrence_unit"] = "week"
        context.user_data["recurrence_interval"] = 1
        context.user_data["recurrence_weekday"] = remind_at.weekday()
        await query.edit_message_text(
            "Repeat until?", reply_markup=recurrence_end_keyboard()
        )
        return ASK_REPEAT_END

    # custom
    await query.edit_message_text(
        "Type the interval, e.g. `every 4 days` or `every 3 weeks`.",
        parse_mode="Markdown",
    )
    return ASK_REPEAT_CUSTOM


async def reminder_got_repeat_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().lower()
    match = re.match(r"every (\d+) (day|days|week|weeks)", text)
    if not match:
        await update.message.reply_text(
            "Couldn't parse that. Try `every 4 days` or `every 3 weeks`."
        )
        return ASK_REPEAT_CUSTOM

    interval, unit = match.groups()
    interval = int(interval)
    unit = "day" if unit.startswith("day") else "week"

    context.user_data["recurrence_unit"] = unit
    context.user_data["recurrence_interval"] = interval
    if unit == "week":
        context.user_data["recurrence_weekday"] = context.user_data["remind_at"].weekday()
    else:
        context.user_data["recurrence_weekday"] = None

    await update.message.reply_text("Repeat until?", reply_markup=recurrence_end_keyboard())
    return ASK_REPEAT_END


async def reminder_got_repeat_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    value = query.data.split(":", 1)[1]

    if value == "never":
        context.user_data["recurrence_end_date"] = None
        context.user_data["recurrence_max_count"] = None
        return await _finalize_and_save(update, context, via_callback=True)

    if value == "count":
        await query.edit_message_text("How many times should it repeat? Send a number, e.g. `8`.")
        context.user_data["awaiting_repeat_end_type"] = "count"
        return ASK_REPEAT_END_VALUE

    # date
    await query.edit_message_text("Repeat until what date? e.g. `2026-08-01`.")
    context.user_data["awaiting_repeat_end_type"] = "date"
    return ASK_REPEAT_END_VALUE


async def reminder_got_repeat_end_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    end_type = context.user_data.get("awaiting_repeat_end_type")

    if end_type == "count":
        if not text.isdigit() or int(text) <= 0:
            await update.message.reply_text("Please send a positive number, e.g. `8`.")
            return ASK_REPEAT_END_VALUE
        context.user_data["recurrence_max_count"] = int(text)
        context.user_data["recurrence_end_date"] = None
    else:  # date
        parsed_date = None
        for fmt in ("%Y-%m-%d", "%d %B", "%d %b", "%d/%m/%Y"):
            try:
                parsed_date = datetime.strptime(text, fmt)
                if parsed_date.year == 1900:
                    parsed_date = parsed_date.replace(year=datetime.utcnow().year)
                break
            except ValueError:
                continue
        if not parsed_date:
            await update.message.reply_text("Couldn't parse that date. Try `2026-08-01`.")
            return ASK_REPEAT_END_VALUE
        context.user_data["recurrence_end_date"] = parsed_date
        context.user_data["recurrence_max_count"] = None

    return await _finalize_and_save(update, context, via_callback=False)


async def _ask_assignee(update, context, via_callback: bool) -> int:
    users = get_all_users()
    context.user_data["_via_callback"] = via_callback
    msg = "Who is this reminder for?"
    kb = reminder_assignee_keyboard(users)
    if via_callback:
        await update.callback_query.edit_message_text(msg, reply_markup=kb)
    else:
        await update.message.reply_text(msg, reply_markup=kb)
    return ASK_ASSIGNEE


async def reminder_got_assignee(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    value = query.data.split(":", 1)[1]

    tg_user = update.effective_user
    creator = get_user_by_telegram_id(tg_user.id)

    assigned_to_id = None
    assigned_both = False
    if value == "both":
        assigned_both = True
    else:
        assigned_to_id = int(value)

    reminder = create_reminder(
        text=context.user_data["reminder_text"],
        created_by_id=creator.id,
        remind_at=context.user_data["remind_at"],
        recurrence_unit=context.user_data.get("recurrence_unit"),
        recurrence_interval=context.user_data.get("recurrence_interval"),
        recurrence_weekday=context.user_data.get("recurrence_weekday"),
        recurrence_end_date=context.user_data.get("recurrence_end_date"),
        recurrence_max_count=context.user_data.get("recurrence_max_count"),
        assigned_to_id=assigned_to_id,
        assigned_both=assigned_both,
    )

    users = get_all_users()
    if assigned_both:
        assignee_label = "Everyone"
    else:
        user = next((u for u in users if u.id == assigned_to_id), None)
        assignee_label = user.display_name if user else "Unknown"

    recur_label = _describe_recurrence(reminder)
    msg = (
        f"✅ *Reminder Set*\n{reminder.text}\n"
        f"{reminder.remind_at.strftime('%a %d %b, %I:%M%p')}{recur_label}\n"
        f"For: {assignee_label}"
    )
    await query.edit_message_text(msg, parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END


async def _finalize_and_save(update, context, via_callback: bool) -> int:
    return await _ask_assignee(update, context, via_callback)


def _describe_recurrence(reminder) -> str:
    """Builds the human-readable '(repeats ...)' suffix for the confirmation message."""
    if not reminder.recurrence_unit:
        return ""

    if reminder.recurrence_unit == "day":
        unit_label = "day" if reminder.recurrence_interval == 1 else "days"
        base = f"every {reminder.recurrence_interval} {unit_label}" if reminder.recurrence_interval > 1 else "daily"
    else:  # week
        if reminder.recurrence_interval == 1:
            day_name = WEEKDAYS[reminder.recurrence_weekday].capitalize()
            base = f"weekly on {day_name}"
        else:
            base = f"every {reminder.recurrence_interval} weeks"

    if reminder.recurrence_max_count:
        return f" (repeats {base}, {reminder.recurrence_max_count}x)"
    if reminder.recurrence_end_date:
        return f" (repeats {base}, until {reminder.recurrence_end_date.strftime('%d %b %Y')})"
    return f" (repeats {base})"


# ---------- /reminders ----------

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists every active reminder, not just today/tomorrow (that's what /today's reminder section is for)."""
    reminders = get_active_reminders()

    if not reminders:
        await update.message.reply_text("⏰ No active reminders.")
        return

    lines = ["⏰ *All Active Reminders*"]
    for r in reminders:
        recur_label = _describe_recurrence(r)
        lines.append(f"\n• {r.text}\n  {r.remind_at.strftime('%a %d %b, %I:%M%p')}{recur_label}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def reminder_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("❌ Reminder cancelled.")
    else:
        await update.message.reply_text("❌ Reminder cancelled.")
    context.user_data.clear()
    return ConversationHandler.END


def _try_parse_datetime(text: str) -> datetime | None:
    """
    Accepts a wide range of date+time strings, e.g.:
      25 Jun 9pm / Jun 25 9pm / 25/6 9pm
      25 Jun 9:30pm / 25 Jun 21:30
      2026-06-25 09:00 / 2026-06-25 9pm
    Returns a UTC datetime (no tz conversion — caller's responsibility).
    """
    now = datetime.utcnow()
    text = text.strip()

    # --- split into date part and time part ---
    # Try to extract a 12-hour time suffix like "9pm", "9:30pm", "9 pm" first
    m12 = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*$", text, re.IGNORECASE)
    # Try a 24-hour time suffix like "09:00" or "21:30"
    m24 = re.search(r"(\d{1,2}):(\d{2})\s*$", text)

    if m12:
        time_str = m12.group(0).strip()
        date_str = text[: m12.start()].strip()
        hour = int(m12.group(1))
        minute = int(m12.group(2)) if m12.group(2) else 0
        meridiem = m12.group(3).lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
    elif m24:
        date_str = text[: m24.start()].strip()
        hour = int(m24.group(1))
        minute = int(m24.group(2))
    else:
        return None

    if not date_str:
        return None

    # --- parse the date part ---
    parsed_date = None
    for fmt in ("%Y-%m-%d", "%d %B", "%d %b", "%B %d", "%b %d", "%d/%m/%Y", "%d/%m"):
        try:
            d = datetime.strptime(date_str, fmt)
            if d.year == 1900:
                d = d.replace(year=now.year)
                if d.date() < now.date():
                    d = d.replace(year=now.year + 1)
            parsed_date = d
            break
        except ValueError:
            continue

    if not parsed_date:
        return None

    return parsed_date.replace(hour=hour, minute=minute, second=0, microsecond=0)


reminder_conversation = ConversationHandler(
    entry_points=[CommandHandler("reminder", reminder_start)],
    states={
        ASK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, reminder_got_text)],
        ASK_WHEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, reminder_got_when)],
        ASK_REPEAT: [CallbackQueryHandler(reminder_got_repeat, pattern="^recur:")],
        ASK_REPEAT_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, reminder_got_repeat_custom)],
        ASK_REPEAT_END: [CallbackQueryHandler(reminder_got_repeat_end, pattern="^recurend:")],
        ASK_REPEAT_END_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reminder_got_repeat_end_value)],
        ASK_ASSIGNEE: [CallbackQueryHandler(reminder_got_assignee, pattern="^reminderassignee:")],
    },
    fallbacks=[CallbackQueryHandler(reminder_cancel, pattern="^cancel$"), CommandHandler("cancel", reminder_cancel)],
    per_user=True,
    per_chat=True,
)
