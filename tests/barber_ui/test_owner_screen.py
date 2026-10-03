"""The owner's screen, checked twice: on the screen, and from the other side -
what a customer is offered after the owner changes something. An hours editor
that saves is not the point; the customer's times changing is."""

import secrets

import pytest
from playwright.sync_api import expect

from utils.local_time import at_local, local_day, next_weekday, parse_instant

SHOP_HOURS = {day: ["10:00", "19:00"] for day in ("sun", "mon", "tue", "wed", "thu")} | {
    "fri": None,
    "sat": None,
}


def offered(barbers, barber_id, day, service_id) -> list[str]:
    return [parse_instant(s["start"]).isoformat() for s in barbers.slots(barber_id, day, service_id)]


def test_the_owner_gets_the_management_screen_and_a_booking_form_that_asks_for_a_name(owner_screen):
    screen = owner_screen()

    expect(screen.by("owner")).to_be_visible()
    expect(screen.by("book-panel")).to_be_visible()
    expect(screen.by("guest-field")).to_be_visible()
    expect(screen.by("hours-row")).to_have_count(7)


def test_a_customer_and_a_barber_never_get_the_management_screen(shop, account, credentials):
    shop.sign_in_as(account)
    expect(shop.by("owner")).to_be_hidden()

    shop.by("logout").click()
    username, password = credentials("barber")
    shop.sign_in(username, password)
    expect(shop.by("owner")).to_be_hidden()
    expect(shop.by("book-panel")).to_be_hidden()


def test_new_hours_change_what_customers_are_offered(owner_screen, barbers, ui_haircut, shop_tz):
    barber = barbers.create_fake_barber(opening="10:00", closing="19:00")
    screen = owner_screen().select_barber(barber["id"])
    for day in ("sun", "tue", "wed", "thu", "fri", "sat"):
        screen.set_day(day)
    screen.set_day("mon", "12:00", "14:00").save_hours()

    expect(screen.message()).to_have_attribute("data-kind", "ok")
    assert barbers.hours(barber["id"]) == {
        "sun": None,
        "mon": ["12:00", "14:00"],
        "tue": None,
        "wed": None,
        "thu": None,
        "fri": None,
        "sat": None,
    }
    monday, tuesday = next_weekday(shop_tz, "mon"), next_weekday(shop_tz, "tue")
    times = [s["start_local"][11:16] for s in barbers.slots(barber["id"], monday, ui_haircut["id"])]
    assert (times[0], times[-1]) == (
        "12:00",
        "13:30",
    ), "a 30 minute haircut fits 12:00 to 13:30 in a 12-14 day"
    assert barbers.slots(barber["id"], tuesday, ui_haircut["id"]) == []


def test_closing_before_opening_is_refused_and_nothing_is_saved(owner_screen, barbers):
    barber = barbers.create_fake_barber(opening="10:00", closing="19:00")
    screen = owner_screen().select_barber(barber["id"])

    screen.set_day("sun", "15:00", "14:00").save_hours()

    expect(screen.message()).to_have_attribute("data-kind", "error")
    expect(screen.message()).to_contain_text("אחרי שעת הפתיחה")
    assert barbers.hours(barber["id"])["sun"] == ["10:00", "19:00"]


@pytest.mark.parametrize("bad", ["10:10", "9:00", "25:00", "abc"])
def test_a_time_that_is_not_on_the_quarter_hour_is_refused(owner_screen, barbers, bad):
    barber = barbers.create_fake_barber(opening="10:00", closing="19:00")
    screen = owner_screen().select_barber(barber["id"])

    screen.set_day("mon", bad, "18:00").save_hours()

    expect(screen.message()).to_contain_text("ברבע שעה עגולה")
    assert barbers.hours(barber["id"])["mon"] == ["10:00", "19:00"]


def test_a_day_off_takes_the_barber_out_that_day_and_can_be_undone(
    owner_screen, barbers, ui_haircut, shop_tz
):
    barber = barbers.create_fake_barber()
    day = local_day(shop_tz, 5)
    screen = owner_screen().select_barber(barber["id"])

    screen.add_day_off(day)
    assert screen.days_off() == [day.isoformat()]
    assert offered(barbers, barber["id"], day, ui_haircut["id"]) == []

    screen.remove_day_off(day)
    assert screen.days_off() == []
    assert offered(barbers, barber["id"], day, ui_haircut["id"]), "the day came back"


