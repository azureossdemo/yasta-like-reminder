# 🔔 Reminder Bot — @yastabot Clone

A **fire-and-forget** Telegram reminder bot. Just type naturally and the bot handles the rest — no buttons, no menus.

---

## ✨ Features

| Feature | Example |
|---|---|
| Relative time | `/remindme in 30 minutes to leave for work` |
| Absolute time | `/remindme at 4pm to pick up the kids` |
| Tomorrow | `/remindme tomorrow at 9am to call dentist` |
| Specific day | `/remindme on friday at 6pm to leave early` |
| Specific date | `/remindme on january 5th to pay rent` |
| Next weekday | `/remindme next monday at 9am for standup` |
| Daily recurring | `/remindme every day at 8am to drink water` |
| Weekly recurring | `/remindme every monday at 9am to send update` |
| Weekday only | `/remindme every weekday at 5pm to log hours` |
| Every N weeks | `/remindme every 2 saturdays to fill up gas` |
| Every X hours | `/remindme every 2 hours to stretch` |
| Filter list | `/list work` — shows only reminders with "work" |
| Delete | `/delete 3` — deletes reminder #3 |
| Timezone | `/timezone Europe/Warsaw` |

---

## 🚀 Quick Start

### 1. Create a Bot Token

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow prompts
3. Copy the token (looks like `123456789:ABCdef...`)

### 2. Option A — Run with Docker (recommended)

```bash
# Clone or download this folder, then:
cd reminder_bot

export BOT_TOKEN="your_token_here"
docker-compose up -d
```

### 2. Option B — Run with Python directly

```bash
cd reminder_bot

# Install dependencies
pip install -r requirements.txt

# Run
BOT_TOKEN="your_token_here" python bot.py
```

---

## 📋 Commands

| Command | Description |
|---|---|
| `/start` | Welcome message and quick guide |
| `/help` | Full help with examples |
| `/tutorial` | Step-by-step tutorial |
| `/remindme [time] [to] [text]` | Create a reminder |
| `/list` | List all your reminders |
| `/list <keyword>` | Filter reminders by keyword |
| `/delete <id>` | Delete a reminder by ID |
| `/timezone <tz>` | Set your timezone |

---

## 🗂️ File Structure

```
reminder_bot/
├── bot.py          # Main bot — handlers, scheduler
├── parser.py       # Natural language date/time parser
├── db.py           # SQLite persistence layer
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 🌍 Timezone Setup

Set your timezone so all times are interpreted correctly:

```
/timezone Europe/Warsaw
/timezone America/New_York
/timezone Asia/Tokyo
```

Find your timezone name: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | *(required)* | Telegram bot token from BotFather |
| `DB_PATH` | `reminders.db` | Path to SQLite database file |

---

## 🔄 Persistence

All reminders are stored in a local SQLite database (`reminders.db`). When the bot restarts, all pending reminders are automatically rescheduled.

- **One-time** reminders: sent once, then marked as done
- **Recurring** reminders (cron): fire indefinitely
- **Interval** reminders: fire every N seconds/minutes/hours

---

## 🐛 Troubleshooting

**Bot doesn't respond:** Double-check your `BOT_TOKEN`.

**Times are wrong:** Set your timezone with `/timezone`.

**Reminder didn't fire:** Check logs with `docker-compose logs -f`.
