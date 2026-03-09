"""
parser.py — Natural language reminder time parser.

Supports:
  One-time:
    in X minutes/hours/days/weeks
    at HH:MM / at 3pm / at 3:30pm
    tomorrow [at TIME]
    on WEEKDAY [at TIME]
    on MONTH DAY [at TIME]
    next WEEKDAY [at TIME]
    in X days/weeks

  Recurring:
    every day/night [at TIME]
    every WEEKDAY [at TIME]
    every weekday/weekend [at TIME]
    every X hours/minutes
    every X weeks on WEEKDAY
    every X WEEKDAYS (e.g. every 2 saturdays)
    every morning/evening/night

Returns:
  (trigger_type, trigger_data, reminder_text, human_when)
  trigger_type: "once" | "recurring"
  trigger_data:
    once      → ISO datetime string (naive in user tz)
    recurring → cron expression string
"""

import re
from datetime import datetime, timedelta, time as dt_time


# ─── Constants ────────────────────────────────────────────────

WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
    "thirty": 30, "forty": 40, "sixty": 60,
    "a": 1, "an": 1,
}

SPECIAL_TIMES = {
    "morning": dt_time(8, 0),
    "noon": dt_time(12, 0),
    "afternoon": dt_time(14, 0),
    "evening": dt_time(18, 0),
    "night": dt_time(21, 0),
    "midnight": dt_time(0, 0),
}


# ─── Helpers ──────────────────────────────────────────────────

def _parse_num(s: str) -> int | None:
    s = s.strip().lower()
    if s.isdigit():
        return int(s)
    return NUMBER_WORDS.get(s)


def _parse_time(s: str) -> dt_time | None:
    """Parse 3pm, 15:30, 3:30pm, noon, morning etc."""
    s = s.strip().lower()
    if s in SPECIAL_TIMES:
        return SPECIAL_TIMES[s]
    # 3pm / 3:30pm / 15:00
    m = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$', s)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        meridiem = m.group(3)
        if meridiem == 'pm' and hour != 12:
            hour += 12
        elif meridiem == 'am' and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return dt_time(hour, minute)
    return None


def _next_weekday(from_dt: datetime, weekday: int) -> datetime:
    """Return next occurrence of weekday (0=Mon) strictly after from_dt."""
    days_ahead = weekday - from_dt.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return from_dt + timedelta(days=days_ahead)


def _set_time(dt: datetime, t: dt_time) -> datetime:
    return dt.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)


def _extract_text(s: str) -> str:
    """Strip leading 'to', 'that', 'about' from reminder text."""
    s = s.strip()
    for prefix in ("to ", "that ", "about "):
        if s.lower().startswith(prefix):
            s = s[len(prefix):]
    return s.strip() or "⏰ Reminder"


def _format_human_once(dt: datetime, now: datetime) -> str:
    delta = dt - now
    total_secs = int(delta.total_seconds())
    if total_secs < 60:
        return f"in {total_secs} seconds"
    if total_secs < 3600:
        return f"in {total_secs // 60} minute(s)"
    if total_secs < 86400:
        return f"in {total_secs // 3600} hour(s)"
    return f"on {dt.strftime('%A, %B %d at %-I:%M %p')}"


def _weekday_cron(day_of_week: int, t: dt_time) -> str:
    return f"{t.minute} {t.hour} * * {day_of_week}"


def _daily_cron(t: dt_time) -> str:
    return f"{t.minute} {t.hour} * * *"


# ─── Main parser ──────────────────────────────────────────────