def test_the_same_day_off_twice_is_explained(owner_screen, barbers, shop_tz):
    barber = barbers.create_fake_barber()
    day = local_day(shop_tz, 6)
    screen = owner_screen().select_barber(barber["id"])

    screen.add_day_off(day).add_day_off(day)

    expect(screen.message()).to_contain_text("כבר בחופש")
    assert screen.days_off() == [day.isoformat()]


def test_a_new_barber_is_bookable_at_once_on_the_shops_hours(owner_screen, barbers, ui_haircut, shop_tz):
    name, username = f"ספר {secrets.token_hex(3)}", f"qa-ui-barber-{secrets.token_hex(4)}"
    screen = owner_screen()

    screen.add_barber(name, username, "long-enough-password")

    expect(screen.message()).to_have_attribute("data-kind", "ok")
    created = next(
        b for b in barbers.find(persona="owner").assert_ok(200).content if b["display_name"] == name
    )
    assert screen.by("barber").input_value() == created["id"], "the new barber is the one now selected"
    assert barbers.hours(created["id"]) == SHOP_HOURS
    sunday = next_weekday(shop_tz, "sun")
    assert barbers.slots(created["id"], sunday, ui_haircut["id"])[0]["start_local"][11:16] == "10:00"


def test_a_new_service_is_priced_in_shekels_exactly(owner_screen, services):
    name = f"QA שירות {secrets.token_hex(3)}"

    owner_screen().add_service(name, 45, "92.55")

    created = next(s for s in services.find(persona="owner").assert_ok(200).content if s["name"] == name)
    # 92.55 * 100 is 9254.999999999998 in floating point. The page converts in
    # whole numbers, so the shop charges what it typed.
    assert created["price_minor"] == 9255
    assert created["duration_minutes"] == 45


@pytest.mark.parametrize("bad", ["80.555", "abc", "-5", "80,50"])
def test_a_price_that_is_not_shekels_and_agorot_is_refused(owner_screen, services, bad):
    name = f"QA שירות {secrets.token_hex(3)}"
    screen = owner_screen()

    screen.add_service(name, 30, bad)

    expect(screen.message()).to_contain_text("המחיר צריך להיות מספר בשקלים")
    assert not [s for s in services.find(persona="owner").assert_ok(200).content if s["name"] == name]


def test_the_same_service_name_twice_is_explained(owner_screen, services):
    existing = services.create_fake_service()

    screen = owner_screen().add_service(existing["name"], 30, "50")

    expect(screen.message()).to_contain_text("כבר יש שירות בשם הזה")


def test_a_price_change_reaches_new_bookings_only(
    owner_screen, services, bookings, barbers, new_customer, shop_tz
):
    service = services.create_fake_service(duration_minutes=30, price_minor=8000)
    barber = barbers.create_fake_barber()
    customer = new_customer()
    day = local_day(shop_tz, 7)
    before = bookings.create_booking(
        barber["id"], service["id"], at_local(shop_tz, day, "10:00"), persona=customer
    )

    owner_screen().save_service(service["id"], price="99.90")

    after = bookings.create_booking(
        barber["id"], service["id"], at_local(shop_tz, day, "11:00"), persona=customer
    )
    assert bookings.get_by_id(before["id"], persona=customer).assert_ok(200).as_dict["price_minor"] == 8000
    assert after["price_minor"] == 9990


def test_withdrawing_a_service_hides_it_from_customers(owner_screen, services):
    service = services.create_fake_service()

    screen = owner_screen().save_service(service["id"], offered=False)

    expect(screen.service_row(service["id"])).to_have_attribute("data-active", "false")
    offered_to_customers = {s["id"] for s in services.find(persona="customer").assert_ok(200).content}
    assert service["id"] not in offered_to_customers


def test_the_owner_cancels_a_booking_even_inside_the_cutoff(
    owner_screen, barbers, bookings, new_customer, ui_haircut, shop_tz
):
    barber = barbers.create_fake_barber()
    soon = (
        barbers.slots(barber["id"], local_day(shop_tz, 0), ui_haircut["id"])
        + barbers.slots(barber["id"], local_day(shop_tz, 1), ui_haircut["id"])
    )[1]
    booking = bookings.create_booking(barber["id"], ui_haircut["id"], soon["start"], persona=new_customer())
    screen = owner_screen().select_barber(barber["id"])

    screen.cancel(soon["start_local"][11:16])

    expect(screen.message()).to_have_attribute("data-kind", "ok")
    assert bookings.get_by_id(booking["id"], persona="owner").assert_ok(200).as_dict["status"] == "cancelled"
