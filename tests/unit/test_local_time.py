from datetime import date, timedelta
from zoneinfo import ZoneInfo

from utils.local_time import at_local, day_length, dst_transitions

TZ = ZoneInfo("Asia/Jerusalem")


def test_the_fall_back_day_is_25_hours_long():
    assert day_length(TZ, date(2026, 10, 25)) == timedelta(hours=25)


def test_the_spring_forward_day_is_23_hours_long():
    assert day_length(TZ, date(2027, 3, 26)) == timedelta(hours=23)


def test_an_ordinary_day_is_24_hours():
    assert day_length(TZ, date(2026, 10, 12)) == timedelta(hours=24)


def test_both_transitions_of_a_year_are_found_and_nothing_else():
    assert dst_transitions(TZ, date(2026, 9, 1), date(2027, 5, 1)) == [date(2026, 10, 25), date(2027, 3, 26)]


def test_the_repeated_hour_is_two_different_instants():
    first = at_local(TZ, date(2026, 10, 25), "01:30", fold=0)
    second = at_local(TZ, date(2026, 10, 25), "01:30", fold=1)

    assert second - first == timedelta(hours=1)
