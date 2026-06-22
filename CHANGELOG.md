# Changelog

### 2026-06-22 (5)
- Fixed Postgres connection on Railway — switched from psycopg2 to psycopg3 which bundles its own PostgreSQL library, resolving the libpq.so.5 crash
- Data (users, tasks, reminders, food places, recipes) now fully persists across all future deploys — no more losing anything when the bot updates

### 2026-06-22 (4)
- Reminders now understand monthly and yearly recurrence — "every 3 months", "every year", "every 6 months" etc all work correctly, including proper month-end date handling

### 2026-06-22 (3)
- Added /summary which sends two messages: tasks + reminders first, then food places + recipes — one command to see everything

### 2026-06-22 (2)
- Added /recipe to save recipes with a tag (Main Meal, Snack, Drink, or your own custom tag) plus an optional description or link
- Added /recipes to view all saved recipes grouped by tag
- /delete now includes Recipes alongside Tasks, Reminders, and Food Places

### 2026-06-22
- Fixed /food command freezing after you enter the Google Maps link — the bot now saves the place correctly and confirms it
- Switched from SQLite to PostgreSQL on Railway so all data (users, tasks, food places, reminders) now persists across deploys — no more losing everything when the bot updates

### 2026-06-21
- Added Google Calendar integration — Hongyu's upcoming events for the next 7 days now appear automatically at the top of the daily summary
- The daily summary now posts itself to the group every morning at 6am Singapore time, no need to type /today
- Bot is now hosted on Railway so it runs 24/7 without needing your laptop to be on
- Added /food command to save restaurant and cafe recommendations with cuisine type and map link
- Added unified /delete command with multi-select — tap multiple items to remove at once instead of one by one
- Reminders now ask who they're for (Hongyu, Zifong, or Shared) after setting the time
- Date and time entry for reminders and tasks now accepts natural formats like "25 Jun 9pm" instead of requiring "2026-06-25 09:00"
