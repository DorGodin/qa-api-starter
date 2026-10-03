"""The booking page on a phone: the narrowest screen in use, a common iPhone and
a common Android, each with its own screen size, touch and user agent.

Each test opens its own phone, so these run in every UI run - the desktop one
included - and in the WebKit run they run on Safari's engine. The whole suite
on a phone is the other half: `make ui-barber-mobile` runs every UI test with
--device.
"""

from __future__ import annotations

import secrets

import pytest
from playwright.sync_api import expect

from obj.barber.booking_page import BookingPage, OwnerScreen, a_device
from utils.local_time import local_day

PHONES = ["iPhone SE", "iPhone 13", "Pixel 7"]

# A finger needs about 44 CSS pixels (Apple's Human Interface Guidelines; WCAG
# 2.5.5). A checkbox sits beside its words and gets the WCAG 2.5.8 minimum.
FINGER, CHECKBOX = 44, 24

# Below 16px, Safari on iOS zooms the whole page in when a field takes the
# focus, and leaves it zoomed. Only a font size of 16px or more prevents it.
NO_ZOOM_FONT = 16

CONTROLS = "button, select, input, a[href]"


@pytest.fixture(params=PHONES)
def phone(request, browser, playwright):
    context = a_device(browser, **playwright.devices[request.param], locale="he-IL")
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def phone_shop(phone, env_config) -> BookingPage:
    return BookingPage(phone, env_config["url"])


@pytest.fixture
def phone_owner(phone, env_config, credentials) -> OwnerScreen:
    username, password = credentials("owner")
    return OwnerScreen(phone, env_config["url"]).sign_in(username, password)


def sideways_overflow(page) -> list[str]:
    """Everything that reaches past either edge of the screen. scrollWidth alone
    is not enough: a page that hides its overflow cuts content off without ever
    scrolling."""
    return page.evaluate(
        """() => {
            const width = window.innerWidth;
            const out = [];
            if (document.documentElement.scrollWidth > width) out.push(`the page scrolls to ${document.documentElement.scrollWidth}px on a ${width}px screen`);
            for (const el of document.querySelectorAll("body *")) {
                if (!el.offsetParent || el.closest("dialog:not([open])")) continue;
                const r = el.getBoundingClientRect();
                if (r.width && (r.left < -1 || r.right > width + 1)) out.push(`${el.tagName} ${el.dataset.testid || el.textContent.trim().slice(0, 20)}: ${Math.round(r.left)}..${Math.round(r.right)}`);
            }
            return out.slice(0, 10);
        }"""
    )


def too_small_to_tap(page) -> list[str]:
    return page.evaluate(
        """([selector, finger, checkbox]) => [...document.querySelectorAll(selector)]
            .filter((el) => el.offsetParent && el.type !== "hidden")
            .map((el) => {
                const r = el.getBoundingClientRect();
                const need = el.type === "checkbox" ? checkbox : finger;
                const tooSmall = r.height < need || (el.tagName !== "INPUT" && el.tagName !== "SELECT" && r.width < need) || (el.type === "checkbox" && r.width < need);
                return tooSmall ? `${el.tagName.toLowerCase()} ${el.dataset.testid || el.textContent.trim().slice(0, 12)}: ${Math.round(r.width)}x${Math.round(r.height)}, needs ${need}` : null;
            })
            .filter(Boolean)
            .slice(0, 10)""",
        [CONTROLS, FINGER, CHECKBOX],
    )


def clipped_labels(page) -> list[str]:
    """Buttons narrower than their own words plus their padding - a row squeezed
    the button. Measured against the words, not scrollWidth: Chromium lets the
    words slide into the padding up to the border, so a squeezed button never
    overflows there, and only looks broken."""
    return page.evaluate(
        """() => [...document.querySelectorAll("button")]
            .filter((el) => el.offsetParent)
            .map((el) => {
                const words = document.createRange();
                words.selectNodeContents(el);
                const cs = getComputedStyle(el);
                const needs = words.getBoundingClientRect().width + parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight)
                    + parseFloat(cs.borderLeftWidth) + parseFloat(cs.borderRightWidth);
                const has = el.getBoundingClientRect().width;
                return has + 1 < needs ? `${el.dataset.testid || el.textContent.trim()}: ${Math.round(has)}px wide, its words and padding need ${Math.round(needs)}px` : null;
            })
            .filter(Boolean)
            .slice(0, 10)"""
    )


