"""A customer as the staff know them, through the API: what they did, the note the staff keep, the
owner alone seeing the phone - and a booking marked not come to only once its time has come.

A booking whose time has passed cannot be made from outside, so marking one, and its weight toward
waiting for the barber, are the product's own tests (tests/test_customer_card.py)."""

from __future__ import annotations

from utils.assertions import assert_refused
from utils.local_time import at_local, local_day


def card(api, customer_id, persona):
    return api.request("GET", f"/customers/{customer_id}/card", persona=persona)


def note(api, customer_id, text, persona="owner"):
    return api.request("PUT", f"/customers/{customer_id}/note", persona=persona, json={"text": text})


def test_the_card_counts_what_is_ahead_and_only_what_the_customer_cancelled(
    api, customers, sms_inbox, bookings, barbers, haircut, shop_tz
):
    who = customers.sign_in_by_code(sms_inbox, full_name="רותם בדיקה")
    barber = barbers.create_fake_barber()
    ahead = bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 5), "10:00"), persona=who["persona"]
    )
    gone = bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 6), "10:00"), persona=who["persona"]
    )
    bookings.cancel(gone["id"], persona=who["persona"]).assert_ok(200)
    shop_gone = bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 7), "10:00"), persona=who["persona"]
    )
    bookings.cancel(shop_gone["id"], persona="owner").assert_ok(200)

    seen = card(api, ahead["customer_id"], "owner").assert_ok(200).as_dict

    assert (seen["name"], seen["phone"]) == ("רותם בדיקה", who["phone"])
    assert (seen["visits"], seen["upcoming"], seen["cancellations"], seen["no_shows"]) == (0, 1, 1, 0)
    assert seen["last_visit"] is None and seen["note"] == ""


def test_the_barber_sees_their_customers_without_the_phone_and_nobody_elses(
    api, customers, sms_inbox, bookings, barbers, haircut, shop_tz
):
    who = customers.sign_in_by_code(sms_inbox)
    mine, other = barbers.create_fake_barber(), barbers.create_fake_barber()
    made = bookings.create_booking(
        mine["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 5), "11:00"), persona=who["persona"]
    )

    assert (
        card(api, made["customer_id"], barbers.sign_in_as_persona(mine)).assert_ok(200).as_dict["phone"]
        is None
    )
    assert_refused(card(api, made["customer_id"], barbers.sign_in_as_persona(other)), 404, "not_found")
    assert_refused(card(api, made["customer_id"], who["persona"]), 403, "forbidden")


def test_the_note_is_shared_by_the_staff_and_gone_when_emptied(
    api, customers, sms_inbox, bookings, barbers, haircut, shop_tz
):
    who = customers.sign_in_by_code(sms_inbox)
    barber = barbers.create_fake_barber()
    made = bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 5), "12:00"), persona=who["persona"]
    )

    note(api, made["customer_id"], "מספר 2 בצדדים").assert_ok(200)

    as_barber = barbers.sign_in_as_persona(barber)
    assert card(api, made["customer_id"], as_barber).as_dict["note"] == "מספר 2 בצדדים"
    assert note(api, made["customer_id"], "", persona=as_barber).assert_ok(200).as_dict["note"] == ""
    assert note(api, made["customer_id"], "x" * 1001).status_code == 422
    assert_refused(note(api, made["customer_id"], "x", persona=who["persona"]), 403, "forbidden")


def test_a_booking_is_not_marked_not_come_to_before_its_time(
    api, bookings, barbers, haircut, new_customer, shop_tz
):
    me, barber = new_customer(), barbers.create_fake_barber()
    made = bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 5), "13:00"), persona=me
    )

    early = api.request("POST", f"/bookings/{made['id']}/no-show", persona="owner")

    assert_refused(early, 409, "not_started")
    assert_refused(api.request("POST", f"/bookings/{made['id']}/no-show", persona=me), 403, "forbidden")
    assert bookings.get_by_id(made["id"], persona=me).as_dict["no_show"] is False


def test_a_declined_request_is_not_a_booking_ahead_on_the_card(
    api, customers, sms_inbox, bookings, barbers, services, shop_tz
):
    who = customers.sign_in_by_code(sms_inbox)
    barber = barbers.create_fake_barber()
    asks = services.create_fake_service(requires_approval=True)
    made = bookings.create_booking(
        barber["id"], asks["id"], at_local(shop_tz, local_day(shop_tz, 5), "14:00"), persona=who["persona"]
    )
    assert card(api, made["customer_id"], "owner").as_dict["upcoming"] == 1

    bookings.decline(made["id"], persona="owner").assert_ok(200)

    assert card(api, made["customer_id"], "owner").as_dict["upcoming"] == 0
