"""A review comes after the appointment. A booking cannot be made in the past, so from outside
only the refusals can be reached; the review of a finished booking is tested in the product's
own suite and, on the page, with a booking the page is told is over."""

from __future__ import annotations

import pytest

from utils.assertions import assert_refused
from utils.local_time import at_local, local_day


@pytest.fixture
def upcoming(barbers, bookings, haircut, new_customer, shop_tz):
    me = new_customer()
    barber = barbers.create_fake_barber()
    booking = bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 6), "10:00"), persona=me
    )
    return {"me": me, "booking": booking}


def test_a_booking_has_no_review_and_is_not_reviewable_before_it_is_over(upcoming):
    assert upcoming["booking"]["review"] is None
    assert upcoming["booking"]["reviewable"] is False


def test_a_booking_that_is_not_over_cannot_be_reviewed_or_given_words(bookings, upcoming):
    booking, me = upcoming["booking"], upcoming["me"]

    assert_refused(bookings.review(booking["id"], persona=me), 409, "not_over_yet")
    assert_refused(bookings.review_words(booking["id"], "x", persona=me), 409, "not_over_yet")


@pytest.mark.parametrize("stars", [0, 6, -1])
def test_stars_outside_one_to_five_are_refused(bookings, upcoming, stars):
    refused = bookings.review(upcoming["booking"]["id"], persona=upcoming["me"], stars=stars)

    assert refused.status_code == 422


def test_only_a_customer_reviews_and_only_their_own_booking(bookings, upcoming, new_customer):
    booking = upcoming["booking"]

    assert_refused(bookings.review(booking["id"], persona=new_customer()), 404, "not_found")
    assert_refused(bookings.review(booking["id"], persona="owner"), 403, "forbidden")


def test_a_cancelled_booking_is_not_reviewable(bookings, upcoming):
    bookings.cancel(upcoming["booking"]["id"], persona=upcoming["me"]).assert_ok(200)

    assert_refused(bookings.review(upcoming["booking"]["id"], persona=upcoming["me"]), 409, "not_reviewable")
