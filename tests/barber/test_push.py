"""Web Push: a customer is told when the barber answers and a barber when a request waits. Only "there
is news" is sent - a signed header and no body - and only to a push service's own address. A test
subscribes with an address at the fake push service (utils/fake_push.py) and reads what arrived."""

from __future__ import annotations

import pytest

from utils.assertions import assert_refused
from utils.local_time import at_local, local_day


@pytest.fixture
def ready(push, new_customer):
    if push.key(new_customer()).status_code == 404:
        pytest.skip("this copy of the shop has no VAPID key pair set")


@pytest.fixture
def own_barber(barbers):
    barber = barbers.create_fake_barber()
    return {**barber, "persona": barbers.sign_in_as_persona(barber)}


def waiting(bookings, barber, haircut, me, shop_tz, hhmm="15:00", days=9):
    return bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, days), hhmm), persona=me
    )


def test_a_signed_in_user_is_given_the_public_key_and_nobody_else(push, ready, new_customer):
    given = push.key(new_customer()).assert_ok(200).as_dict["key"]

    assert len(given) >= 80
    assert_refused(push.key(None), 401, "unauthorized")


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://evil.example/collect",
        "http://fcm.googleapis.com/fcm/send/x",
        "https://fcm.googleapis.com.evil.example/x",
        "https://evilfcm.googleapis.com/x",
        "http://169.254.169.254/latest/meta-data",
        "javascript:alert(1)",
    ],
)
def test_an_address_that_is_not_a_push_service_is_refused(push, ready, new_customer, endpoint):
    assert_refused(push.subscribe(endpoint, new_customer()), 422, "push_endpoint_refused")


def test_a_customer_is_told_when_the_barber_answers_with_no_body_and_a_signed_header(
    push, push_inbox, ready, bookings, own_barber, haircut, new_customer, shop_tz
):
    me, endpoint = new_customer(), push_inbox.new_endpoint()
    push.subscribe(endpoint, me).assert_ok(201)
    made = waiting(bookings, own_barber, haircut, me, shop_tz)

    bookings.approve(made["id"], persona=own_barber["persona"]).assert_ok(200)

    [post] = push_inbox.wait_for(endpoint)
    assert post["body_size"] == 0
    assert (
        post["headers"]["authorization"].startswith("vapid t=") and ", k=" in post["headers"]["authorization"]
    )


def test_a_no_tells_the_customer_too_and_the_same_answer_twice_tells_once(
    push, push_inbox, ready, bookings, own_barber, haircut, new_customer, shop_tz
):
    me, endpoint = new_customer(), push_inbox.new_endpoint()
    push.subscribe(endpoint, me).assert_ok(201)
    first = waiting(bookings, own_barber, haircut, me, shop_tz, "15:00")
    second = waiting(bookings, own_barber, haircut, me, shop_tz, "15:30")

    bookings.decline(first["id"], persona=own_barber["persona"]).assert_ok(200)
    bookings.approve(second["id"], persona=own_barber["persona"]).assert_ok(200)
    bookings.approve(second["id"], persona=own_barber["persona"]).assert_ok(200)

    assert len(push_inbox.wait_for(endpoint, count=2)) == 2
    assert len(push_inbox.stays_quiet(endpoint)) == 2


def test_the_barber_is_told_of_a_request_and_not_of_an_ordinary_booking(
    push, push_inbox, ready, bookings, own_barber, haircut, new_customer, shop_tz
):
    me, endpoint = new_customer(), push_inbox.new_endpoint()
    push.subscribe(endpoint, own_barber["persona"]).assert_ok(201)

    waiting(bookings, own_barber, haircut, me, shop_tz, "10:00")
    assert push_inbox.stays_quiet(endpoint) == []
    waiting(bookings, own_barber, haircut, me, shop_tz, "15:00")

    assert len(push_inbox.wait_for(endpoint)) == 1


def test_a_customer_is_not_told_about_someone_elses_booking(
    push, push_inbox, ready, bookings, own_barber, haircut, new_customer, shop_tz
):
    mine, other, endpoint = new_customer(), new_customer(), push_inbox.new_endpoint()
    push.subscribe(endpoint, other).assert_ok(201)
    made = waiting(bookings, own_barber, haircut, mine, shop_tz)

    bookings.approve(made["id"], persona=own_barber["persona"]).assert_ok(200)

    assert push_inbox.stays_quiet(endpoint) == []


def test_after_unsubscribing_nothing_is_sent(
    push, push_inbox, ready, bookings, own_barber, haircut, new_customer, shop_tz
):
    me, endpoint = new_customer(), push_inbox.new_endpoint()
    push.subscribe(endpoint, me).assert_ok(201)
    push.unsubscribe(endpoint, me).assert_ok(200)
    made = waiting(bookings, own_barber, haircut, me, shop_tz)

    bookings.approve(made["id"], persona=own_barber["persona"]).assert_ok(200)

    assert push_inbox.stays_quiet(endpoint) == []


def test_a_subscription_the_push_service_says_is_gone_is_forgotten(
    push, push_inbox, ready, bookings, own_barber, haircut, new_customer, shop_tz
):
    me, endpoint = new_customer(), push_inbox.new_endpoint()
    push.subscribe(endpoint, me).assert_ok(201)
    push_inbox.answer_with(endpoint, 410)
    first = waiting(bookings, own_barber, haircut, me, shop_tz, "15:00")
    second = waiting(bookings, own_barber, haircut, me, shop_tz, "15:30")

    bookings.approve(first["id"], persona=own_barber["persona"]).assert_ok(200)
    assert len(push_inbox.wait_for(endpoint)) == 1
    bookings.approve(second["id"], persona=own_barber["persona"]).assert_ok(200)

    assert len(push_inbox.stays_quiet(endpoint)) == 1


def test_a_push_service_that_is_down_never_breaks_the_answer(
    push, push_inbox, ready, bookings, own_barber, haircut, new_customer, shop_tz
):
    me, endpoint = new_customer(), push_inbox.new_endpoint()
    push.subscribe(endpoint, me).assert_ok(201)
    push_inbox.answer_with(endpoint, 503)
    made = waiting(bookings, own_barber, haircut, me, shop_tz)

    answered = bookings.approve(made["id"], persona=own_barber["persona"]).assert_ok(200).as_dict

    assert answered["approval"] == "approved"
