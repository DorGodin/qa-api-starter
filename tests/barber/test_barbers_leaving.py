"""A barber who leaves: inactive, never deleted - offered to no one, signed in
nowhere, their bookings kept for the owner to decide about one by one."""

from utils.assertions import assert_refused
from utils.local_time import at_local, local_day


def test_a_barber_who_left_is_offered_to_no_one_and_the_owner_still_sees_them(barbers, new_customer):
    leaving = barbers.create_fake_barber()

    left = barbers.set_active(leaving["id"], False).assert_ok(200).as_dict

    assert left["active"] is False
    seen_by_customer = barbers.find(persona=new_customer()).assert_ok(200).as_dict["content"]
    assert leaving["id"] not in [b["id"] for b in seen_by_customer]
    seen_by_owner = {b["id"]: b for b in barbers.find(persona="owner").assert_ok(200).as_dict["content"]}
    assert seen_by_owner[leaving["id"]]["active"] is False


def test_nobody_books_a_barber_who_left(barbers, bookings, haircut, new_customer, shop_tz):
    leaving = barbers.create_fake_barber()
    barbers.set_active(leaving["id"], False).assert_ok(200)
    day = local_day(shop_tz, 5)
    start = at_local(shop_tz, day, "11:00")
    me = new_customer()

    assert_refused(
        barbers.availability(leaving["id"], day, haircut["id"], persona=me), 422, "barber_inactive"
    )
    assert_refused(bookings.book(leaving["id"], haircut["id"], start, persona=me), 422, "barber_inactive")
    assert_refused(bookings.book_guest(leaving["id"], haircut["id"], start), 422, "barber_inactive")


def test_their_bookings_stay_say_who_and_wait_for_the_owner(
    barbers, bookings, haircut, new_customer, shop_tz
):
    leaving = barbers.create_fake_barber()
    me = new_customer()
    day = local_day(shop_tz, 5)
    booking = bookings.create_booking(
        leaving["id"], haircut["id"], at_local(shop_tz, day, "11:00"), persona=me
    )

    barbers.set_active(leaving["id"], False).assert_ok(200)

    kept = bookings.get_by_id(booking["id"], persona=me).assert_ok(200).as_dict
    assert kept["status"] == "confirmed", "leaving does not cancel anyone's booking by itself"
    assert kept["barber_name"] == leaving["display_name"], "the customer still sees who the booking is with"
    assert_refused(
        bookings.move(booking["id"], at_local(shop_tz, day, "15:00"), persona="owner"), 422, "barber_inactive"
    )
    assert bookings.cancel(booking["id"], persona="owner").assert_ok(200).as_dict["status"] == "cancelled"


def test_a_barber_who_left_is_signed_out_and_cannot_sign_in(barbers, api):
    leaving = barbers.create_fake_barber()
    persona = barbers.sign_in_as_persona(leaving)
    assert api.request("GET", "/me", persona=persona).status_code == 200

    barbers.set_active(leaving["id"], False).assert_ok(200)

    assert api.request("GET", "/me", persona=persona).status_code == 401
    refused = api.request(
        "POST",
        "/auth/token",
        persona=None,
        json={"username": leaving["username"], "password": leaving["password"]},
    )
    assert_refused(refused, 403, "account_inactive")


def test_a_barber_who_comes_back_is_bookable_again(barbers, bookings, haircut, new_customer, shop_tz):
    leaving = barbers.create_fake_barber()
    barbers.set_active(leaving["id"], False).assert_ok(200)

    assert barbers.set_active(leaving["id"], True).assert_ok(200).as_dict["active"] is True

    bookings.create_booking(
        leaving["id"],
        haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 5), "12:00"),
        persona=new_customer(),
    )


def test_only_the_owner_decides_who_has_left(barbers, new_customer):
    leaving = barbers.create_fake_barber()

    assert_refused(barbers.set_active(leaving["id"], False, persona=new_customer()), 403, "forbidden")
    assert_refused(
        barbers.set_active(leaving["id"], False, persona=barbers.sign_in_as_persona(leaving)),
        403,
        "forbidden",
    )
