"""
Reminder Bot - Clone of @yastabot
A "fire and forget" Telegram reminder bot with natural language parsing.

Setup:
  pip install "python-telegram-bot>=20.0" python-dateutil pytz APScheduler

Run (Windows PowerShell):
  $env:BOT_TOKEN="your_token_here"; python bot.py
"""

import os
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytz

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from db import (
    init_db,
    save_reminder,
    get_reminders_for_user,
    delete_reminder,
    get_reminder_by_id,
    get_user_timezone,
    set_user_timezone,
    get_all_pending_reminders,
    mark_reminder_sent,
)
from reminder_parser import parse_reminder_command

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

scheduler = AsyncIOScheduler()


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def format_reminder_list(reminders: list) -> str:
    if not reminders:
        return "📭 You have no upcoming reminders."
    lines = ["📋 *Your reminders:*\n"]
    for r in reminders:
        rid, chat_id, text, trigger_type, trigger_data, tz, sent = r
        when = trigger_data if trigger_type == "recurring" else trigger_data
        lines.append(f"🔔 *[{rid}]* {text}\n   ⏰ `{when}`\n")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────

async def fire_reminder(app, chat_id: int, reminder_id: int, text: str, trigger_type: str):
    try:
        await app.bot.send_message(
            chat_id=chat_id,
            text=f"⏰ *Reminder:* {text}",
            parse_mode="Markdown",
        )
        if trigger_type == "once":
            mark_reminder_sent(reminder_id)
    except Exception as e:
        logger.error(f"Failed to send reminder {reminder_id}: {e}")


def schedule_reminder(app, reminder_id: int, chat_id: int, text: str,
                      trigger_type: str, trigger_data: str, tz_name: str):
    job_id = f"reminder_{reminder_id}"
    user_tz = pytz.timezone(tz_name) if tz_name else pytz.UTC

    if trigger_type == "once":
        # trigger_data is ISO datetime string (naive, in user's TZ)
        dt_naive = datetime.fromisoformat(trigger_data)
        dt_aware = user_tz.localize(dt_naive)
        if dt_aware < datetime.now(pytz.UTC):
            return  # already past
        scheduler.add_job(
            fire_reminder,
            trigger=DateTrigger(run_date=dt_aware),
            args=[app, chat_id, reminder_id, text, trigger_type],
            id=job_id,
            replace_existing=True,
        )

    elif trigger_type == "recurring":
        # trigger_data is a cron expression like "0 17 * * 1-5"
        scheduler.add_job(
            fire_reminder,
            trigger=CronTrigger.from_crontab(trigger_data, timezone=user_tz),
            args=[app, chat_id, reminder_id, text, trigger_type],
            id=job_id,
            replace_existing=True,
        )

    elif trigger_type == "interval":
        # trigger_data is seconds as string
        seconds = int(trigger_data)
        scheduler.add_job(
            fire_reminder,
            trigger=IntervalTrigger(seconds=seconds, timezone=user_tz),
            args=[app, chat_id, reminder_id, text, trigger_type],
            id=job_id,
            replace_existing=True,
        )


def restore_scheduled_reminders(app):
    reminders = get_all_pending_reminders()
    for r in reminders:
        rid, chat_id, text, trigger_type, trigger_data, tz, sent = r
        if not sent:
            schedule_reminder(app, rid, chat_id, text, trigger_type, trigger_data, tz or "UTC")


