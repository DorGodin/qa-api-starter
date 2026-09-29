from datetime import datetime, timedelta, timezone

import pytest

from utils.helpers import assert_not_prod, cached_lookup, date_range, now_utc, to_iso


def test_now_utc_is_aware():
    assert now_utc().tzinfo is not None


def test_to_iso_uses_z_suffix_and_milliseconds():
    value = datetime(2026, 4, 12, 0, 0, 0, 123456, tzinfo=timezone.utc)
    assert to_iso(value) == "2026-04-12T00:00:00.123Z"


def test_to_iso_rejects_naive_datetime():
    with pytest.raises(ValueError):
        to_iso(datetime(2026, 4, 12))


def test_date_range_orders_start_before_end():
    start, end = date_range(start_offset_days=-1, duration_days=5)
    assert start < end


def test_cached_lookup_calls_once_per_argument_set():
    calls = []

    @cached_lookup
    def lookup(name):
        calls.append(name)
        return name.upper()

    assert lookup("a") == "A"
    assert lookup("a") == "A"
    assert lookup("b") == "B"
    assert calls == ["a", "b"]


def test_assert_not_prod_raises_on_prod(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    with pytest.raises(AssertionError, match="never run against prod"):
        assert_not_prod("seed_something")


def test_assert_not_prod_passes_elsewhere(monkeypatch):
    monkeypatch.setenv("ENV", "staging")
    assert_not_prod("seed_something")
