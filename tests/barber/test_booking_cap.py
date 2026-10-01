"""A customer holds at most two bookings ahead, or one account - or a script -
could take every free time in the shop. Cancelling one makes room; a booking
already past does not count."""

from __future__ import annotations

from utils.concurrency import at_once
from utils.local_time import at_local, local_day


def test_two_bookings_ahead_and_the_third_is_refused_naming_the_limit(
    barbers, bookings, haircut, new_customer, shop_tz
):
    barber, me, day = barbers.create_fake_barber(), new_customer(), local_day(shop_tz, 3)
    for hhmm in ("10:00", "11:00"):
        bookings.create_booking(barber["id"], haircut["id"], at_local(shop_tz, day, hhmm), persona=me)

    third = bookings.book(barber["id"], haircut["id"], at_local(shop_tz, day, "12:00"), persona=me)

    assert third.status_code == 409
    assert third.as_dict["code"] == "too_many_bookings"
    assert third.as_dict["limit"] == 2


def test_cancelling_one_makes_room_for_another(barbers, bookings, haircut, new_customer, shop_tz):
    barber, me, day = barbers.create_fake_barber(), new_customer(), local_day(shop_tz, 3)
    first = bookings.create_booking(barber["id"], haircut["id"], at_local(shop_tz, day, "10:00"), persona=me)
    bookings.create_booking(barber["id"], haircut["id"], at_local(shop_tz, day, "11:00"), persona=me)

    bookings.cancel(first["id"], persona=me).assert_ok(200)

    bookings.create_booking(barber["id"], haircut["id"], at_local(shop_tz, day, "12:00"), persona=me)


def test_one_customer_at_the_limit_does_not_hold_back_another(
    barbers, bookings, haircut, new_customer, shop_tz
):
    barber, me, someone_else, day = (
        barbers.create_fake_barber(),
        new_customer(),
        new_customer(),
        local_day(shop_tz, 3),
    )
    for hhmm in ("10:00", "11:00"):
        bookings.create_booking(barber["id"], haircut["id"], at_local(shop_tz, day, hhmm), persona=me)

    bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, day, "12:00"), persona=someone_else
    )


def test_bookings_sent_at_once_cannot_pass_the_limit_together(
    barbers, bookings, haircut, new_customer, shop_tz
):
    barber, me, day = barbers.create_fake_barber(), new_customer(), local_day(shop_tz, 4)
    bookings.create_booking(barber["id"], haircut["id"], at_local(shop_tz, day, "09:00"), persona=me)
    starts = [at_local(shop_tz, day, f"{h}:00") for h in (11, 12, 13, 14, 15)]

    responses = at_once(
        [lambda s=s: bookings.book(barber["id"], haircut["id"], s, persona=me) for s in starts]
    )

    codes = sorted(r.status_code for r in responses)
    assert codes == [201, 409, 409, 409, 409], f"one room left, so exactly one gets it: {codes}"
    assert {r.as_dict["code"] for r in responses if r.status_code == 409} == {"too_many_bookings"}
    assert len([b for b in bookings.listing(persona=me)["content"] if b["status"] == "confirmed"]) == 2
