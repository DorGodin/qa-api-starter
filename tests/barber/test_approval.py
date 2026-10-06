"""A customer's booking that starts from 14:00 up to 16:00 waits for its barber.
It holds the chair meanwhile; the barber or the owner answers; no answer in two
hours and it stands."""

from __future__ import annotations

from datetime import timedelta

import pytest

from utils.assertions import assert_refused
from utils.helpers import now_utc
from utils.local_time import at_local, local_day, parse_instant


@pytest.fixture
def own_barber(barbers):
    barber = barbers.create_fake_barber()
    return {**barber, "persona": barbers.sign_in_as_persona(barber)}


def book(bookings, barber, haircut, me, shop_tz, hhmm, days=5):
    return bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, days), hhmm), persona=me
    )


@pytest.mark.parametrize(
    ("hhmm", "approval"),
    [("13:45", None), ("14:00", "pending"), ("15:45", "pending"), ("16:00", None), ("10:00", None)],
)
def test_the_hours_that_wait_start_at_two_and_end_before_four(
    bookings, own_barber, haircut, new_customer, shop_tz, hhmm, approval
):
    made = book(bookings, own_barber, haircut, new_customer(), shop_tz, hhmm)

    assert made["approval"] == approval
    assert made["status"] == "confirmed"


def test_the_wait_ends_in_two_hours_and_is_also_told_on_the_shops_clock(
    bookings, own_barber, haircut, new_customer, shop_tz
):
    made = book(bookings, own_barber, haircut, new_customer(), shop_tz, "15:00")

    wait = parse_instant(made["decide_by"]) - now_utc()

    assert timedelta(hours=1, minutes=50) < wait <= timedelta(hours=2), wait
    assert made["decide_by_local"][11:16] == (parse_instant(made["decide_by"]).astimezone(shop_tz)).strftime(
        "%H:%M"
    )


def test_a_waiting_booking_holds_the_chair(bookings, own_barber, haircut, new_customer, shop_tz):
    book(bookings, own_barber, haircut, new_customer(), shop_tz, "15:00")

    taken = bookings.book(
        own_barber["id"],
        haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 5), "15:00"),
        persona=new_customer(),
    )

    assert_refused(taken, 409, "slot_taken")


def test_the_barber_approves_and_saying_it_again_changes_nothing(
    bookings, own_barber, haircut, new_customer, shop_tz
):
    made = book(bookings, own_barber, haircut, new_customer(), shop_tz, "15:00")

    approved = bookings.approve(made["id"], persona=own_barber["persona"]).assert_ok(200).as_dict
    again = bookings.approve(made["id"], persona=own_barber["persona"]).assert_ok(200).as_dict

    assert (approved["approval"], approved["status"], approved["decide_by"]) == (
        "approved",
        "confirmed",
        None,
    )
    assert again == approved


def test_a_declined_booking_is_cancelled_by_the_shop_and_frees_the_time(
    bookings, own_barber, haircut, new_customer, shop_tz
):
    made = book(bookings, own_barber, haircut, new_customer(), shop_tz, "15:00")

    declined = bookings.decline(made["id"], persona=own_barber["persona"]).assert_ok(200).as_dict

    assert (declined["status"], declined["approval"], declined["cancelled_by"]) == (
        "cancelled",
        "declined",
        "staff",
    )
    bookings.create_booking(
        own_barber["id"],
        haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 5), "15:00"),
        persona=new_customer(),
    )


def test_a_declined_booking_no_longer_counts_toward_the_limit(
    bookings, own_barber, haircut, new_customer, shop_tz
):
    me = new_customer()
    waiting = book(bookings, own_barber, haircut, me, shop_tz, "15:00")
    book(bookings, own_barber, haircut, me, shop_tz, "10:00")
    bookings.decline(waiting["id"], persona=own_barber["persona"]).assert_ok(200)

    book(bookings, own_barber, haircut, me, shop_tz, "11:00")


def test_the_owner_may_answer_for_any_barber(bookings, own_barber, haircut, new_customer, shop_tz):
    made = book(bookings, own_barber, haircut, new_customer(), shop_tz, "14:30")

    approved = bookings.approve(made["id"], persona="owner").assert_ok(200).as_dict

    assert approved["approval"] == "approved"


