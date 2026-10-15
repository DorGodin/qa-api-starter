"""Notifications to the shop's app on a phone, through Firebase - here the fake Firebase in utils/fake_push.py.
A phone is told the fixed words of its person's role and nothing about the booking."""

from __future__ import annotations

import pytest

from utils.local_time import at_local, local_day

STAFF = ("עדכון ביומן", "תור חדש, בקשה או ביטול - פתחו את היומן.")
CUSTOMER = ("עדכון על התור שלך", "פתחו את האפליקציה לפרטים.")


@pytest.fixture
def phones(push, push_inbox, new_customer):
    probe = push.register_device(push_inbox.new_device_token(), new_customer())
    if probe.status_code == 404:
        pytest.skip("this copy of the shop sends no phone notifications (no FCM_CREDENTIALS)")
    return push_inbox


@pytest.fixture
def own_barber(barbers):
    barber = barbers.create_fake_barber()
    return {**barber, "persona": barbers.sign_in_as_persona(barber)}


def book(bookings, barber, haircut, me, shop_tz, hhmm="10:00", days=9):
    return bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, days), hhmm), persona=me
    )


def words(message: dict) -> tuple[str, str]:
    note = message["message"]["notification"]
    return note["title"], note["body"]


def test_the_barbers_phone_is_told_of_a_new_booking_in_the_staffs_words_and_nothing_of_it(
    push, phones, bookings, own_barber, haircut, customers, sms_inbox, shop_tz
):
    token = phones.new_device_token()
    push.register_device(token, own_barber["persona"], platform="android").assert_ok(201)
    who = customers.sign_in_by_code(sms_inbox, full_name="רותם בדיקה")

    book(bookings, own_barber, haircut, who["persona"], shop_tz, "10:00")

    told = phones.wait_for_phone(token)
    assert [words(m) for m in told] == [STAFF]
    sent = str(told[0]["message"])
    assert "רותם" not in sent and "10:00" not in sent, "nothing about the booking travels through Firebase"
    assert told[0]["authorization"].startswith("Bearer ")


def test_the_customers_phone_is_told_of_the_barbers_answer_in_the_customers_words(
    push, phones, bookings, own_barber, haircut, new_customer, shop_tz
):
    me, token = new_customer(), phones.new_device_token()
    push.register_device(token, me).assert_ok(201)
    made = book(bookings, own_barber, haircut, me, shop_tz, "15:00")
    assert made["approval"] == "pending"

    bookings.approve(made["id"], persona=own_barber["persona"]).assert_ok(200)

    assert [words(m) for m in phones.wait_for_phone(token)] == [CUSTOMER]


def test_a_phone_firebase_says_is_gone_is_told_nothing_more(
    push, phones, bookings, own_barber, haircut, new_customer, shop_tz
):
    token = phones.new_device_token()
    push.register_device(token, own_barber["persona"]).assert_ok(201)
    phones.phone_answers_with(token, 404)

    book(bookings, own_barber, haircut, new_customer(), shop_tz, "10:00")
    phones.wait_for_phone(token)
    book(bookings, own_barber, haircut, new_customer(), shop_tz, "11:00")

    assert len(phones.phone_stays_quiet(token)) == 1


def test_signing_out_on_the_phone_ends_its_notifications_and_only_its_person_can(
    push, phones, bookings, own_barber, haircut, new_customer, shop_tz
):
    token, stranger = phones.new_device_token(), new_customer()
    push.register_device(token, own_barber["persona"]).assert_ok(201)

    push.remove_device(token, stranger).assert_ok(200)
    book(bookings, own_barber, haircut, new_customer(), shop_tz, "10:00")
    assert len(phones.wait_for_phone(token)) == 1, "someone else cannot turn it off"
    push.remove_device(token, own_barber["persona"]).assert_ok(200)
    book(bookings, own_barber, haircut, new_customer(), shop_tz, "11:00")

    assert len(phones.phone_stays_quiet(token)) == 1


def test_a_device_is_registered_only_with_a_token_and_a_platform_it_knows(push, phones, new_customer, api):
    me = new_customer()

    assert push.register_device("short", me).status_code == 422
    assert push.register_device("a" * 30 + "/../x", me).status_code == 422
    assert push.register_device(phones.new_device_token(), me, platform="windows").status_code == 422
    assert push.register_device(phones.new_device_token(), None).status_code == 401
    assert api.request("POST", "/push/devices", persona=me, json={}).status_code == 422
