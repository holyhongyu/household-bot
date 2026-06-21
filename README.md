# Household Bot

A private Telegram bot for managing shared tasks and reminders between two
people, via buttons rather than typed commands where possible.

## Features (v1)

- `/task` - guided task creation (description → assignee → due date → priority)
- `/today` - dashboard of pending tasks grouped by person, plus upcoming reminders
- `/done <keyword>` - mark a task complete by partial name match
- `/reminder` - guided reminder creation, including weekly recurring reminders
  (e.g. type `every sunday 10:00` when asked "when?")

Shopping list and expense tracking tables already exist in the schema
(`database/models.py`) but have no commands yet - see "Adding a new feature" below.

## Local setup

1. **Create the bot**: message [@BotFather](https://t.me/BotFather) on Telegram,
   run `/newbot`, follow the prompts, copy the token it gives you.

2. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```
   cp .env.example .env
   ```
   Open `.env` and paste your bot token into `BOT_TOKEN`. Set `TIMEZONE` to
   your IANA timezone (e.g. `Australia/Sydney`). Leave `GROUP_CHAT_ID` blank for now.

4. **Run it**:
   ```
   python bot.py
   ```

5. **Register both of you**:
   - Create a Telegram group, add your bot to it.
   - **Important**: in the group's settings, you do NOT need to change the
     bot's privacy mode - commands (anything starting with `/`) always reach
     the bot in groups regardless of privacy mode.
   - Both people run `/start` in the group, once each.
   - Run `/chatid` in the group, copy the number it gives you (it'll be
     negative, like `-1001234567890`).
   - Paste that into `GROUP_CHAT_ID` in `.env` and restart the bot. This step
     is what allows scheduled reminders to be sent proactively (the bot can't
     message a chat it's never seen an ID for).

6. Try `/task` and `/reminder` to confirm the buttons work.

## Deploying to Railway

1. Push this folder to a GitHub repo.
2. On [railway.app](https://railway.app), "New Project" → "Deploy from GitHub repo".
3. Add the same environment variables from `.env` in Railway's Variables tab
   (`BOT_TOKEN`, `DATABASE_URL`, `TIMEZONE`, `GROUP_CHAT_ID`).
4. Railway will detect the `Procfile` and run `python bot.py` as a worker.
5. **Persistent storage**: SQLite writes to a file (`household.db`). Railway's
   filesystem is ephemeral on redeploys unless you attach a Volume. In your
   Railway service settings, add a Volume mounted at `/app` (or wherever your
   working directory is) so `household.db` survives redeploys.
6. Deploy. Check the logs for "Bot starting (polling mode)..." to confirm it's live.

## Project structure

```
household_bot/
├── bot.py                  # Entry point
├── config.py                # Env var loading
├── database/
│   ├── models.py             # SQLAlchemy tables
│   ├── session.py            # Engine/session factory
│   └── crud.py                # All DB reads/writes
├── handlers/
│   ├── start.py               # /start, /help, /chatid
│   ├── task.py                  # /task conversation, /today, /done
│   └── reminder.py            # /reminder conversation
├── scheduler/
│   └── jobs.py                  # Fires due reminders every 60s
├── keyboards.py            # All inline button layouts
├── requirements.txt
├── .env.example
└── Procfile
```

## Adding a new feature (e.g. /shopping)

1. The `ShoppingItem` table already exists in `database/models.py`.
2. Add CRUD functions to `database/crud.py` (e.g. `add_shopping_item`, `get_shopping_list`).
3. Create `handlers/shopping.py` with a `CommandHandler` or `ConversationHandler`.
4. Register it in `bot.py` with `app.add_handler(...)`.

No schema migration needed since the table is already there.

## Known limitations / things to revisit

- Custom date/time parsing is intentionally simple (a few fixed formats).
  If you find yourself fighting the format, that's the sign to add a proper
  parsing library (e.g. `dateparser`) rather than more regex.
- The scheduler checks every 60 seconds, so reminders can fire up to ~1 minute
  late. Fine for household use; tighten the interval in `scheduler/jobs.py` if needed.
- `/done` matches the *first* pending task containing the keyword. If you have
  two similarly-named tasks, be specific enough in the keyword to disambiguate.