# ─────────────────────────────────────────────
# COMMAND HANDLERS
# ─────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Welcome to Reminder Bot!*\n\n"
        "I'm a fire-and-forget reminder bot. Just tell me when and what to remind you about!\n\n"
        "*Examples:*\n"
        "• `/remindme in 30 minutes to leave for work`\n"
        "• `/remindme at 4pm to pick up the kids`\n"
        "• `/remindme tomorrow at 9am to call the dentist`\n"
        "• `/remindme every day at 8am to drink water`\n"
        "• `/remindme every monday at 9am to send status update`\n"
        "• `/remindme on january 5th to pay rent`\n\n"
        "*Commands:*\n"
        "`/remindme` — set a reminder\n"
        "`/list` — view your reminders\n"
        "`/delete <id>` — delete a reminder\n"
        "`/timezone` — set your timezone\n"
        "`/help` — show help\n"
        "`/tutorial` — show tutorial\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 *Help*\n\n"
        "*General formula:*\n"
        "`/remindme [date/time] [to/that] [text]`\n\n"
        "*One-time reminders:*\n"
        "• `/remindme in 5 minutes to check the oven`\n"
        "• `/remindme in 2 hours to take medicine`\n"
        "• `/remindme at 3pm to call mom`\n"
        "• `/remindme tomorrow at 9am for the meeting`\n"
        "• `/remindme on friday at 6pm to leave early`\n"
        "• `/remindme on december 25 to wish merry christmas`\n\n"
        "*Recurring reminders:*\n"
        "• `/remindme every day at 8am to drink water`\n"
        "• `/remindme every monday at 9am for standup`\n"
        "• `/remindme every weekday at 5pm to log hours`\n"
        "• `/remindme every 2 hours to stretch`\n"
        "• `/remindme every saturday at 10am to clean the house`\n\n"
        "*Managing reminders:*\n"
        "• `/list` — see all reminders\n"
        "• `/list work` — filter reminders containing 'work'\n"
        "• `/delete 3` — delete reminder #3\n"
        "• `/timezone America/New_York` — set timezone\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_tutorial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎓 *Tutorial*\n\n"
        "1️⃣ *Set your timezone first:*\n"
        "   `/timezone Europe/London`\n\n"
        "2️⃣ *Create a one-time reminder:*\n"
        "   `/remindme in 10 minutes to take a break`\n\n"
        "3️⃣ *Create a recurring reminder:*\n"
        "   `/remindme every day at 7am to wake up`\n\n"
        "4️⃣ *List your reminders:*\n"
        "   `/list`\n\n"
        "5️⃣ *Delete a reminder:*\n"
        "   `/delete 1`\n\n"
        "💡 *Tip:* The bot uses natural language — just write naturally!\n"
        "Try phrases like `next monday`, `in 3 days`, `every friday`, etc."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args

    if not args:
        current_tz = get_user_timezone(chat_id) or "UTC"
        msg = (
            f"🌍 Your current timezone is: `{current_tz}`\n\n"
            "To change it, use:\n`/timezone America/New_York`\n\n"
            "Find your timezone name at:\nhttps://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    tz_name = args[0]
    try:
        ZoneInfo(tz_name)  # validate
        set_user_timezone(chat_id, tz_name)
        await update.message.reply_text(
            f"✅ Timezone set to `{tz_name}`!", parse_mode="Markdown"
        )
    except ZoneInfoNotFoundError:
        await update.message.reply_text(
            f"❌ Unknown timezone `{tz_name}`.\n"
            "Find valid names at: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
            parse_mode="Markdown",
        )


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    keyword = " ".join(context.args).lower() if context.args else None

    reminders = get_reminders_for_user(chat_id)
    if keyword:
        reminders = [r for r in reminders if keyword in r[2].lower()]

    await update.message.reply_text(
        format_reminder_list(reminders), parse_mode="Markdown"
    )


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text(
            "Usage: `/delete <id>` — get IDs from `/list`", parse_mode="Markdown"
        )
        return

    try:
        rid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid numeric ID.")
        return

    reminder = get_reminder_by_id(rid)
    if not reminder or reminder[1] != chat_id:
        await update.message.reply_text("❌ Reminder not found.")
        return

    delete_reminder(rid)
    job_id = f"reminder_{rid}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    await update.message.reply_text(f"✅ Reminder #{rid} deleted.")


async def cmd_remindme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    full_text = " ".join(context.args).strip()

    if not full_text:
        await update.message.reply_text(
            "Usage: `/remindme [time] [to/that] [message]`\n\nExample: `/remindme in 30 minutes to leave for work`",
            parse_mode="Markdown",
        )
        return

    user_tz_name = get_user_timezone(chat_id) or "UTC"
    user_tz = pytz.timezone(user_tz_name)
    now_user = datetime.now(user_tz)

    try:
        result = parse_reminder_command(full_text, now_user)
    except Exception as e:
        logger.error(f"Parse error: {e}")
        await update.message.reply_text(
            "❌ Sorry, I couldn't understand that time format.\n"
            "Try something like: `/remindme in 30 minutes to check the oven`",
            parse_mode="Markdown",
        )
        return

    if result is None:
        await update.message.reply_text(
            "❌ I couldn't parse that reminder. Try:\n"
            "• `/remindme in 30 minutes to leave`\n"
            "• `/remindme at 4pm to pick up the kids`\n"
            "• `/remindme every day at 8am to drink water`",
            parse_mode="Markdown",
        )
        return

    trigger_type, trigger_data, reminder_text, human_when = result

    rid = save_reminder(chat_id, reminder_text, trigger_type, trigger_data, user_tz_name)
    schedule_reminder(
        context.application, rid, chat_id, reminder_text,
        trigger_type, trigger_data, user_tz_name
    )

    await update.message.reply_text(
        f"✅ Got it! I'll remind you *{human_when}*:\n_{reminder_text}_\n\n"
        f"_(Reminder ID: {rid})_",
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────
# FALLBACK (direct messages without /)
# ─────────────────────────────────────────────

async def handle_plain_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if any(kw in text for kw in ["remind", "remindme"]):
        # treat as /remindme
        context.args = update.message.text.strip().split()
        await cmd_remindme(update, context)
    else:
        await update.message.reply_text(
            "Use `/remindme [time] [to] [message]` to set a reminder.\nType /help for examples.",
            parse_mode="Markdown",
        )


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

async def post_init(app: Application) -> None:
    """Called after the bot is initialized — safe place to start scheduler."""
    scheduler.start()
    restore_scheduled_reminders(app)
    logger.info("Scheduler started and reminders restored.")


async def post_shutdown(app: Application) -> None:
    """Called on shutdown — cleanly stop scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)


def main():
    init_db()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("tutorial", cmd_tutorial))
    app.add_handler(CommandHandler("timezone", cmd_timezone))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(CommandHandler("remindme", cmd_remindme))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plain_message))

    logger.info("Bot started. Polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
