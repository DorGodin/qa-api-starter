"""A barber signs in as a customer does - a mobile, and the code sent to it - and whose phone it
is decides what they are. The owner gives a barber the phone, changes it and takes it away.

The owner's own phone is a setting of the shop; signing in with it is tested once, on the page
(tests/barber_ui/test_staff_sign_in.py) - a phone is sent only so many codes an hour."""

from __future__ import annotations

import pytest

from obj.barber.customers import Customers
from utils.assertions import assert_refused


def me(api, persona: str) -> dict:
    return api.request("GET", "/me", persona=persona).assert_ok(200).as_dict


def test_a_barber_with_a_phone_signs_in_by_code_whatever_name_is_typed(barbers, customers, sms_inbox, api):
    phone = Customers.new_phone()
    barber = barbers.create_fake_barber(phone=phone)

    signed = customers.sign_in_by_code(sms_inbox, full_name="כל שם", phone=phone)

    who = me(api, signed["persona"])
    assert (who["id"], who["role"], who["display_name"]) == (barber["id"], "barber", barber["display_name"])


def test_a_barbers_name_typed_with_another_phone_is_only_a_customer(barbers, customers, sms_inbox, api):
    barber = barbers.create_fake_barber(phone=Customers.new_phone())

    signed = customers.sign_in_by_code(sms_inbox, full_name=barber["display_name"])

    assert me(api, signed["persona"])["role"] == "customer"
    assert_refused(barbers.set_phone(barber["id"], "", persona=signed["persona"]), 403, "forbidden")


def test_a_barbers_phone_is_the_owners_to_see_and_no_customers(barbers, new_customer):
    phone = Customers.new_phone()
    barber = barbers.create_fake_barber(phone=phone)

    def listed(persona):
        return next(
            b for b in barbers.find(persona=persona).assert_ok(200).content if b["id"] == barber["id"]
        )

    assert listed("owner")["phone"] == phone
    assert "phone" not in listed(new_customer())


def test_the_phone_is_stored_the_way_every_phone_is(barbers):
    barber = barbers.create_fake_barber()
    digits = Customers.new_phone()
    typed = f"+972 {digits[1:3]}-{digits[3:6]} {digits[6:]}"

    saved = barbers.set_phone(barber["id"], typed).assert_ok(200).as_dict

    assert saved["phone"] == digits


@pytest.mark.parametrize("phone", ["123", "03-5551234", "05012345678", "barber"])
def test_a_barbers_phone_must_be_a_mobile(barbers, phone):
    barber = barbers.create_fake_barber()

    assert_refused(barbers.set_phone(barber["id"], phone), 422, "bad_phone")
    payload = {**barbers.build_barber_payload(), "phone": phone}
    assert_refused(barbers.create(payload, persona="owner"), 422, "bad_phone")


def test_a_phone_is_one_persons_a_customers_or_a_barbers(barbers, customers, sms_inbox):
    customer_phone = customers.sign_in_by_code(sms_inbox)["phone"]
    barber_phone = Customers.new_phone()
    first = barbers.create_fake_barber(phone=barber_phone)
    second = barbers.create_fake_barber()

    for taken in (customer_phone, barber_phone):
        assert_refused(barbers.set_phone(second["id"], taken), 409, "phone_taken")
    payload = {**barbers.build_barber_payload(), "phone": barber_phone}
    assert_refused(barbers.create(payload, persona="owner"), 409, "phone_taken")
    barbers.set_phone(first["id"], barber_phone).assert_ok(200)


def test_a_phone_taken_away_no_longer_opens_the_diary(barbers, customers, sms_inbox, api):
    phone = Customers.new_phone()
    barber = barbers.create_fake_barber(phone=phone)

    cleared = barbers.set_phone(barber["id"], "").assert_ok(200).as_dict

    assert cleared["phone"] is None and cleared["active"] is True
    signed = customers.sign_in_by_code(sms_inbox, phone=phone)
    assert me(api, signed["persona"])["role"] == "customer", "the number is anybody's again"


def test_a_barber_who_left_keeps_the_phone_and_it_signs_in_nowhere(barbers, customers, sms_inbox):
    phone = Customers.new_phone()
    barber = barbers.create_fake_barber(phone=phone)

    left = barbers.set_active(barber["id"], False).assert_ok(200).as_dict

    assert (left["active"], left["phone"]) == (False, phone)
    seen = sms_inbox.last_id(phone)
    customers.request_code(phone, "כל שם").assert_ok(202)
    assert_refused(
        customers.verify_code(phone, sms_inbox.code_for(phone, after=seen)), 403, "account_inactive"
    )


def test_a_change_that_names_nothing_is_refused(barbers):
    barber = barbers.create_fake_barber()

    refused = barbers.update_by_id(barber["id"], {}, persona="owner")

    assert refused.status_code == 422