def parse_reminder_command(text: str, now: datetime):
    """
    Parse a reminder command string.
    Returns (trigger_type, trigger_data, reminder_text, human_when) or None.
    """
    text = text.strip()
    lower = text.lower()

    # ── Try to split into TIME_PART and TEXT_PART ──
    # Look for " to ", " that ", after the time expression
    time_part, text_part = _split_time_and_text(text)
    if time_part is None:
        return None

    reminder_text = _extract_text(text_part)
    tp = time_part.lower().strip()

    # ── RECURRING patterns ──────────────────────────────────

    # "every day/daily/night/morning/evening at TIME"
    m = re.match(r'^every\s+(day|daily|morning|night|evening|noon|afternoon)(?:\s+at\s+(.+))?$', tp)
    if m:
        t = _parse_time(m.group(2)) if m.group(2) else SPECIAL_TIMES.get(m.group(1), dt_time(9, 0))
        if t is None:
            t = dt_time(9, 0)
        cron = _daily_cron(t)
        return ("recurring", cron, reminder_text, f"every day at {t.strftime('%-I:%M %p')}")

    # "every weekday/weekdays at TIME"
    m = re.match(r'^every\s+weekdays?(?:\s+at\s+(.+))?$', tp)
    if m:
        t = _parse_time(m.group(1)) if m.group(1) else dt_time(9, 0)
        if t is None: t = dt_time(9, 0)
        cron = f"{t.minute} {t.hour} * * 1-5"
        return ("recurring", cron, reminder_text, f"every weekday at {t.strftime('%-I:%M %p')}")

    # "every weekend/weekends at TIME"
    m = re.match(r'^every\s+weekends?(?:\s+at\s+(.+))?$', tp)
    if m:
        t = _parse_time(m.group(1)) if m.group(1) else dt_time(10, 0)
        if t is None: t = dt_time(10, 0)
        cron = f"{t.minute} {t.hour} * * 6,0"
        return ("recurring", cron, reminder_text, f"every weekend at {t.strftime('%-I:%M %p')}")

    # "every WEEKDAY at TIME" / "every 2 saturdays at TIME"
    m = re.match(r'^every\s+(\w+)\s+(' + '|'.join(WEEKDAYS.keys()) + r')(?:\s+at\s+(.+))?$', tp)
    if m:
        n_str = m.group(1)
        wday_name = m.group(2)
        n = _parse_num(n_str)
        t = _parse_time(m.group(3)) if m.group(3) else dt_time(9, 0)
        if t is None: t = dt_time(9, 0)
        if n and wday_name in WEEKDAYS:
            wday = WEEKDAYS[wday_name]
            if n == 1:
                cron = _weekday_cron(wday, t)
                return ("recurring", cron, reminder_text, f"every {wday_name} at {t.strftime('%-I:%M %p')}")
            # every N weeks on weekday — use interval approach; approximate with cron note
            # We'll store as interval in seconds (N * 7 days)
            seconds = n * 7 * 86400
            # Find next occurrence first
            next_dt = _next_weekday(now, wday)
            next_dt = _set_time(next_dt, t)
            return ("interval", str(seconds), reminder_text, f"every {n} {wday_name}s at {t.strftime('%-I:%M %p')}")

    # "every WEEKDAY at TIME" (no multiplier)
    m = re.match(r'^every\s+(' + '|'.join(WEEKDAYS.keys()) + r')(?:\s+at\s+(.+))?$', tp)
    if m:
        wday_name = m.group(1)
        t = _parse_time(m.group(2)) if m.group(2) else dt_time(9, 0)
        if t is None: t = dt_time(9, 0)
        wday = WEEKDAYS[wday_name]
        cron = _weekday_cron(wday, t)
        return ("recurring", cron, reminder_text, f"every {wday_name} at {t.strftime('%-I:%M %p')}")

    # "every X minutes/hours"
    m = re.match(r'^every\s+(\w+)\s+(minute|minutes|min|mins|hour|hours|hr|hrs)$', tp)
    if m:
        n = _parse_num(m.group(1))
        unit = m.group(2)
        if n:
            if "min" in unit:
                seconds = n * 60
                return ("interval", str(seconds), reminder_text, f"every {n} minute(s)")
            else:
                seconds = n * 3600
                return ("interval", str(seconds), reminder_text, f"every {n} hour(s)")

    # "every hour"
    if tp == "every hour":
        return ("interval", "3600", reminder_text, "every hour")

    # "every minute"
    if tp == "every minute":
        return ("interval", "60", reminder_text, "every minute")

    # "every month on DAY at TIME"
    m = re.match(r'^every\s+month(?:\s+on\s+(?:the\s+)?(\d+)(?:st|nd|rd|th)?)?(?:\s+at\s+(.+))?$', tp)
    if m:
        day = int(m.group(1)) if m.group(1) else 1
        t = _parse_time(m.group(2)) if m.group(2) else dt_time(9, 0)
        if t is None: t = dt_time(9, 0)
        cron = f"{t.minute} {t.hour} {day} * *"
        return ("recurring", cron, reminder_text, f"every month on the {day} at {t.strftime('%-I:%M %p')}")

    # ── ONE-TIME patterns ────────────────────────────────────

    # "in X minutes/hours/days/weeks"
    m = re.match(r'^in\s+(\w+)\s+(second|seconds|sec|secs|minute|minutes|min|mins|hour|hours|hr|hrs|day|days|week|weeks)$', tp)
    if m:
        n = _parse_num(m.group(1))
        unit = m.group(2)
        if n:
            if "sec" in unit:
                dt = now + timedelta(seconds=n)
            elif "min" in unit:
                dt = now + timedelta(minutes=n)
            elif "hour" in unit or unit.startswith("hr"):
                dt = now + timedelta(hours=n)
            elif "day" in unit:
                dt = now + timedelta(days=n)
            else:  # weeks
                dt = now + timedelta(weeks=n)
            human = _format_human_once(dt, now)
            return ("once", dt.strftime("%Y-%m-%dT%H:%M:%S"), reminder_text, human)

    # "at TIME"
    m = re.match(r'^at\s+(.+)$', tp)
    if m:
        t = _parse_time(m.group(1))
        if t:
            dt = _set_time(now, t)
            if dt <= now:
                dt += timedelta(days=1)
            human = _format_human_once(dt, now)
            return ("once", dt.strftime("%Y-%m-%dT%H:%M:%S"), reminder_text, human)

    # "tomorrow [at TIME]"
    m = re.match(r'^tomorrow(?:\s+at\s+(.+))?$', tp)
    if m:
        t = _parse_time(m.group(1)) if m.group(1) else dt_time(9, 0)
        if t is None: t = dt_time(9, 0)
        dt = _set_time(now + timedelta(days=1), t)
        human = f"tomorrow at {t.strftime('%-I:%M %p')}"
        return ("once", dt.strftime("%Y-%m-%dT%H:%M:%S"), reminder_text, human)

    # "next WEEKDAY [at TIME]"
    m = re.match(r'^next\s+(' + '|'.join(WEEKDAYS.keys()) + r')(?:\s+at\s+(.+))?$', tp)
    if m:
        wday_name = m.group(1)
        t = _parse_time(m.group(2)) if m.group(2) else dt_time(9, 0)
        if t is None: t = dt_time(9, 0)
        wday = WEEKDAYS[wday_name]
        dt = _next_weekday(now, wday)
        dt = _set_time(dt, t)
        human = f"next {wday_name} at {t.strftime('%-I:%M %p')}"
        return ("once", dt.strftime("%Y-%m-%dT%H:%M:%S"), reminder_text, human)

    # "on WEEKDAY [at TIME]"
    m = re.match(r'^on\s+(' + '|'.join(WEEKDAYS.keys()) + r')(?:\s+at\s+(.+))?$', tp)
    if m:
        wday_name = m.group(1)
        t = _parse_time(m.group(2)) if m.group(2) else dt_time(9, 0)
        if t is None: t = dt_time(9, 0)
        wday = WEEKDAYS[wday_name]
        dt = _next_weekday(now, wday)
        dt = _set_time(dt, t)
        human = f"on {wday_name} at {t.strftime('%-I:%M %p')}"
        return ("once", dt.strftime("%Y-%m-%dT%H:%M:%S"), reminder_text, human)

    # "on MONTH DAY [at TIME]" e.g. "on january 5th at 3pm"
    months_pattern = '|'.join(MONTHS.keys())
    m = re.match(rf'^on\s+({months_pattern})\s+(\d+)(?:st|nd|rd|th)?(?:\s+at\s+(.+))?$', tp)
    if m:
        month_name = m.group(1)
        day = int(m.group(2))
        t = _parse_time(m.group(3)) if m.group(3) else dt_time(9, 0)
        if t is None: t = dt_time(9, 0)
        month = MONTHS[month_name]
        year = now.year
        dt = now.replace(month=month, day=day, hour=t.hour, minute=t.minute, second=0, microsecond=0)
        if dt <= now:
            dt = dt.replace(year=year + 1)
        human = f"on {month_name.capitalize()} {day} at {t.strftime('%-I:%M %p')}"
        return ("once", dt.strftime("%Y-%m-%dT%H:%M:%S"), reminder_text, human)

    # "WEEKDAY at TIME" (no "on")
    m = re.match(r'^(' + '|'.join(WEEKDAYS.keys()) + r')\s+at\s+(.+)$', tp)
    if m:
        wday_name = m.group(1)
        t = _parse_time(m.group(2))
        if t:
            wday = WEEKDAYS[wday_name]
            dt = _next_weekday(now, wday)
            dt = _set_time(dt, t)
            human = f"on {wday_name} at {t.strftime('%-I:%M %p')}"
            return ("once", dt.strftime("%Y-%m-%dT%H:%M:%S"), reminder_text, human)

    # "in X days and Y hours"
    m = re.match(r'^in\s+(\w+)\s+days?\s+and\s+(\w+)\s+hours?$', tp)
    if m:
        d = _parse_num(m.group(1))
        h = _parse_num(m.group(2))
        if d and h:
            dt = now + timedelta(days=d, hours=h)
            human = _format_human_once(dt, now)
            return ("once", dt.strftime("%Y-%m-%dT%H:%M:%S"), reminder_text, human)

    # "on WEEKDAY at TIME and on WEEKDAY2 at TIME2" (multiple schedules — use first only)
    m = re.match(r'^on\s+(' + '|'.join(WEEKDAYS.keys()) + r')\s+at\s+(\S+)\s+and\s+on', tp)
    if m:
        wday_name = m.group(1)
        t = _parse_time(m.group(2))
        if t:
            wday = WEEKDAYS[wday_name]
            dt = _next_weekday(now, wday)
            dt = _set_time(dt, t)
            human = f"on {wday_name} at {t.strftime('%-I:%M %p')} (and more)"
            return ("once", dt.strftime("%Y-%m-%dT%H:%M:%S"), reminder_text, human)

    return None