def zooming_fields(page) -> list[str]:
    return page.evaluate(
        """(least) => [...document.querySelectorAll("input:not([type=checkbox]), select, textarea")]
            .filter((el) => el.offsetParent)
            .map((el) => [el.dataset.testid || el.id, parseFloat(getComputedStyle(el).fontSize)])
            .filter(([, size]) => size < least)
            .map(([name, size]) => `${name}: ${size}px`)""",
        NO_ZOOM_FONT,
    )


def fits_on_screen(page, locator) -> bool:
    box, screen = locator.bounding_box(), page.viewport_size
    return (
        box["x"] >= 0
        and box["y"] >= 0
        and box["x"] + box["width"] <= screen["width"]
        and box["y"] + box["height"] <= screen["height"]
    )


def test_the_sign_in_screen_fits_and_its_fields_do_not_zoom(phone_shop):
    phone_shop.open()

    assert sideways_overflow(phone_shop.page) == []
    assert too_small_to_tap(phone_shop.page) == []
    assert zooming_fields(phone_shop.page) == []


def test_the_booking_screen_fits_a_phone_with_the_times_on_it(
    phone_shop, account, ui_barber, ui_haircut, shop_tz
):
    phone_shop.sign_in_as(account)
    phone_shop.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 3))
    expect(phone_shop.by("slot").first).to_be_visible()
    booking, bookings = (
        phone_shop.by("left-panel").bounding_box(),
        phone_shop.by("right-panel").bounding_box(),
    )

    assert (
        booking["y"] + booking["height"] <= bookings["y"]
    ), "on a phone the two columns stack, booking on top"
    assert sideways_overflow(phone_shop.page) == []
    assert too_small_to_tap(phone_shop.page) == []
    assert zooming_fields(phone_shop.page) == []


# A day in the month's calendar is a seventh of the panel wide: on the narrowest
# phone less than a finger's 44px, so it is held to WCAG 2.5.8's 24px - and made
# a full finger tall.
DAY_WIDTH, DAY_HEIGHT = 24, 44


def test_every_day_of_the_month_is_big_enough_to_tap(phone_shop, account, ui_barber, ui_haircut, shop_tz):
    phone_shop.sign_in_as(account)
    phone_shop.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 3))

    sizes = (
        phone_shop.by("days")
        .locator("td[data-date]")
        .evaluate_all(
            "cells => cells.map(c => [c.dataset.date, c.getBoundingClientRect().width, c.getBoundingClientRect().height])"
        )
    )

    small = [(d, round(w), round(h)) for d, w, h in sizes if w < DAY_WIDTH or h < DAY_HEIGHT]
    assert small == [], f"days too small to tap: {small}"


def test_a_customer_books_by_touch_and_the_answer_fits_on_the_screen(
    phone_shop, account, barbers, ui_haircut, shop_tz
):
    barber = barbers.create_fake_barber()
    phone_shop.sign_in_as(account)
    phone_shop.choose(barber["id"], ui_haircut["id"], local_day(shop_tz, 3))

    phone_shop.by("slot").filter(has_text="10:00").first.tap()
    expect(phone_shop.by("confirm")).to_be_visible()
    phone_shop.by("book").tap()
    phone_shop.settled()

    popup = phone_shop.by("popup")
    expect(popup).to_be_visible()
    expect(popup).to_have_attribute("data-kind", "ok")
    assert fits_on_screen(phone_shop.page, popup), "the whole answer, and its close button, on the screen"
    assert too_small_to_tap(phone_shop.page) == []

    phone_shop.by("popup-close").tap()
    expect(popup).to_be_hidden()
    expect(phone_shop.row_at("10:00")).to_be_visible()
    assert clipped_labels(phone_shop.page) == []


def test_the_owner_screen_fits_a_phone(phone_owner):
    expect(phone_owner.by("owner")).to_be_visible()

    assert sideways_overflow(phone_owner.page) == []
    assert too_small_to_tap(phone_owner.page) == []
    assert zooming_fields(phone_owner.page) == []
    assert clipped_labels(phone_owner.page) == []


