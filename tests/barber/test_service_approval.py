"""A service whose every booking waits for the barber - any day, any hour, and no yes by silence."""

from __future__ import annotations

import pytest

from utils.assertions import assert_refused
from utils.local_time import at_local, local_day


@pytest.fixture
def emergency(services):
    return services.create_fake_service(requires_approval=True)


@pytest.fixture
def own_barber(barbers):
    barber = barbers.create_fake_barber()
    return {**barber, "persona": barbers.sign_in_as_persona(barber)}


def test_a_service_says_whether_it_needs_the_barber(services, emergency):
    plain = services.create_fake_service()

    assert (emergency["requires_approval"], plain["requires_approval"]) == (True, False)


def test_only_the_owner_turns_it_on_or_off(services, new_customer):
    service = services.create_fake_service()

    assert_refused(
        services.update_by_id(service["id"], {"requires_approval": True}, persona=new_customer()),
        403,
        "forbidden",
    )
    on = (
        services.update_by_id(service["id"], {"requires_approval": True}, persona="owner")
        .assert_ok(200)
        .as_dict
    )
    off = (
        services.update_by_id(service["id"], {"requires_approval": False}, persona="owner")
        .assert_ok(200)
        .as_dict
    )
    assert (on["requires_approval"], off["requires_approval"]) == (True, False)


@pytest.mark.parametrize("hhmm", ["09:00", "10:00", "16:00", "20:00"])
def test_a_booking_of_it_waits_at_every_hour_with_no_time_limit(
    bookings, own_barber, emergency, new_customer, shop_tz, hhmm
):
    made = bookings.create_booking(
        own_barber["id"],
        emergency["id"],
        at_local(shop_tz, local_day(shop_tz, 9), hhmm),
        persona=new_customer(),
    )

    assert (made["status"], made["approval"], made["decide_by"]) == ("confirmed", "pending", None)


def test_the_same_hour_with_an_ordinary_service_does_not_wait(
    bookings, own_barber, haircut, new_customer, shop_tz
):
    made = bookings.create_booking(
        own_barber["id"],
        haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 9), "10:00"),
        persona=new_customer(),
    )

    assert made["approval"] is None


def test_the_barber_answers_it_like_any_request(bookings, own_barber, emergency, new_customer, shop_tz):
    made = bookings.create_booking(
        own_barber["id"],
        emergency["id"],
        at_local(shop_tz, local_day(shop_tz, 9), "10:00"),
        persona=new_customer(),
    )

    approved = bookings.approve(made["id"], persona=own_barber["persona"]).assert_ok(200).as_dict

    assert approved["approval"] == "approved"


def test_moving_it_waits_again_and_the_owner_moving_it_decides(
    bookings, own_barber, emergency, new_customer, shop_tz
):
    me, day = new_customer(), local_day(shop_tz, 9)
    made = bookings.create_booking(
        own_barber["id"], emergency["id"], at_local(shop_tz, day, "10:00"), persona=me
    )
    bookings.approve(made["id"], persona="owner").assert_ok(200)

    by_customer = (
        bookings.move(made["id"], at_local(shop_tz, day, "11:00"), persona=me).assert_ok(200).as_dict
    )
    by_owner = (
        bookings.move(made["id"], at_local(shop_tz, day, "12:00"), persona="owner").assert_ok(200).as_dict
    )

    assert (by_customer["approval"], by_customer["decide_by"]) == ("pending", None)
    assert by_owner["approval"] is None


def test_the_owner_booking_it_for_a_guest_needs_no_yes(bookings, own_barber, emergency, shop_tz):
    made = (
        bookings.book_guest(
            own_barber["id"], emergency["id"], at_local(shop_tz, local_day(shop_tz, 9), "10:00")
        )
        .assert_ok(201)
        .as_dict
    )

    assert made["approval"] is None
