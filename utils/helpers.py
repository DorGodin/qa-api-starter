from __future__ import annotations

import functools
import os
from datetime import UTC, datetime, timedelta

UTC = UTC


def now_utc() -> datetime:
    return datetime.now(UTC)


def to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("naive datetime: build it with now_utc()")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"


def future_date(days: int = 30) -> str:
    return to_iso(now_utc() + timedelta(days=days))


def past_date(days: int = 1) -> str:
    return to_iso(now_utc() - timedelta(days=days))


def date_range(start_offset_days: int = -1, duration_days: int = 30) -> tuple[str, str]:
    start = now_utc() + timedelta(days=start_offset_days)
    return to_iso(start), to_iso(start + timedelta(days=duration_days))


def cached_lookup(func):
    """Memoise an idempotent lookup for the life of the process.

    Use only for reference data that cannot change during a run.
    """
    cache: dict[tuple, object] = {}

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key = (args, tuple(sorted(kwargs.items())))
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    wrapper.cache_clear = cache.clear  # type: ignore[attr-defined]
    return wrapper


def current_env() -> str:
    return os.getenv("ENV", "local")


def assert_not_prod(caller: str) -> None:
    """First statement of every helper that creates or mutates server state."""
    env = current_env()
    assert env != "prod", (
        f"{caller} creates data and must never run against prod. ENV={env!r}. "
        "Set ENV to a test environment."
    )
