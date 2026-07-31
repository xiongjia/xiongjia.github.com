"""Parse user-friendly date/time strings for CLI scripts.

Supported inputs (case-insensitive):

    # Today at a given time
    9am, 9pm, 9:30am, 21:30

    # Relative day + optional time
    yesterday, today, yesterday 9am

    # Day-of-month + time (backfill: this month, e.g. 30th at 9am)
    30, 30 9am, 31 9pm, 30 21:36

    # Full date with optional time
    2026-07-30, 2026-07-30 21:36, 2026/7/30 9am, 2026.07.30

Anything unparseable falls back to the current time.
"""

import re
import warnings
from datetime import datetime, timedelta

_ISO_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d",
    "%Y-%m-%d",
    "%Y.%m.%d",
)

_DATE_STRICT_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M%z",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d",
)


def parse_date_strict(raw) -> datetime | None:
    """Strict date parse with no fallback; returns ``None`` when unparseable.

    Accepts ``datetime``/``date`` objects as-is and a fixed set of string
    formats. Unlike ``parse_datetime_arg`` this never falls back to the
    current time — callers treat ``None`` as a hard error.
    """
    if isinstance(raw, datetime):
        return raw
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    for fmt in _DATE_STRICT_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def parse_datetime_arg(raw: str | None, now: datetime | None = None) -> datetime:
    """Parse a user-friendly date/time string; falls back to ``now``."""
    if raw is None:
        raw = ""
    now = now or datetime.now()
    s = raw.strip()
    if not s:
        return now

    # Full ISO-ish formats
    for fmt in _ISO_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass

    s = s.lower()

    # --- Date part ---
    day_offset = 0
    day_num = None
    year, month = now.year, now.month

    if re.search(r"\byesterday\b", s):
        day_offset = -1
        s = re.sub(r"\byesterday\b", " ", s)
    elif re.search(r"\btoday\b", s):
        day_offset = 0
        s = re.sub(r"\btoday\b", " ", s)

    m = re.match(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        day_num = int(m.group(3))
        s = s[m.end() :]

    s = s.strip()
    m = re.match(r"^(\d{1,2})", s)
    if m:
        day = int(m.group(1))
        rest = s[m.end() :].strip()
        # "9am" / "21:30" also start with a number — treat as time, not day
        is_time_token = bool(re.match(r"^:", rest) or re.match(r"^(am|pm)\b", rest))
        if 1 <= day <= 31 and not is_time_token:
            day_num = day
            s = rest

    # --- Time part ---
    hour, minute = now.hour, now.minute
    has_time = False

    m = re.match(r"(\d{1,2})(?::(\d{1,2}))?\s*(am|pm)?", s)
    if m and m.group(1) is not None:
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        ampm = m.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        has_time = True

    if not 0 <= hour <= 23:
        warnings.warn(f"Invalid hour {hour}; using 23 instead", stacklevel=2)
        hour = 23
    if not 0 <= minute <= 59:
        warnings.warn(f"Invalid minute {minute}; using 59 instead", stacklevel=2)
        minute = 59

    # --- Combine ---
    if day_num is not None:
        try:
            base = datetime(year, month, day_num)
        except ValueError:
            warnings.warn(
                f"Invalid day {day_num} for {year}-{month:02d}; using current time instead",
                stacklevel=2,
            )
            # ignore any parsed time too — fall back to the current moment entirely
            return now.replace(second=0, microsecond=0)
    else:
        base = datetime(now.year, now.month, now.day) + timedelta(days=day_offset)

    if has_time:
        return base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return base.replace(hour=now.hour, minute=now.minute, second=0, microsecond=0)
