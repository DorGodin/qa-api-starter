"""A double tap on "Book" with the same Idempotency-Key is one booking, not two."""

import secrets

from utils.assertions import assert_refused
from utils.concurrency import at_once
from utils.local_time import at_local, local_day


def test_the_same_key_twice_returns_the_first_booking(bookings, barber, haircut, new_customer, shop_tz):
    me, key = new_customer(), secrets.token_hex(8)
    start = at_local(shop_tz, local_day(shop_tz, 8), "10:00")

    first = bookings.book(barber["id"], haircut["id"], start, persona=me, idempotency_key=key)
    second = bookings.book(barber["id"], haircut["id"], start, persona=me, idempotency_key=key)

    assert first.status_code == second.status_code == 201
    assert first.as_dict["id"] == second.as_dict["id"]
    assert second.raw.headers.get("Idempotent-Replayed") == "true"
    assert bookings.listing(persona=me)["total"] == 1


def test_a_key_reused_for_a_different_booking_is_refused(bookings, barber, haircut, new_customer, shop_tz):
    me, key = new_customer(), secrets.token_hex(8)
    day = local_day(shop_tz, 8)
    bookings.book(
        barber["id"], haircut["id"], at_local(shop_tz, day, "12:00"), persona=me, idempotency_key=key
    ).assert_ok(201)

    reused = bookings.book(
        barber["id"], haircut["id"], at_local(shop_tz, day, "15:00"), persona=me, idempotency_key=key
    )

    assert_refused(reused, 409, "idempotency_mismatch")
    assert bookings.listing(persona=me)["total"] == 1


def test_a_double_tap_that_arrives_at_the_same_instant_is_still_one_booking(
    bookings, barber, haircut, new_customer, shop_tz
):
    me, key = new_customer(), secrets.token_hex(8)
    start = at_local(shop_tz, local_day(shop_tz, 9), "10:00")

    responses = at_once(
        [lambda: bookings.book(barber["id"], haircut["id"], start, persona=me, idempotency_key=key)] * 2
    )

    assert [r.status_code for r in responses] == [201, 201]
    assert len({r.as_dict["id"] for r in responses}) == 1
    assert bookings.listing(persona=me)["total"] == 1


def test_the_same_key_from_two_customers_is_two_bookings(bookings, barber, haircut, new_customer, shop_tz):
    key = secrets.token_hex(8)
    day = local_day(shop_tz, 9)

    one = bookings.book(
        barber["id"],
        haircut["id"],
        at_local(shop_tz, day, "13:00"),
        persona=new_customer(),
        idempotency_key=key,
    )
    two = bookings.book(
        barber["id"],
        haircut["id"],
        at_local(shop_tz, day, "14:00"),
        persona=new_customer(),
        idempotency_key=key,
    )

    assert one.status_code == two.status_code == 201
    assert (
        one.as_dict["id"] != two.as_dict["id"]
    ), "a key belongs to one customer; another's must not replay it"
