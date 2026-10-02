"""The owner books, by name, someone who phoned or walked in - into the same
diary, under the same rules, with no account and no limit on bookings ahead."""

import pytest

from utils.assertions import assert_refused
from utils.local_time import at_local, local_day, parse_instant


def test_a_guest_booking_takes_the_time_from_everyone_else(
    barbers, bookings, barber, haircut, new_customer, shop_tz
):
    day = local_day(shop_tz, 5)
    me = new_customer()

    booked = (
        bookings.book_guest(barber["id"], haircut["id"], at_local(shop_tz, day, "11:00"), "משה")
        .assert_ok(201)
        .as_dict
    )

    assert booked["guest_name"] == "משה" and booked["customer_id"] is None
    assert booked["price_minor"] == haircut["price_minor"]
    assert at_local(shop_tz, day, "11:00") not in [
        parse_instant(s["start"]) for s in barbers.slots(barber["id"], day, haircut["id"], persona=me)
    ]
    assert_refused(
        bookings.book(barber["id"], haircut["id"], at_local(shop_tz, day, "11:00"), persona=me),
        409,
        "slot_taken",
    )


def test_a_guest_booking_cannot_take_a_customers_time(bookings, barber, haircut, new_customer, shop_tz):
    day = local_day(shop_tz, 5)
    bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, day, "13:00"), persona=new_customer()
    )

    assert_refused(
        bookings.book_guest(barber["id"], haircut["id"], at_local(shop_tz, day, "13:15")), 409, "slot_taken"
    )


def test_the_owner_is_not_held_to_the_customers_limit(bookings, barber, trim, shop_tz):
    day = local_day(shop_tz, 6)

    for hhmm in ("10:00", "10:30", "11:00", "11:30"):
        bookings.book_guest(barber["id"], trim["id"], at_local(shop_tz, day, hhmm)).assert_ok(201)


@pytest.mark.parametrize("name", ["", "   ", "א" * 81], ids=["empty", "spaces", "too-long"])
def test_a_guest_needs_a_real_name(bookings, barber, trim, shop_tz, name):
    resp = bookings.book_guest(
        barber["id"], trim["id"], at_local(shop_tz, local_day(shop_tz, 6), "15:00"), name
    )

    assert resp.status_code == 422


def test_only_the_owner_books_guests_and_a_customer_never_sees_them(
    barbers, bookings, barber, haircut, new_customer, shop_tz
):
    me = new_customer()
    start = at_local(shop_tz, local_day(shop_tz, 7), "11:00")
    own = barbers.create_fake_barber()

    assert_refused(bookings.book_guest(barber["id"], haircut["id"], start, persona=me), 403, "forbidden")
    assert_refused(
        bookings.book_guest(barber["id"], haircut["id"], start, persona=barbers.sign_in_as_persona(own)),
        403,
        "forbidden",
    )
    booked = bookings.book_guest(barber["id"], haircut["id"], start).assert_ok(201).as_dict
    assert bookings.get_by_id(booked["id"], persona=me).status_code == 404
    assert bookings.cancel(booked["id"], persona=me).status_code == 404


def test_the_owner_moves_a_guest_booking_past_another_barbers_customer(
    barbers, bookings, barber, haircut, new_customer, shop_tz
):
    other = barbers.create_fake_barber()
    day = local_day(shop_tz, 8)
    booked = (
        bookings.book_guest(barber["id"], haircut["id"], at_local(shop_tz, day, "10:00"))
        .assert_ok(201)
        .as_dict
    )
    bookings.create_booking(
        other["id"], haircut["id"], at_local(shop_tz, day, "16:00"), persona=new_customer()
    )

    moved = (
        bookings.move(booked["id"], at_local(shop_tz, day, "16:00"), persona="owner").assert_ok(200).as_dict
    )

    assert parse_instant(moved["start"]) == at_local(shop_tz, day, "16:00")
    assert bookings.cancel(booked["id"], persona="owner").assert_ok(200).as_dict["status"] == "cancelled"
