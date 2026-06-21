"""
One-time migration: upgrades an existing household.db to the new
recurrence schema (interval/unit/end-date columns on the reminders table)
without losing any existing tasks or reminders.

Run this ONCE, after pulling the updated database/models.py and before
starting the bot again:

    python3 migrate_reminders.py

Safe to run multiple times - it checks for each column before adding it,
so re-running does nothing if already migrated.
"""
import sqlite3

from config import DATABASE_URL

# Extract the file path from a sqlite:/// URL
db_path = DATABASE_URL.replace("sqlite:///", "")

NEW_COLUMNS = [
    ("recurrence_unit", "VARCHAR(10)"),
    ("recurrence_interval", "INTEGER"),
    ("recurrence_weekday", "INTEGER"),
    ("recurrence_end_date", "DATETIME"),
    ("recurrence_max_count", "INTEGER"),
    ("recurrence_count_so_far", "INTEGER DEFAULT 0"),
]


def migrate():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(reminders)")
    existing_columns = {row[1] for row in cur.fetchall()}

    if not existing_columns:
        print(
            f"No 'reminders' table found in {db_path} yet - nothing to "
            "migrate. It'll be created fresh with the new schema on next "
            "bot startup."
        )
        conn.close()
        return

    added_any = False
    for column_name, column_type in NEW_COLUMNS:
        if column_name in existing_columns:
            print(f"  - {column_name}: already present, skipping")
            continue
        cur.execute(f"ALTER TABLE reminders ADD COLUMN {column_name} {column_type}")
        print(f"  + {column_name}: added")
        added_any = True

    # Migrate old-style recurrence_rule data ("weekly:sun") into the new
    # columns if that column still exists from before.
    if "recurrence_rule" in existing_columns:
        cur.execute("SELECT id, recurrence_rule FROM reminders WHERE recurrence_rule IS NOT NULL")
        rows = cur.fetchall()
        weekday_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
        for reminder_id, rule in rows:
            if rule and rule.startswith("weekly:"):
                day_str = rule.split(":")[1]
                weekday_num = weekday_map.get(day_str)
                cur.execute(
                    "UPDATE reminders SET recurrence_unit='week', recurrence_interval=1, "
                    "recurrence_weekday=? WHERE id=?",
                    (weekday_num, reminder_id),
                )
                print(f"  ~ migrated old rule '{rule}' on reminder #{reminder_id} to weekly recurrence")

    conn.commit()
    conn.close()

    if added_any:
        print("\nMigration complete. Your existing tasks and reminders are untouched.")
    else:
        print("\nNothing to migrate - already up to date.")


if __name__ == "__main__":
    migrate()
