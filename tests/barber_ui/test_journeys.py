"""Journeys: what a shop and its customers do, start to finish, through the page
alone.

Every other page test builds its barbers, services and bookings through the API,
to be fast and to test one thing. Nothing there proves the pieces join up: that
a barber the owner adds on the screen can be booked by a customer who signed up
on the screen, at the hours the owner typed, for the price the owner typed. Here
nothing is prepared. The API is used only at the end, to check that what the
screens showed is what was stored.

Each person is a separate browser - their own storage and their own sign-in - as
four people on four phones would be. Under --device, all of them use that phone.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import time
import urllib.request
from datetime import datetime, timedelta

import pytest
from playwright.sync_api import expect

from obj.barber.booking_page import BookingPage, OwnerScreen, a_device, greeting
from obj.barber.customers import Customers
from utils.local_time import at_local, local_day, parse_instant

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@pytest.fixture
def person(browser, browser_context_args, env_config):
    contexts = []

    def _open(screen: type[BookingPage] = BookingPage) -> BookingPage:
        context = a_device(browser, **browser_context_args)
        contexts.append(context)
        return screen(context.new_page(), env_config["url"])

    yield _open
    for context in contexts:
        context.close()


@pytest.fixture
def run_id() -> str:
    return secrets.token_hex(3)


def new_account(run_id: str, who: str) -> dict:
    return {"name": f"QA {who} {run_id}", "phone": Customers.new_phone()}


def new_barber(run_id: str, who: str) -> dict:
    # Staff still sign in with a username and a password, until they have phones.
    return {
        "name": f"QA {who} {run_id}",
        "username": f"qa-journey-{run_id}-{who}",
        "password": f"journey-{run_id}-{who}-pw",
    }


@pytest.fixture
def signed_up(sms_inbox):
    """A person opening their account on the screen: name, phone, the code from
    the SMS - the first sign-in opens it."""

    def _sign_up(screen: BookingPage, account: dict, navigate: bool = True) -> BookingPage:
        screen.sign_in_by_code(account["name"], account["phone"], sms_inbox, navigate=navigate)
        expect(screen.by("app")).to_be_visible()
        screen.settled()
        return screen

    return _sign_up


def quarter_hours(first: str, last: str) -> list[str]:
    start, end = (datetime.strptime(hhmm, "%H:%M") for hhmm in (first, last))
    return [
        (start + timedelta(minutes=15 * i)).strftime("%H:%M")
        for i in range(int((end - start).total_seconds() // 900) + 1)
    ]


def open_a_barber(owner: OwnerScreen, run_id: str, weekday: str, opening: str, closing: str) -> dict:
    # A Hebrew name, as the shop's barbers have. The list is sorted by name, and
    # a Latin "QA ..." sorts first - which hid a new barber not being selected,
    # because the first barber happened to be the new one.
    barber = {**new_barber(run_id, "barber"), "name": f"תומר {run_id}"}
    owner.add_barber(barber["name"], barber["username"], barber["password"])
    expect(owner.message()).to_have_attribute("data-kind", "ok")
    expect(owner.by("barber").locator("option:checked")).to_have_text(barber["name"])
    barber["id"] = owner.by("barber").input_value()
    owner.set_day(weekday, opening, closing).save_hours()
    expect(owner.message()).to_have_attribute("data-kind", "ok")
    return barber


def add_a_service(owner: OwnerScreen, name: str, minutes: int, price: str) -> str:
    owner.add_service(name, minutes, price)
    expect(owner.message()).to_have_attribute("data-kind", "ok")
    return owner.by("service-row").filter(has_text=name).get_attribute("data-id")


def test_a_shop_opened_on_the_screen_is_booked_cancelled_and_booked_again(
    person, run_id, credentials, customers, bookings, shop_tz, signed_up
):
    day = local_day(shop_tz, 7)
    weekday = WEEKDAYS[day.weekday()]

    owner = person(OwnerScreen).sign_in(*credentials("owner"))
    barber = open_a_barber(owner, run_id, weekday, "09:00", "13:00")
    service = f"QA journey cut {run_id}"
    service_id = add_a_service(owner, service, 45, "72.50")

    first_account = new_account(run_id, "first")
    first = signed_up(person(), first_account)
    first.choose_by_name(barber["name"], service, day)
    assert first.times() == quarter_hours(
        "09:00", "12:15"
    ), "a 45 minute service, inside the hours the owner typed"
    first.pick("12:15").book()
    assert first.last_popup["kind"] == "ok", "the last time offered ends exactly at closing, and is bookable"
    assert "72.50 ₪" in first.last_popup["text"]
    expect(first.row_at("12:15")).to_have_attribute("data-status", "confirmed")

    diary = person().sign_in(barber["username"], barber["password"])
    expect(diary.row_at("12:15")).to_be_visible()
    expect(diary.row_at("12:15").get_by_test_id("cancel")).to_have_count(0)

    owner.select_barber(barber["id"])
    expect(owner.row_at("12:15")).to_have_attribute("data-status", "confirmed")

    first.cancel("12:15")
    expect(first.row_at("12:15")).to_have_attribute("data-status", "cancelled")

    second_account = new_account(run_id, "second")
    second = signed_up(person(), second_account)
    second.choose_by_name(barber["name"], service, day)
    assert "12:15" in second.times(), "the cancelled time is offered again"
    second.pick("12:15").book()
    assert second.last_popup["kind"] == "ok"

    owner.select_barber(barber["id"])
    expect(owner.page.locator('[data-testid="booking-row"][data-status="confirmed"]')).to_have_count(1)
    expect(owner.page.locator('[data-testid="booking-row"][data-status="cancelled"]')).to_have_count(1)

    # Each customer's own view, through the sign-in their screen holds.
    for screen, account in ((first, first_account), (second, second_account)):
        customers.client.register_persona_headers(
            f"journey-{account['phone']}", {"Authorization": f"Bearer {screen.session_token()}"}
        )
    stored = bookings.listing(persona="owner", barber_id=barber["id"])["content"]
    assert sorted(b["status"] for b in stored) == ["cancelled", "confirmed"]
    assert {parse_instant(b["start"]) for b in stored} == {at_local(shop_tz, day, "12:15")}
    assert all(
        b["service_id"] == service_id and b["price_minor"] == 7250 for b in stored
    ), "the price the owner typed"
    assert [
        b["status"] for b in bookings.listing(persona=f"journey-{first_account['phone']}")["content"]
    ] == ["cancelled"]
    assert [
        b["status"] for b in bookings.listing(persona=f"journey-{second_account['phone']}")["content"]
    ] == ["confirmed"]


def test_a_day_off_given_on_the_screen_closes_the_day_and_taking_it_back_reopens_it(
    person, run_id, credentials, shop_tz, signed_up
):
    day = local_day(shop_tz, 9)
    weekday = WEEKDAYS[day.weekday()]

    owner = person(OwnerScreen).sign_in(*credentials("owner"))
    barber = open_a_barber(owner, run_id, weekday, "10:00", "12:00")
    service = f"QA journey trim {run_id}"
    add_a_service(owner, service, 30, "50")

    customer = signed_up(person(), new_account(run_id, "customer"))
    customer.choose_by_name(barber["name"], service, day)
    assert customer.times() == quarter_hours("10:00", "11:30")

    owner.add_day_off(day)
    assert owner.days_off() == [day.isoformat()]
    customer.choose_by_name(barber["name"], service, day)
    expect(customer.by("no-slots")).to_be_visible()
    expect(customer.by("slot")).to_have_count(0)

    owner.remove_day_off(day)
    assert owner.days_off() == []
    customer.choose_by_name(barber["name"], service, day)
    assert customer.times() == quarter_hours("10:00", "11:30"), "the day is back, with its hours"


def values_left_in_the_page(screen: BookingPage) -> list[str]:
    """Everything a person could read or send from the page without signing in:
    the values in every field, and every word of text - hidden ones included."""
    return screen.page.evaluate(
        """() => [...document.querySelectorAll("input, select")].map((el) => el.value)
            .concat([document.body.textContent])"""
    )


def test_on_a_shared_device_the_next_person_finds_nothing_of_the_one_before(
    person, run_id, credentials, shop_tz, signed_up
):
    day = local_day(shop_tz, 7)
    owner = person(OwnerScreen).sign_in(*credentials("owner"))
    barber = open_a_barber(owner, run_id, WEEKDAYS[day.weekday()], "10:00", "12:00")
    service = f"QA journey cut {run_id}"
    add_a_service(owner, service, 30, "80")

    device = person()
    first = new_account(run_id, "first")
    signed_up(device, first)
    device.choose_by_name(barber["name"], service, day).pick("10:00").book()
    expect(device.row_at("10:00")).to_have_attribute("data-status", "confirmed")

    device.by("logout").click()
    expect(device.by("code-request-form")).to_be_visible()
    left = values_left_in_the_page(device)
    for value in (first["name"], first["phone"]):
        assert not any(value in item for item in left), f"{value!r} is still in the page after signing out"
    expect(device.by("booking-row")).to_have_count(0)

    second = new_account(run_id, "second")
    signed_up(device, second, navigate=False)
    expect(device.by("display-name")).to_have_text(greeting(second["name"]))
    expect(device.by("no-bookings")).to_be_visible()
    expect(device.by("booking-row")).to_have_count(0)
    device.choose_by_name(barber["name"], service, day).pick("11:00").book()

    device.reload()
    expect(device.by("app")).to_be_visible()
    expect(device.by("display-name")).to_have_text(greeting(second["name"]))
    expect(device.row_at("11:00")).to_have_attribute("data-status", "confirmed")

    device.by("logout").click()
    device.reload()
    expect(device.by("code-request-form")).to_be_visible()
    expect(device.by("app")).to_be_hidden()


def test_what_the_owner_changes_reaches_each_customer_the_way_it_should(
    person, run_id, credentials, bookings, shop_tz, signed_up
):
    day = local_day(shop_tz, 7)
    owner = person(OwnerScreen).sign_in(*credentials("owner"))
    barber = open_a_barber(owner, run_id, WEEKDAYS[day.weekday()], "10:00", "14:00")
    cut, trim = f"QA journey cut {run_id}", f"QA journey trim {run_id}"
    cut_id = add_a_service(owner, cut, 30, "80")
    add_a_service(owner, trim, 30, "50")

    first = signed_up(person(), new_account(run_id, "first"))
    first.choose_by_name(barber["name"], cut, day).pick("10:00").book()
    assert "80.00 ₪" in first.last_popup["text"]

    owner.save_service(cut_id, price="95")
    expect(owner.message()).to_have_attribute("data-kind", "ok")
    first.reload()
    assert "80.00 ₪" in first.text(first.row_at("10:00")), "a booking keeps the price it was made at"

    second = signed_up(person(), new_account(run_id, "second"))
    assert "95.00 ₪" in second.text(second.by("service").locator("option", has_text=cut))
    second.choose_by_name(barber["name"], cut, day).pick("11:00").book()
    assert "95.00 ₪" in second.last_popup["text"], "a new booking takes the new price"

    owner.save_service(cut_id, offered=False)
    expect(owner.message()).to_have_attribute("data-kind", "ok")
    third = signed_up(person(), new_account(run_id, "third"))
    expect(third.by("service").locator("option", has_text=cut)).to_have_count(0)
    first.reload()
    expect(first.row_at("10:00")).to_have_attribute("data-status", "confirmed")

    owner.select_barber(barber["id"])
    owner.cancel("10:00")
    first.reload()
    expect(first.row_at("10:00")).to_have_attribute("data-status", "cancelled")
    third.choose_by_name(barber["name"], trim, day)
    assert "10:00" in third.times(), "the time the owner freed is offered again"

    stored = {
        (parse_instant(b["start"]), b["status"], b["price_minor"])
        for b in bookings.listing(persona="owner", barber_id=barber["id"])["content"]
    }
    assert stored == {
        (at_local(shop_tz, day, "10:00"), "cancelled", 8000),
        (at_local(shop_tz, day, "11:00"), "confirmed", 9500),
    }


def healthy(env_config, seconds: int = 90) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(env_config["url"] + env_config["health_path"], timeout=2) as resp:
                if resp.status == 200:
                    return
        except OSError:
            time.sleep(1)
    raise RuntimeError(f"{env_config['url']} did not come back within {seconds}s of the redeploy")


def test_accounts_bookings_and_a_sign_in_survive_a_redeploy(
    person, run_id, credentials, env_config, shop_tz, signed_up, sms_inbox
):
    command = os.environ.get("REDEPLOY_COMMAND")
    if not command and env_config.get("redeploy"):
        pytest.fail(f"{env_config['url']} must be redeployed by this test, and REDEPLOY_COMMAND is not set")
    if not command:
        pytest.skip("this environment cannot be redeployed from a test; barber-image in CI can")
    day = local_day(shop_tz, 7)
    owner = person(OwnerScreen).sign_in(*credentials("owner"))
    barber = open_a_barber(owner, run_id, WEEKDAYS[day.weekday()], "10:00", "12:00")
    service = f"QA journey cut {run_id}"
    add_a_service(owner, service, 30, "80")
    account = new_account(run_id, "customer")
    customer = signed_up(person(), account)
    customer.choose_by_name(barber["name"], service, day).pick("10:00").book()

    subprocess.run(command, shell=True, check=True, timeout=300)
    healthy(env_config)

    customer.reload()
    expect(customer.by("app")).to_be_visible()
    expect(customer.row_at("10:00")).to_have_attribute("data-status", "confirmed")
    again = person().sign_in_by_code(account["name"], account["phone"], sms_inbox)
    expect(again.row_at("10:00")).to_be_visible()
    owner.reload()
    owner.select_barber(barber["id"])
    expect(owner.row_at("10:00")).to_be_visible()
