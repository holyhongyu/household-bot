"""
Background scheduler. Runs two jobs:

1. check_reminders - every 60 seconds, fires any reminder that's due,
   and either deactivates (one-off, or recurring that's reached its end
   condition) or reschedules (still-recurring) it.

2. send_tomorrow_nag - once a day at 9am (in TIMEZONE from .env), posts a
   heads-up listing anything due tomorrow, so it doesn't catch anyone
   off guard the day it actually fires.

Both rely on state living in the database, not in memory, so a bot
restart doesn't lose track of anything.
"""
import logging
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application

from config import GROUP_CHAT_ID, TIMEZONE
from database.crud import (
    get_due_reminders, deactivate_reminder, reschedule_reminder,
    get_reminders_in_range,
)
from handlers.task import build_today_message

logger = logging.getLogger(__name__)


def _compute_next_occurrence(reminder, now: datetime) -> datetime:
    """
    Works out the next remind_at for a recurring reminder, given its
    structured recurrence fields. Called only when the reminder is
    confirmed to still be recurring (end condition checked separately).
    """
    unit = reminder.recurrence_unit
    n = reminder.recurrence_interval
    base = reminder.remind_at

    if unit == "day":
        return base + timedelta(days=n)
    if unit == "week":
        return base + timedelta(weeks=n)
    if unit == "month":
        month = base.month - 1 + n
        year = base.year + month // 12
        month = month % 12 + 1
        import calendar
        day = min(base.day, calendar.monthrange(year, month)[1])
        return base.replace(year=year, month=month, day=day)
    # year
    try:
        return base.replace(year=base.year + n)
    except ValueError:
        # Feb 29 in a non-leap year
        return base.replace(year=base.year + n, day=28)


def _has_reached_end_condition(reminder, next_occurrence: datetime) -> bool:
    """True if firing again would exceed the reminder's configured end condition."""
    if reminder.recurrence_max_count:
        # recurrence_count_so_far is incremented by reschedule_reminder AFTER
        # each fire, so at this point it reflects fires completed so far
        # (not counting the one about to happen). We're checking whether
        # the fire about to happen would be the last allowed one.
        fires_completed_including_this_one = (reminder.recurrence_count_so_far or 0) + 1
        return fires_completed_including_this_one >= reminder.recurrence_max_count

    if reminder.recurrence_end_date:
        return next_occurrence > reminder.recurrence_end_date

    return False  # no end condition - repeats forever


async def check_reminders(app: Application):
    if not GROUP_CHAT_ID:
        logger.warning("GROUP_CHAT_ID not set - skipping reminder check. Run /chatid in your group and set it in .env.")
        return

    now = datetime.utcnow()
    due = get_due_reminders(now)

    for reminder in due:
        try:
            await app.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=f"⏰ *Reminder*\n{reminder.text}",
                parse_mode="Markdown",
            )
        except Exception:
            logger.exception(f"Failed to send reminder {reminder.id}")
            continue

        if reminder.recurrence_unit:
            next_occurrence = _compute_next_occurrence(reminder, now)
            if _has_reached_end_condition(reminder, next_occurrence):
                deactivate_reminder(reminder.id)
            else:
                reschedule_reminder(reminder.id, next_occurrence)
        else:
            deactivate_reminder(reminder.id)


async def send_tomorrow_nag(app: Application):
    """
    Runs once a day at 9am local time. Looks at reminders due tomorrow
    (in UTC, since that's how remind_at is stored) and posts a single
    heads-up message listing all of them, so nothing fires as a surprise.
    """
    if not GROUP_CHAT_ID:
        logger.warning("GROUP_CHAT_ID not set - skipping tomorrow nag.")
        return

    now = datetime.utcnow()
    tomorrow_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    day_after_start = tomorrow_start + timedelta(days=1)

    tomorrows_reminders = get_reminders_in_range(tomorrow_start, day_after_start)
    if not tomorrows_reminders:
        return  # nothing due tomorrow - stay quiet, don't post an empty nag

    lines = ["🔔 *XXX REMEMBER FOR TOMORROW XXX*"]
    for r in tomorrows_reminders:
        lines.append(f"• {r.remind_at.strftime('%I:%M%p')}: {r.text}")

    try:
        await app.bot.send_message(chat_id=GROUP_CHAT_ID, text="\n".join(lines), parse_mode="Markdown")
    except Exception:
        logger.exception("Failed to send the tomorrow nag.")


def start_scheduler(app: Application) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, "interval", seconds=60, args=[app])

    # Cron trigger needs an explicit timezone - without it APScheduler
    # uses the server's local time, which on Railway would be UTC, not
    # the household's actual 9am.
    tz = pytz.timezone(TIMEZONE)
    scheduler.add_job(send_tomorrow_nag, CronTrigger(hour=9, minute=0, timezone=tz), args=[app])
    scheduler.add_job(send_daily_today, CronTrigger(hour=6, minute=0, timezone=tz), args=[app])

    scheduler.start()
    return scheduler


async def send_daily_today(app: Application):
    if not GROUP_CHAT_ID:
        return
    try:
        await app.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=build_today_message(),
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("Failed to send the daily today summary.")
