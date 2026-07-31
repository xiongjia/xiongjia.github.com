"""Unit tests for the user-friendly date/time parser in shared/date.py."""

import warnings
from datetime import datetime

from shared.date import parse_datetime_arg

NOW = datetime(2026, 7, 31, 14, 5)


def test_today_time_formats():
    """9am/9pm/24h/am-pm with minutes resolve to today."""
    assert parse_datetime_arg("9am", NOW) == datetime(2026, 7, 31, 9, 0)
    assert parse_datetime_arg("9pm", NOW) == datetime(2026, 7, 31, 21, 0)
    assert parse_datetime_arg("9:30am", NOW) == datetime(2026, 7, 31, 9, 30)
    assert parse_datetime_arg("9:5am", NOW) == datetime(2026, 7, 31, 9, 5)
    assert parse_datetime_arg("21:30", NOW) == datetime(2026, 7, 31, 21, 30)


def test_relative_days():
    """yesterday/today keep the current time unless a time is given."""
    assert parse_datetime_arg("yesterday", NOW) == datetime(2026, 7, 30, 14, 5)
    assert parse_datetime_arg("yesterday 9am", NOW) == datetime(2026, 7, 30, 9, 0)
    assert parse_datetime_arg("today", NOW) == datetime(2026, 7, 31, 14, 5)


def test_day_of_month_backfill():
    """A bare day number (or day + time) resolves to this month."""
    assert parse_datetime_arg("30", NOW) == datetime(2026, 7, 30, 14, 5)
    assert parse_datetime_arg("30 9am", NOW) == datetime(2026, 7, 30, 9, 0)
    assert parse_datetime_arg("31 9pm", NOW) == datetime(2026, 7, 31, 21, 0)


def test_full_dates():
    """ISO-ish full dates parse directly."""
    assert parse_datetime_arg("2026-07-30", NOW) == datetime(2026, 7, 30, 0, 0)
    assert parse_datetime_arg("2026-07-30 21:36", NOW) == datetime(2026, 7, 30, 21, 36)
    assert parse_datetime_arg("2026/7/30 9am", NOW) == datetime(2026, 7, 30, 9, 0)


def test_word_boundaries():
    """'yesterday' as a substring must not match."""
    assert parse_datetime_arg("yesterdays", NOW) == datetime(2026, 7, 31, 14, 5)
    assert parse_datetime_arg("notyesterday", NOW) == datetime(2026, 7, 31, 14, 5)


def test_invalid_day_warns():
    """An impossible day (e.g. 31 Feb) warns and falls back to now."""
    feb = datetime(2026, 2, 10, 14, 5)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = parse_datetime_arg("31 9am", feb)
    assert result == feb
    assert len(caught) == 1
    assert "Invalid day" in str(caught[0].message)


def test_invalid_minute_warns():
    """Minutes out of range (e.g. 9:75) warn instead of silently clamping."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = parse_datetime_arg("9:75", NOW)
    assert result == datetime(2026, 7, 31, 9, 59)
    assert len(caught) == 1
    assert "Invalid minute" in str(caught[0].message)


def test_empty_and_garbage_fall_back_to_now():
    """Empty or unparseable input falls back to now."""
    assert parse_datetime_arg("", NOW) == NOW
    assert parse_datetime_arg("whatever", NOW) == NOW
    assert parse_datetime_arg(None, NOW) == NOW