@pytest.mark.parametrize(
    "section, panel", [("שעות עבודה", "hours-panel"), ("שירותים", "services-panel"), ("תורים", "right-panel")]
)
def test_the_owner_jumps_to_each_section_without_scrolling_through_the_rest(phone_owner, section, panel):
    nav = phone_owner.by("owner-nav")
    expect(nav).to_be_visible()

    nav.get_by_role("link", name=section, exact=True).tap()

    heading = phone_owner.by(panel).locator("h2")
    expect(heading).to_be_in_viewport()
    assert (
        heading.bounding_box()["y"] >= nav.bounding_box()["y"] + nav.bounding_box()["height"] - 1
    ), "the section's title is not hidden under the menu that stays on top"
    slim = phone_owner.by("mini-brand").bounding_box()
    assert (
        nav.bounding_box()["y"] >= slim["y"] + slim["height"] - 1
    ), "the menu stands under the slim bar, not behind it"


def test_a_new_service_added_on_a_phone_is_offered_to_customers(phone_owner, services):
    name = f"QA mobile {secrets.token_hex(4)}"
    phone_owner.by("owner-nav").get_by_role("link", name="שירותים", exact=True).tap()

    phone_owner.add_service(name, 30, "95")

    expect(phone_owner.message()).to_have_attribute("data-kind", "ok")
    assert name in [s["name"] for s in services.find(persona="owner").assert_ok(200).content]


def test_at_200_percent_zoom_the_page_still_fits_and_books(
    browser, env_config, account, ui_barber, ui_haircut, shop_tz
):
    # WCAG 1.4.4 and 1.4.10: zooming a 1100px window to 200% leaves the page 550
    # CSS pixels to lay itself out in, at twice the pixel density.
    context = a_device(browser, viewport={"width": 550, "height": 380}, device_scale_factor=2, locale="he-IL")
    try:
        zoomed = BookingPage(context.new_page(), env_config["url"])
        zoomed.sign_in_as(account)
        zoomed.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 6)).pick("15:30")

        assert sideways_overflow(zoomed.page) == []
        zoomed.by("book").click()
        zoomed.settled()
        expect(zoomed.by("popup")).to_be_visible()
        assert fits_on_screen(zoomed.page, zoomed.by("popup")), "the whole answer, at 200%"
    finally:
        context.close()


def test_a_signed_in_screen_opens_at_its_top(phone_owner):
    """The sign-in form sits low on a phone; the screen after it opened scrolled
    to where the form had been, its first fields under the owner's menu."""
    phone_owner.settled()

    assert phone_owner.page.evaluate("window.scrollY") == 0


# The height left above a phone's keyboard: an iPhone 13 with the number pad open.
KEYBOARD_OPEN = 470


def test_the_brand_shrinks_to_a_slim_bar_once_it_scrolls_away_and_comes_back_at_the_top(phone_shop):
    """Scrolled, the round picture was cut in half at the top of the screen. Now
    a slim bar with the brand comes in over it, and leaves at the top."""
    page = phone_shop.page
    page.set_viewport_size({"width": page.viewport_size["width"], "height": KEYBOARD_OPEN})
    phone_shop.open()
    slim = phone_shop.by("mini-brand")
    expect(slim).to_be_hidden()

    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")

    expect(slim).to_be_visible()
    expect(slim).to_have_text(phone_shop.by("shop-brand").inner_text())
    page.wait_for_function(
        "() => document.querySelector('[data-testid=mini-brand]').getBoundingClientRect().top === 0",
        timeout=2000,
    )

    page.evaluate("window.scrollTo(0, 0)")

    expect(slim).to_be_hidden()


def test_a_field_the_keyboard_reaches_is_not_under_the_slim_bar(phone_shop):
    page = phone_shop.page
    page.set_viewport_size({"width": page.viewport_size["width"], "height": KEYBOARD_OPEN})
    phone_shop.open()
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    slim = phone_shop.by("mini-brand")
    expect(slim).to_be_visible()

    phone_shop.by("full-name").focus()

    field = phone_shop.by("full-name").bounding_box()
    covered_to = slim.bounding_box()["height"] if slim.is_visible() else 0
    assert field["y"] >= covered_to, "the name field is hidden under the slim bar"
