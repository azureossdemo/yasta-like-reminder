"""
db.py — SQLite persistence layer for reminders.
"""

import sqlite3
import os
from typing import Optional

DB_PATH = os.environ.get("DB_PATH", "reminders.db")


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id       INTEGER NOT NULL,
                text          TEXT    NOT NULL,
                trigger_type  TEXT    NOT NULL,   -- "once" | "recurring" | "interval"
                trigger_data  TEXT    NOT NULL,   -- ISO datetime or cron string or seconds
                tz            TEXT    NOT NULL DEFAULT 'UTC',
                sent          INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS user_timezones (
                chat_id   INTEGER PRIMARY KEY,
                tz        TEXT NOT NULL DEFAULT 'UTC'
            )
        """)
        con.commit()


def save_reminder(chat_id: int, text: str, trigger_type: str,
                  trigger_data: str, tz: str) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO reminders (chat_id, text, trigger_type, trigger_data, tz) VALUES (?,?,?,?,?)",
            (chat_id, text, trigger_type, trigger_data, tz),
        )
        con.commit()
        return cur.lastrowid


def get_reminders_for_user(chat_id: int) -> list:
    with _conn() as con:
        rows = con.execute(
            "SELECT id, chat_id, text, trigger_type, trigger_data, tz, sent "
            "FROM reminders WHERE chat_id=? AND sent=0 ORDER BY id ASC",
            (chat_id,),
        ).fetchall()
    return rows


def get_reminder_by_id(rid: int) -> Optional[tuple]:
    with _conn() as con:
        row = con.execute(
            "SELECT id, chat_id, text, trigger_type, trigger_data, tz, sent FROM reminders WHERE id=?",
            (rid,),
        ).fetchone()
    return row


def delete_reminder(rid: int):
    with _conn() as con:
        con.execute("DELETE FROM reminders WHERE id=?", (rid,))
        con.commit()


def mark_reminder_sent(rid: int):
    with _conn() as con:
        con.execute("UPDATE reminders SET sent=1 WHERE id=?", (rid,))
        con.commit()


def get_all_pending_reminders() -> list:
    with _conn() as con:
        rows = con.execute(
            "SELECT id, chat_id, text, trigger_type, trigger_data, tz, sent "
            "FROM reminders WHERE sent=0",
        ).fetchall()
    return rows


def get_user_timezone(chat_id: int) -> Optional[str]:
    with _conn() as con:
        row = con.execute(
            "SELECT tz FROM user_timezones WHERE chat_id=?", (chat_id,)
        ).fetchone()
    return row[0] if row else None


def set_user_timezone(chat_id: int, tz: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO user_timezones (chat_id, tz) VALUES (?,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET tz=excluded.tz",
            (chat_id, tz),
        )
        con.commit()
