"""
Google Calendar integration.

Fetches events for the current week (Mon–Sun) from now onwards.
Returns a list of dicts with 'title', 'start' (datetime), 'all_day' (bool).

If credentials aren't configured the public functions return [] silently,
so /today degrades gracefully rather than crashing.
"""
import logging
from datetime import datetime, timedelta

import pytz

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _load_credentials():
    """Load service account credentials from a file or the GOOGLE_CREDENTIALS_JSON env var."""
    import os, json
    from google.oauth2 import service_account

    raw = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if raw:
        info = json.loads(raw)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

    creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE")
    if creds_file:
        return service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)

    return None


def get_week_events(credentials_file: str, calendar_id: str, timezone: str) -> list[dict]:
    """
    Returns events from now until 7 days later as a list of dicts.
    Silently returns [] on any error so /today always renders.
    """
    try:
        from googleapiclient.discovery import build

        creds = _load_credentials()
        if not creds:
            return []
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        tz = pytz.timezone(timezone)
        now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
        end_utc = now_utc + timedelta(days=7)

        result = service.events().list(
            calendarId=calendar_id,
            timeMin=now_utc.isoformat(),
            timeMax=end_utc.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=20,
        ).execute()

        events = []
        for item in result.get("items", []):
            start = item["start"]
            if "dateTime" in start:
                dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
                all_day = False
            else:
                # all-day event: date only
                dt = datetime.strptime(start["date"], "%Y-%m-%d").replace(tzinfo=tz)
                all_day = True
            events.append({
                "title": item.get("summary", "(no title)"),
                "start": dt,
                "all_day": all_day,
            })
        return events

    except Exception:
        logger.exception("Google Calendar fetch failed")
        return []


def format_calendar_section(events: list[dict], timezone: str) -> list[str]:
    """
    Renders the calendar event list as text lines for /today.
    Groups by day: 'Today', 'Tomorrow', or 'Wed 25 Jun'.
    """
    if not events:
        return []

    tz = pytz.timezone(timezone)
    now_local = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(tz)
    today = now_local.date()
    tomorrow = today + timedelta(days=1)

    lines = ["\n📅 *Hongyu's Calendar*"]
    for e in events:
        start: datetime = e["start"]
        day_label = start.strftime("%a %-d %b")

        if e["all_day"]:
            lines.append(f"• {day_label} — {e['title']}")
        else:
            lines.append(f"• {day_label} {start.strftime('%-I:%M%p').lower()} — {e['title']}")

    return lines
