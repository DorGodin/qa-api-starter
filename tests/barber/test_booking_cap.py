"""A customer holds only so many bookings ahead - five unless the shop sets another number - or one account,
or a script, could take every free time in the shop. Cancelling one makes room; a booking already past does
not count."""

from __future__ import annotations

from utils.concurrency import at_once
from utils.local_time import at_local, local_day


def hours(first: int, count: int) -> list[str]:
    return [f"{h:02d}:00" for h in range(first, first + count)]


def fill(bookings, barber, haircut, me, day, count, shop_tz) -> list[dict]:
    return [
        bookings.create_booking(barber["id"], haircut["id"], at_local(shop_tz, day, hhmm), persona=me)
        for hhmm in hours(6, count)
    ]


def test_the_shop_lets_a_customer_hold_five_bookings_ahead(bookings_ahead_limit):
    assert bookings_ahead_limit == 5


def test_at_the_limit_the_next_is_refused_naming_the_limit(
    barbers, bookings, haircut, new_customer, shop_tz, bookings_ahead_limit
):
    barber, me, day = barbers.create_fake_barber(), new_customer(), local_day(shop_tz, 3)
    fill(bookings, barber, haircut, me, day, bookings_ahead_limit, shop_tz)

    next_one = bookings.book(barber["id"], haircut["id"], at_local(shop_tz, day, "20:00"), persona=me)

    assert next_one.status_code == 409
    assert next_one.as_dict["code"] == "too_many_bookings"
    assert next_one.as_dict["limit"] == bookings_ahead_limit


def test_cancelling_one_makes_room_for_another(
    barbers, bookings, haircut, new_customer, shop_tz, bookings_ahead_limit
):
    barber, me, day = barbers.create_fake_barber(), new_customer(), local_day(shop_tz, 3)
    first, *_ = fill(bookings, barber, haircut, me, day, bookings_ahead_limit, shop_tz)

    bookings.cancel(first["id"], persona=me).assert_ok(200)

    bookings.create_booking(barber["id"], haircut["id"], at_local(shop_tz, day, "20:00"), persona=me)


def test_one_customer_at_the_limit_does_not_hold_back_another(
    barbers, bookings, haircut, new_customer, shop_tz, bookings_ahead_limit
):
    barber, me, someone_else, day = (
        barbers.create_fake_barber(),
        new_customer(),
        new_customer(),
        local_day(shop_tz, 3),
    )
    fill(bookings, barber, haircut, me, day, bookings_ahead_limit, shop_tz)

    bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, day, "20:00"), persona=someone_else
    )


def test_bookings_sent_at_once_cannot_pass_the_limit_together(
    barbers, bookings, haircut, new_customer, shop_tz, bookings_ahead_limit
):
    barber, me, day = barbers.create_fake_barber(), new_customer(), local_day(shop_tz, 4)
    fill(bookings, barber, haircut, me, day, bookings_ahead_limit - 1, shop_tz)
    starts = [at_local(shop_tz, day, hhmm) for hhmm in hours(16, 5)]

    responses = at_once(
        [lambda s=s: bookings.book(barber["id"], haircut["id"], s, persona=me) for s in starts]
    )

    codes = sorted(r.status_code for r in responses)
    assert codes == [201, 409, 409, 409, 409], f"one room left, so exactly one gets it: {codes}"
    assert {r.as_dict["code"] for r in responses if r.status_code == 409} == {"too_many_bookings"}
    confirmed = [b for b in bookings.listing(persona=me)["content"] if b["status"] == "confirmed"]
    assert len(confirmed) == bookings_ahead_limit
