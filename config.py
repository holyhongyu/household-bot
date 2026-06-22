"""
Loads and validates environment configuration.
Everything that varies between dev/prod lives here - nowhere else in the
codebase should call os.getenv directly.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL", "sqlite:///household.db")
TIMEZONE = os.getenv("TIMEZONE", "UTC")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")  # optional, set after first /chatid

if not BOT_TOKEN:
    sys.exit(
        "ERROR: BOT_TOKEN is not set. Copy .env.example to .env and fill in "
        "your bot token from @BotFather."
    )

if GROUP_CHAT_ID:
    try:
        GROUP_CHAT_ID = int(GROUP_CHAT_ID)
    except ValueError:
        sys.exit("ERROR: GROUP_CHAT_ID must be a number (e.g. -100123456789).")

# Google Calendar integration (optional — skipped if not configured)
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
GOOGLE_CALENDAR_ENABLED = bool(GOOGLE_CALENDAR_ID and (GOOGLE_CREDENTIALS_FILE or GOOGLE_CREDENTIALS_JSON))
# Which user's section in /today the calendar events appear under
GOOGLE_CALENDAR_USER = os.getenv("GOOGLE_CALENDAR_USER", "Hongyu")
