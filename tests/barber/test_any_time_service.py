"""A service that works at any time (an emergency haircut) opens the whole day on every day, whatever
the barber's hours and days off - and a booking already there still takes its time."""

from __future__ import annotations

import pytest

from obj.barber.barbers import WEEK
from utils.assertions import assert_refused
from utils.local_time import at_local, local_day


@pytest.fixture
def emergency(services):
    return services.create_fake_service(any_time=True)


@pytest.fixture
def short_barber(barbers):
    barber = barbers.create_fake_barber()
    hours = {"hours": {**dict.fromkeys(WEEK, ["09:00", "10:00"]), "sat": None}}
    barbers.set_hours(barber["id"], hours).assert_ok(200)
    return barber


def starts(barbers, barber, service, day, persona):
    return [s["start"] for s in barbers.slots(barber["id"], day, service["id"], persona=persona)]


def test_a_service_says_whether_it_works_at_any_time_and_only_the_owner_sets_it(services, new_customer):
    service = services.create_fake_service()

    assert service["any_time"] is False
    assert_refused(
        services.update_by_id(service["id"], {"any_time": True}, persona=new_customer()), 403, "forbidden"
    )
    on = services.update_by_id(service["id"], {"any_time": True}, persona="owner").assert_ok(200).as_dict
    assert on["any_time"] is True


def test_it_offers_the_whole_day_where_an_ordinary_service_offers_the_barbers_hour(
    barbers, short_barber, haircut, emergency, new_customer, shop_tz
):
    me, day = new_customer(), local_day(shop_tz, 4)

    ordinary = starts(barbers, short_barber, haircut, day, me)
    anytime = starts(barbers, short_barber, emergency, day, me)

    assert len(ordinary) < 6
    assert len(anytime) > 40
    assert at_local(shop_tz, day, "03:00").strftime("%Y-%m-%dT%H:%M:%SZ") in anytime


def test_it_offers_a_day_the_barber_is_closed_and_a_day_off(
    barbers, short_barber, haircut, emergency, new_customer, shop_tz
):
    me = new_customer()
    saturday = next(local_day(shop_tz, n) for n in range(2, 12) if local_day(shop_tz, n).weekday() == 5)
    off = local_day(shop_tz, 5)
    barbers.add_time_off(short_barber["id"], off).assert_ok(201)

    assert starts(barbers, short_barber, haircut, saturday, me) == []
    assert len(starts(barbers, short_barber, emergency, saturday, me)) > 40
    assert len(starts(barbers, short_barber, emergency, off, me)) > 40


def test_a_booking_already_there_still_takes_its_time(
    barbers, bookings, short_barber, haircut, emergency, new_customer, shop_tz
):
    day = local_day(shop_tz, 6)
    bookings.create_booking(
        short_barber["id"], haircut["id"], at_local(shop_tz, day, "09:00"), persona=new_customer()
    )
    bookings.create_booking(
        short_barber["id"], emergency["id"], at_local(shop_tz, day, "18:00"), persona=new_customer()
    )

    offered = starts(barbers, short_barber, emergency, day, new_customer())
    refused = bookings.book(
        short_barber["id"], emergency["id"], at_local(shop_tz, day, "18:00"), persona=new_customer()
    )

    def utc(hhmm):
        return at_local(shop_tz, day, hhmm).strftime("%Y-%m-%dT%H:%M:%SZ")

    assert utc("09:00") not in offered and utc("18:00") not in offered
    assert utc("08:45") not in offered
    assert utc("18:30") in offered
    assert_refused(refused, 409, "slot_taken")


def test_an_emergency_booking_takes_the_time_from_the_ordinary_services_too(
    bookings, short_barber, haircut, emergency, new_customer, shop_tz
):
    day = local_day(shop_tz, 6)
    bookings.create_booking(
        short_barber["id"], emergency["id"], at_local(shop_tz, day, "09:00"), persona=new_customer()
    )

    ordinary = bookings.book(
        short_barber["id"], haircut["id"], at_local(shop_tz, day, "09:00"), persona=new_customer()
    )

    assert_refused(ordinary, 409, "slot_taken")


def test_it_is_booked_at_three_in_the_morning_and_an_ordinary_service_is_refused(
    bookings, short_barber, haircut, emergency, new_customer, shop_tz
):
    start = at_local(shop_tz, local_day(shop_tz, 7), "03:00")

    bookings.create_booking(short_barber["id"], emergency["id"], start, persona=new_customer())

    assert_refused(
        bookings.book(short_barber["id"], haircut["id"], start, persona=new_customer()), 422, "outside_hours"
    )


def test_the_calendar_shows_every_day_free_for_it(
    barbers, short_barber, haircut, emergency, new_customer, shop_tz
):
    me, month = new_customer(), local_day(shop_tz, 3).isoformat()[:7]

    ordinary = (
        barbers.days(short_barber["id"], month, haircut["id"], persona=me).assert_ok(200).as_dict["days"]
    )
    anytime = (
        barbers.days(short_barber["id"], month, emergency["id"], persona=me).assert_ok(200).as_dict["days"]
    )

    assert any(not d["works"] for d in ordinary)
    assert anytime and all(d["works"] and d["free"] > 0 for d in anytime[1:])


def test_it_stays_inside_the_booking_window(barbers, short_barber, emergency, new_customer, shop_tz):
    refused = barbers.availability(
        short_barber["id"], local_day(shop_tz, 120), emergency["id"], persona=new_customer()
    )

    assert refused.status_code == 422


def test_it_is_booked_on_a_day_off_and_on_a_closed_day(
    barbers, bookings, short_barber, haircut, emergency, new_customer, shop_tz
):
    off = local_day(shop_tz, 8)
    saturday = next(local_day(shop_tz, n) for n in range(2, 12) if local_day(shop_tz, n).weekday() == 5)
    barbers.add_time_off(short_barber["id"], off).assert_ok(201)

    for day in (off, saturday):
        made = bookings.create_booking(
            short_barber["id"], emergency["id"], at_local(shop_tz, day, "09:00"), persona=new_customer()
        )
        assert made["status"] == "confirmed"
    assert_refused(
        bookings.book(
            short_barber["id"], haircut["id"], at_local(shop_tz, off, "09:00"), persona=new_customer()
        ),
        422,
        "barber_off",
    )
