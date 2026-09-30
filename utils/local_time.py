"""Dates and times on a product's own clock.

One trap is the reason this module exists: subtracting two aware datetimes that
share a tzinfo object is done on the WALL CLOCK, offsets ignored. Midnight to
midnight is then always 24 hours - including the 25-hour day the clocks go
back. Every length below is measured between UTC instants.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from utils.helpers import now_utc


def local_today(tz: ZoneInfo) -> date:
    return now_utc().astimezone(tz).date()


def local_day(tz: ZoneInfo, days_ahead: int) -> date:
    return local_today(tz) + timedelta(days=days_ahead)


def at_local(tz: ZoneInfo, day: date, hhmm: str, fold: int = 0) -> datetime:
    """A wall-clock time on the shop's clock, as an aware UTC instant. `fold=1`
    picks the second occurrence of a time that happens twice."""
    hours, minutes = map(int, hhmm.split(":"))
    return datetime.combine(day, time(hours, minutes), tzinfo=tz).replace(fold=fold).astimezone(UTC)


def day_length(tz: ZoneInfo, day: date) -> timedelta:
    start = datetime.combine(day, time(0), tzinfo=tz).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=tz).astimezone(UTC)
    return end - start


def dst_transitions(tz: ZoneInfo, first: date, last: date) -> list[date]:
    """Local dates between first and last, inclusive, that are not 24 hours long."""
    days, day = [], first
    while day <= last:
        if day_length(tz, day) != timedelta(hours=24):
            days.append(day)
        day += timedelta(days=1)
    return days


def parse_instant(value: str) -> datetime:
    return datetime.fromisoformat(value)
