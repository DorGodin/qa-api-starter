"""One way in. The owner and a barber sign in on the same form a customer does - a name, a mobile,
the code sent to it - and whose phone it is decides what opens. Nothing on the page takes a
password, and a name alone opens nothing."""

import secrets

import pytest
from playwright.sync_api import expect

from obj.barber.booking_page import OwnerScreen
from obj.barber.customers import Customers


@pytest.fixture
def name():
    return f"ספר {secrets.token_hex(3)}"


def test_the_owners_phone_opens_the_owners_screen_from_the_customers_form(shop, env_config, sms_inbox):
    """The one test that asks for a code to the owner's phone: a phone is sent only so many an hour."""
    shop.sign_in_by_code("מישהו אחר", env_config["owner_phone"], sms_inbox)

    expect(shop.by("owner")).to_be_visible()
    expect(shop.by("products-admin-panel")).to_be_visible()
    expect(shop.by("tabbar")).to_be_hidden()
    assert "מישהו אחר" not in shop.text(shop.by("display-name")), "the name typed does not rename the owner"


def test_the_owners_name_with_a_strangers_phone_opens_a_customers_screen(shop, sms_inbox, api, credentials):
    owner_name = api.request("GET", "/me", persona="owner").assert_ok(200).as_dict["display_name"]

    shop.sign_in_by_code(owner_name, Customers.new_phone(), sms_inbox)

    expect(shop.by("app")).to_have_attribute("data-role", "customer")
    expect(shop.by("owner")).to_be_hidden()


def test_nothing_on_the_sign_in_screen_takes_a_password_or_a_username(shop):
    shop.open()

    expect(shop.page.locator('input[type="password"]')).to_have_count(0)
    expect(shop.page.locator('input[autocomplete="username"]')).to_have_count(0)
    expect(shop.page.get_by_text("סיסמה")).to_have_count(0)
    assert [shop.text(label) for label in shop.by("auth").locator("label:visible").all()] == [
        "שם מלא",
        "מספר טלפון",
    ]


def test_a_barber_the_owner_adds_with_a_phone_signs_in_by_code_and_sees_only_a_diary(
    owner_screen, barbers, shop, page, env_config, browser, browser_context_args, sms_inbox, name, person
):
    phone = Customers.new_phone()

    owner = owner_screen()
    owner.add_barber(name, phone)

    expect(owner.message()).to_have_attribute("data-kind", "ok")
    created = next(
        b for b in barbers.find(persona="owner").assert_ok(200).content if b["display_name"] == name
    )
    assert created["phone"] == phone
    expect(owner.by("barber-phone")).to_have_value(phone)
    diary = person()
    diary.sign_in_by_code("כל שם", phone, sms_inbox)
    expect(diary.by("app")).to_have_attribute("data-role", "barber")
    expect(diary.by("book-panel")).to_be_hidden()
    expect(diary.by("owner")).to_be_hidden()
    assert name in diary.text(diary.by("display-name"))


def test_a_barber_with_no_phone_is_said_to_have_no_way_in_until_the_owner_gives_one(
    owner_screen, barbers, sms_inbox, person
):
    barber = barbers.create_fake_barber()
    phone = Customers.new_phone()
    owner = owner_screen().select_barber(barber["id"])
    expect(owner.by("barber-phone")).to_have_value("")
    assert "לא יכול להיכנס" in owner.text(owner.by("barber-phone-note"))

    owner.save_barber_phone(f"{phone[:3]}-{phone[3:]}")

    expect(owner.message()).to_have_attribute("data-kind", "ok")
    expect(owner.by("barber-phone")).to_have_value(phone)
    assert "לא יכול" not in owner.text(owner.by("barber-phone-note"))
    assert barbers.find(persona="owner").assert_ok(200).content
    diary = person()
    diary.sign_in_by_code("כל שם", phone, sms_inbox)
    expect(diary.by("app")).to_have_attribute("data-role", "barber")


def test_taking_the_phone_away_is_said_and_stored(owner_screen, barbers):
    barber = barbers.create_fake_barber(phone=Customers.new_phone())
    owner = owner_screen().select_barber(barber["id"])

    owner.save_barber_phone("")

    assert "לא יכול להיכנס" in owner.text(owner.message())
    assert "לא יכול להיכנס" in owner.text(owner.by("barber-phone-note"))
    stored = next(b for b in barbers.find(persona="owner").assert_ok(200).content if b["id"] == barber["id"])
    assert stored["phone"] is None


def test_the_phone_shown_is_the_selected_barbers(owner_screen, barbers):
    first = barbers.create_fake_barber(phone=Customers.new_phone())
    second = barbers.create_fake_barber()
    owner = owner_screen()

    owner.select_barber(first["id"])
    expect(owner.by("barber-phone")).to_have_value(first["phone"] if "phone" in first else "")
    owner.select_barber(second["id"])

    expect(owner.by("barber-phone")).to_have_value("")


@pytest.mark.parametrize(("typed", "word"), [("taken", "שייך")])
def test_a_phone_that_is_somebody_elses_is_refused_in_words(owner_screen, barbers, typed, word):
    other = barbers.create_fake_barber(phone=Customers.new_phone())
    barber = barbers.create_fake_barber()
    stored = next(b for b in barbers.find(persona="owner").assert_ok(200).content if b["id"] == other["id"])
    owner = owner_screen().select_barber(barber["id"])

    owner.save_barber_phone(stored["phone"] if typed == "taken" else typed)

    expect(owner.message()).to_have_attribute("data-kind", "error")
    assert word in owner.text(owner.message())
    mine = next(b for b in barbers.find(persona="owner").assert_ok(200).content if b["id"] == barber["id"])
    assert mine["phone"] is None


def test_a_new_barber_with_a_bad_phone_is_not_added(owner_screen, barbers, name):
    owner: OwnerScreen = owner_screen()

    owner.by("new-barber-name").fill(name)
    owner.by("new-barber-phone").fill("12345")

    expect(owner.by("new-barber-phone-error")).to_have_text("המספר חייב להתחיל ב־05")
    expect(owner.by("add-barber")).to_be_disabled()
    assert name not in [b["display_name"] for b in barbers.find(persona="owner").assert_ok(200).content]