def _split_time_and_text(text: str):
    """
    Split text into (time_expr, reminder_text).
    Tries multiple separator strategies.
    """
    lower = text.lower()

    # Strategy 1: split on " to " — take first occurrence
    idx = lower.find(" to ")
    if idx != -1:
        return text[:idx], text[idx + 4:]

    # Strategy 2: split on " that "
    idx = lower.find(" that ")
    if idx != -1:
        return text[:idx], text[idx + 6:]

    # Strategy 3: split on ":" (e.g. "tomorrow: pick up kids")
    idx = lower.find(":")
    if idx != -1:
        return text[:idx], text[idx + 1:]

    # Strategy 4: no separator — try to detect time expression at start
    # Common time starters
    time_starters = (
        r'^(in\s+\w+\s+\w+)',
        r'^(at\s+\S+)',
        r'^(tomorrow(?:\s+at\s+\S+)?)',
        r'^(next\s+\w+(?:\s+at\s+\S+)?)',
        r'^(on\s+\w+(?:\s+\w+)?(?:\s+at\s+\S+)?)',
        r'^(every\s+\w+(?:\s+at\s+\S+)?)',
    )
    import re as _re
    for pattern in time_starters:
        m = _re.match(pattern, lower)
        if m:
            end = m.end()
            if end < len(text):
                return text[:end], text[end:].strip()

    # Can't split — return None
    return None, None
