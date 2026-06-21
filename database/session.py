"""
Engine + session factory. Other modules import SessionLocal and use it as
a context manager:

    from database.session import SessionLocal
    with SessionLocal() as session:
        ...
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from database.models import Base

# check_same_thread=False is needed because python-telegram-bot runs
# handlers in an async event loop, not the thread SQLite was opened on.
# This is safe here because APScheduler/PTB hand off work sequentially
# per chat, not truly concurrently writing the same rows.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    """Create all tables if they don't exist, and apply any missing column migrations."""
    Base.metadata.create_all(bind=engine)
    _migrate(engine)


def _migrate(eng):
    """Add columns/tables that were introduced after the initial schema."""
    with eng.connect() as conn:
        # reminders: assignee fields added in v2
        existing = {row[1] for row in conn.execute(
            __import__("sqlalchemy").text("PRAGMA table_info(reminders)")
        )}
        if "assigned_to_id" not in existing:
            conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE reminders ADD COLUMN assigned_to_id INTEGER REFERENCES users(id)"
            ))
        if "assigned_both" not in existing:
            conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE reminders ADD COLUMN assigned_both BOOLEAN DEFAULT 0"
            ))
        conn.commit()
