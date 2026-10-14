"""The card that offers to put the shop on the home screen: on an iPhone, the steps in Safari; where
Chrome offers its own install, a button for it. A customer is offered it for a day after each booking,
the staff until they add it. The browser's pieces are stand-ins: an iPhone's Safari, which has no push
outside the home screen, and Chrome's install event, which keeps a record of being used."""

from datetime import UTC, datetime, timedelta

import pytest
from playwright.sync_api import expect

from utils.local_time import at_local, local_day

IPHONE = (
    "delete window.PushManager; delete window.Notification;"
    "Object.defineProperty(navigator, 'userAgent', {value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'});"
)
CHROME = """
Object.defineProperty(navigator, "userAgent", { value: "Mozilla/5.0 (Linux; Android 14; Pixel 7) Chrome/130.0 Mobile" });
window.__installs = 0;
addEventListener("load", () => {
  const offer = new Event("beforeinstallprompt", { cancelable: true });
  offer.prompt = async () => { window.__installs += 1; return { outcome: "accepted" }; };
  dispatchEvent(offer);
});
"""
ON_THE_HOME_SCREEN = """
const real = window.matchMedia.bind(window);
window.matchMedia = (query) => query.includes("display-mode: standalone") ? { matches: true, media: query, addEventListener() {}, removeEventListener() {} } : real(query);
"""


def book(bookings, barbers, haircut, account, shop_tz, days=6, hhmm="11:00"):
    barber = barbers.create_fake_barber()
    start = at_local(shop_tz, local_day(shop_tz, days), hhmm)
    return bookings.create_booking(barber["id"], haircut["id"], start, persona=account["persona"])


@pytest.fixture
def booked(bookings, barbers, ui_haircut, account, shop_tz):
    return book(bookings, barbers, ui_haircut, account, shop_tz)


def mine(shop, account, *scripts):
    for script in scripts:
        shop.page.add_init_script(script)
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("mine")
    return signed_in


def test_on_an_iphone_a_customer_who_just_booked_is_shown_how_to_add_the_shop(booked, shop, account):
    signed_in = mine(shop, account, IPHONE)

    band = signed_in.by("install-card")

    expect(band).to_be_visible()
    steps = signed_in.text(band.get_by_test_id("install-steps"))
    assert "שיתוף" in steps and "״הוספה למסך הבית״" in steps
    expect(signed_in.by("bookings").get_by_test_id("install-card")).to_have_count(0)
    expect(signed_in.by("push-card")).to_have_count(0)


def test_the_band_stands_under_the_bookings_and_on_a_phone_only_with_them(booked, shop, account):
    shop.page.set_viewport_size({"width": 390, "height": 844})
    signed_in = mine(shop, account, IPHONE)
    band = signed_in.by("install-card")

    assert (
        band.bounding_box()["y"]
        > signed_in.by("right-panel").bounding_box()["y"]
        + signed_in.by("right-panel").bounding_box()["height"]
        - 1
    )
    signed_in.show_tab("book")

    expect(band).to_be_hidden()


def test_a_customer_with_nothing_booked_is_not_offered_it(shop, account):
    signed_in = mine(shop, account, IPHONE)

    expect(signed_in.by("install-card")).to_be_hidden()


def test_a_day_after_the_booking_it_is_offered_no_more(booked, shop, account):
    shop.page.clock.set_fixed_time(datetime.now(UTC) + timedelta(hours=25))

    signed_in = mine(shop, account, IPHONE)

    expect(signed_in.by("install-card")).to_be_hidden()


def test_not_now_waits_for_the_next_booking(booked, bookings, barbers, ui_haircut, account, shop, shop_tz):
    signed_in = mine(shop, account, IPHONE)
    signed_in.by("install-later").click()
    signed_in.settled()
    expect(signed_in.by("install-card")).to_be_hidden()
    signed_in.reload()
    signed_in.show_tab("mine")
    expect(signed_in.by("install-card")).to_be_hidden()

    book(bookings, barbers, ui_haircut, account, shop_tz, days=7, hhmm="12:00")
    signed_in.reload()
    signed_in.show_tab("mine")

    expect(signed_in.by("install-card")).to_be_visible()


def test_where_chrome_offers_to_install_the_card_is_a_button_for_it(booked, shop, account):
    signed_in = mine(shop, account, CHROME)
    card = signed_in.by("install-card")
    expect(card.get_by_test_id("install-steps")).to_have_count(0)

    card.get_by_test_id("install-now").click()
    signed_in.settled()

    assert signed_in.page.evaluate("window.__installs") == 1
    expect(signed_in.by("install-card")).to_be_hidden()


def test_once_on_the_home_screen_it_is_not_offered(booked, shop, account):
    signed_in = mine(shop, account, CHROME, ON_THE_HOME_SCREEN)

    expect(signed_in.by("install-card")).to_be_hidden()


def test_the_owner_is_offered_it_without_a_booking_and_again_a_day_after_not_now(owner_screen, page):
    page.add_init_script(IPHONE)
    owner = owner_screen()
    expect(owner.by("install-card")).to_be_visible()

    owner.by("install-later").click()
    owner.settled()
    expect(owner.by("install-card")).to_be_hidden()
    page.clock.set_fixed_time(datetime.now(UTC) + timedelta(hours=25))
    owner.reload()
    owner.settled()

    expect(owner.by("install-card")).to_be_visible()
