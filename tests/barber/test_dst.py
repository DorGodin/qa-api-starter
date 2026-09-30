"""Daylight saving, on whichever transition falls inside the booking window.

The dates are found, not hardcoded: a suite pinned to one date stops testing
anything the day that date passes. When no transition is bookable right now,
the tests skip and say so.
"""

from datetime import timedelta

import pytest

from obj.barber import BOOKING_WINDOW_DAYS, SLOT_MINUTES
from utils.local_time import at_local, day_length, dst_transitions, local_day, parse_instant


@pytest.fixture(scope="module")
def transitions(shop_tz):
    found = dst_transitions(shop_tz, local_day(shop_tz, 1), local_day(shop_tz, BOOKING_WINDOW_DAYS - 1))
    if not found:
        pytest.skip(f"no daylight-saving change in {shop_tz.key} inside the next {BOOKING_WINDOW_DAYS} days")
    return found


def test_a_transition_day_offers_the_hours_it_really_has(barbers, trim, transitions, shop_tz):
    for day in transitions:
        barber = barbers.create_fake_barber()
        starts = [parse_instant(s["start"]) for s in barbers.slots(barber["id"], day, trim["id"])]
        expected = int(day_length(shop_tz, day) / timedelta(minutes=SLOT_MINUTES))

        assert (
            len(starts) == expected
        ), f"{day} is {day_length(shop_tz, day)} long: expected {expected} slots, got {len(starts)}"
        assert len(set(starts)) == len(starts), "two slots are the same instant"
        gaps = {b - a for a, b in zip(starts, starts[1:], strict=False)}
        assert gaps == {
            timedelta(minutes=SLOT_MINUTES)
        }, f"slots are not one quarter hour apart in real time: {gaps}"


def test_the_repeated_hour_can_be_booked_twice_as_two_different_moments(
    barbers, bookings, trim, transitions, new_customer, shop_tz
):
    fall_backs = [d for d in transitions if day_length(shop_tz, d) > timedelta(hours=24)]
    if not fall_backs:
        pytest.skip("the transition inside the window moves the clocks forward; no hour repeats")
    day = fall_backs[0]
    barber = barbers.create_fake_barber()
    repeated = next(
        s["start_local"][11:16]
        for s in barbers.slots(barber["id"], day, trim["id"])
        if [x["start_local"][11:16] for x in barbers.slots(barber["id"], day, trim["id"])].count(
            s["start_local"][11:16]
        )
        == 2
    )

    first = bookings.create_booking(
        barber["id"], trim["id"], at_local(shop_tz, day, repeated, fold=0), persona=new_customer()
    )
    second = bookings.create_booking(
        barber["id"], trim["id"], at_local(shop_tz, day, repeated, fold=1), persona=new_customer()
    )

    assert parse_instant(second["start"]) - parse_instant(first["start"]) == timedelta(hours=1)
    assert first["start_local"][11:16] == second["start_local"][11:16] == repeated
    assert first["start_local"][-6:] != second["start_local"][-6:], "the offset is what tells the two apart"


def test_opening_time_stays_on_the_local_clock_across_the_change(barbers, trim, transitions, shop_tz):
    day = transitions[0]
    barber = barbers.create_fake_barber(opening="09:00", closing="19:00")
    before, after = day - timedelta(days=1), day + timedelta(days=1)
    if before < local_day(shop_tz, 1):
        pytest.skip("the day before the change has already passed")

    first_before = parse_instant(barbers.slots(barber["id"], before, trim["id"])[0]["start_local"])
    first_after = parse_instant(barbers.slots(barber["id"], after, trim["id"])[0]["start_local"])

    assert first_before.strftime("%H:%M") == first_after.strftime("%H:%M") == "09:00"
    assert (
        first_before.utcoffset() != first_after.utcoffset()
    ), "opening moved with the clock, so its UTC instant must move"
