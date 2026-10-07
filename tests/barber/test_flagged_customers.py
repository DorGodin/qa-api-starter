"""A customer who cancelled three bookings, or moved a booking three times, in 90 days has every
booking wait for the barber, at any hour, and silence is never a yes. Never shown to the customer.
The ninety days themselves cannot be reached from outside; the product's own suite holds them."""

from __future__ import annotations

import pytest

from utils.local_time import at_local, local_day


@pytest.fixture
def own_barber(barbers):
    barber = barbers.create_fake_barber()
    return {**barber, "persona": barbers.sign_in_as_persona(barber)}


def cancel_three(bookings, barber, haircut, me, shop_tz, who=None):
    for hhmm in ("10:00", "11:00", "12:00"):
        made = bookings.create_booking(
            barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 4), hhmm), persona=me
        )
        bookings.cancel(made["id"], persona=who or me).assert_ok(200)


def move_times(bookings, barber, haircut, me, shop_tz, count):
    made = bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 4), "09:00"), persona=me
    )
    for n in range(count):
        bookings.move(
            made["id"], at_local(shop_tz, local_day(shop_tz, 5 + n), "09:00"), persona=me
        ).assert_ok(200)


def next_booking(bookings, barber, haircut, me, shop_tz, hhmm="10:00"):
    return bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 9), hhmm), persona=me
    )


def test_three_cancellations_make_the_next_booking_wait_with_no_time_limit(
    bookings, own_barber, haircut, new_customer, shop_tz
):
    me = new_customer()
    cancel_three(bookings, own_barber, haircut, me, shop_tz)

    made = next_booking(bookings, own_barber, haircut, me, shop_tz)

    assert (made["status"], made["approval"], made["decide_by"]) == ("confirmed", "pending", None)


def test_two_cancellations_are_not_enough(bookings, own_barber, haircut, new_customer, shop_tz):
    me = new_customer()
    for hhmm in ("10:00", "11:00"):
        made = bookings.create_booking(
            own_barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 4), hhmm), persona=me
        )
        bookings.cancel(made["id"], persona=me).assert_ok(200)

    assert next_booking(bookings, own_barber, haircut, me, shop_tz)["approval"] is None


def test_three_moves_make_the_next_booking_wait(bookings, own_barber, haircut, new_customer, shop_tz):
    me = new_customer()
    move_times(bookings, own_barber, haircut, me, shop_tz, 3)

    assert next_booking(bookings, own_barber, haircut, me, shop_tz)["approval"] == "pending"


def test_two_moves_are_not_enough(bookings, own_barber, haircut, new_customer, shop_tz):
    me = new_customer()
    move_times(bookings, own_barber, haircut, me, shop_tz, 2)

    assert next_booking(bookings, own_barber, haircut, me, shop_tz)["approval"] is None


@pytest.mark.parametrize("hhmm", ["09:00", "10:00", "16:00", "20:00"])
def test_a_flagged_customer_waits_at_every_hour(bookings, own_barber, haircut, new_customer, shop_tz, hhmm):
    me = new_customer()
    cancel_three(bookings, own_barber, haircut, me, shop_tz)

    assert next_booking(bookings, own_barber, haircut, me, shop_tz, hhmm)["approval"] == "pending"


def test_the_barber_answers_a_flagged_customers_request(bookings, own_barber, haircut, new_customer, shop_tz):
    me = new_customer()
    cancel_three(bookings, own_barber, haircut, me, shop_tz)
    made = next_booking(bookings, own_barber, haircut, me, shop_tz)

    approved = bookings.approve(made["id"], persona=own_barber["persona"]).assert_ok(200).as_dict

    assert approved["approval"] == "approved"


def test_a_flagged_customers_move_waits_again(bookings, own_barber, haircut, new_customer, shop_tz):
    me = new_customer()
    cancel_three(bookings, own_barber, haircut, me, shop_tz)
    made = next_booking(bookings, own_barber, haircut, me, shop_tz)
    bookings.approve(made["id"], persona="owner").assert_ok(200)

    moved = (
        bookings.move(made["id"], at_local(shop_tz, local_day(shop_tz, 9), "11:00"), persona=me)
        .assert_ok(200)
        .as_dict
    )

    assert (moved["approval"], moved["decide_by"]) == ("pending", None)


def test_other_customers_are_not_affected(bookings, own_barber, haircut, new_customer, shop_tz):
    flagged, other = new_customer(), new_customer()
    cancel_three(bookings, own_barber, haircut, flagged, shop_tz)

    assert next_booking(bookings, own_barber, haircut, other, shop_tz)["approval"] is None


def test_cancellations_by_the_shop_are_not_the_customers(
    bookings, own_barber, haircut, new_customer, shop_tz
):
    me = new_customer()
    cancel_three(bookings, own_barber, haircut, me, shop_tz, who="owner")

    assert next_booking(bookings, own_barber, haircut, me, shop_tz)["approval"] is None


def test_moves_by_the_owner_are_not_the_customers(bookings, own_barber, haircut, new_customer, shop_tz):
    me = new_customer()
    made = bookings.create_booking(
        own_barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 4), "09:00"), persona=me
    )
    for n in range(4):
        bookings.move(
            made["id"], at_local(shop_tz, local_day(shop_tz, 5 + n), "09:00"), persona="owner"
        ).assert_ok(200)

    assert next_booking(bookings, own_barber, haircut, me, shop_tz)["approval"] is None