def test_a_barber_cannot_answer_for_another_barbers_booking(
    barbers, bookings, own_barber, haircut, new_customer, shop_tz
):
    other = barbers.sign_in_as_persona(barbers.create_fake_barber())
    made = book(bookings, own_barber, haircut, new_customer(), shop_tz, "15:00")

    assert_refused(bookings.approve(made["id"], persona=other), 404, "not_found")
    assert_refused(bookings.decline(made["id"], persona=other), 404, "not_found")


def test_a_customer_cannot_answer_for_the_barber(bookings, own_barber, haircut, new_customer, shop_tz):
    me = new_customer()
    made = book(bookings, own_barber, haircut, me, shop_tz, "15:00")

    assert_refused(bookings.approve(made["id"], persona=me), 403, "forbidden")
    assert_refused(bookings.decline(made["id"], persona=me), 403, "forbidden")


def test_there_is_nothing_to_answer_in_a_booking_outside_the_hours(
    bookings, own_barber, haircut, new_customer, shop_tz
):
    made = book(bookings, own_barber, haircut, new_customer(), shop_tz, "10:00")

    assert_refused(bookings.approve(made["id"], persona="owner"), 409, "nothing_to_approve")


def test_an_answer_given_cannot_be_reversed(bookings, own_barber, haircut, new_customer, shop_tz):
    approved = book(bookings, own_barber, haircut, new_customer(), shop_tz, "14:00")
    declined = book(bookings, own_barber, haircut, new_customer(), shop_tz, "15:00")
    bookings.approve(approved["id"], persona="owner").assert_ok(200)
    bookings.decline(declined["id"], persona="owner").assert_ok(200)

    assert_refused(bookings.decline(approved["id"], persona="owner"), 409, "already_approved")
    assert_refused(bookings.approve(declined["id"], persona="owner"), 409, "already_declined")


def test_the_owner_booking_a_guest_in_the_hours_needs_no_yes(bookings, own_barber, haircut, shop_tz):
    made = (
        bookings.book_guest(
            own_barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 5), "15:00")
        )
        .assert_ok(201)
        .as_dict
    )

    assert made["approval"] is None


def test_the_customer_cancelling_a_waiting_booking_ends_the_wait(
    bookings, own_barber, haircut, new_customer, shop_tz
):
    me = new_customer()
    made = book(bookings, own_barber, haircut, me, shop_tz, "15:00")

    cancelled = bookings.cancel(made["id"], persona=me).assert_ok(200).as_dict

    assert (cancelled["status"], cancelled["approval"]) == ("cancelled", None)


def test_the_barbers_diary_shows_the_booking_waiting_for_them(
    bookings, own_barber, haircut, new_customer, shop_tz
):
    made = book(bookings, own_barber, haircut, new_customer(), shop_tz, "15:00")

    [seen] = bookings.listing(persona=own_barber["persona"])["content"]

    assert (seen["id"], seen["approval"]) == (made["id"], "pending")


def test_moving_into_the_hours_makes_the_booking_wait_and_out_of_them_ends_it(
    bookings, own_barber, haircut, new_customer, shop_tz
):
    me, day = new_customer(), local_day(shop_tz, 5)
    made = book(bookings, own_barber, haircut, me, shop_tz, "10:00")

    into = bookings.move(made["id"], at_local(shop_tz, day, "15:00"), persona=me).assert_ok(200).as_dict
    out = bookings.move(made["id"], at_local(shop_tz, day, "11:00"), persona=me).assert_ok(200).as_dict

    assert (into["approval"], out["approval"]) == ("pending", None)


def test_the_owner_moving_a_booking_into_the_hours_decides_it(
    bookings, own_barber, haircut, new_customer, shop_tz
):
    made = book(bookings, own_barber, haircut, new_customer(), shop_tz, "10:00")

    moved = (
        bookings.move(made["id"], at_local(shop_tz, local_day(shop_tz, 5), "15:00"), persona="owner")
        .assert_ok(200)
        .as_dict
    )

    assert moved["approval"] is None
