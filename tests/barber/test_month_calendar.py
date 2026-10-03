"""The month's calendar the booking page draws: a day's count is always the
number of times its own list offers, a day off is a day not worked, and only
months inside the booking window are answered."""

from datetime import date, timedelta

from obj.barber import BOOKING_WINDOW_DAYS
from utils.assertions import assert_refused
from utils.local_time import at_local, local_day


def test_every_day_counts_what_its_list_offers_a_booking_and_a_day_off_included(
    barbers, bookings, haircut, new_customer, shop_tz
):
    barber = barbers.create_fake_barber(opening="10:00", closing="13:00")
    booked, off = local_day(shop_tz, 3), local_day(shop_tz, 4)
    persona = new_customer()
    bookings.book(barber["id"], haircut["id"], at_local(shop_tz, booked, "11:00"), persona=persona).assert_ok(
        201
    )
    barbers.add_time_off(barber["id"], off).assert_ok(201)

    for month in {booked.isoformat()[:7], off.isoformat()[:7]}:
        listed = (
            barbers.days(barber["id"], month, haircut["id"], persona=persona).assert_ok(200).as_dict["days"]
        )
        for entry in listed:
            day = date.fromisoformat(entry["date"])
            expected = barbers.slots(barber["id"], day, haircut["id"], persona=persona)
            assert entry["free"] == len(expected), entry
            assert entry["works"] is (day != off), entry


def test_months_outside_the_booking_window_are_refused_with_the_reason(barbers, barber, haircut, shop_tz):
    gone = local_day(shop_tz, 0).replace(day=1) - timedelta(days=1)
    far = local_day(shop_tz, BOOKING_WINDOW_DAYS).replace(day=28) + timedelta(days=10)

    assert_refused(barbers.days(barber["id"], gone.isoformat()[:7], haircut["id"]), 422, "in_past")
    assert_refused(barbers.days(barber["id"], far.isoformat()[:7], haircut["id"]), 422, "beyond_window")
