"""Accessibility: the page checked against WCAG 2.2 AA, and used without a mouse.

axe-core finds what a machine can see - missing names, contrast, a target too
small to hit - and that is a part of what goes wrong, not all of it. The rest is
using the page: here, a whole booking and a cancellation from the keyboard
alone, and where the focus lands after every step. Writing these found that
reaching the book button took a Tab for every time of the day, and that closing
the popup or cancelling dropped the focus to the top of the page.
"""

from __future__ import annotations

import pytest
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect

from obj.barber.booking_page import BookingPage
from utils.local_time import local_day

AXE = Axe()
WCAG_22_AA = {"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]}}


def violations(page) -> list[str]:
    return [
        f"{v['id']}: {v['help']} - {len(v['nodes'])} element(s), e.g. {v['nodes'][0]['target']}"
        for v in AXE.run(page, options=WCAG_22_AA).response["violations"]
    ]


def focused(page) -> dict:
    return page.evaluate(
        """() => {
            const e = document.activeElement;
            return {testid: e.dataset.testid || null, text: (e.textContent || "").trim(), checked: e.getAttribute("aria-checked")};
        }"""
    )


@pytest.fixture
def keyboard(browser_name):
    if browser_name == "webkit":
        pytest.skip(
            "Safari's Tab moves only between text fields unless the user turns on keyboard navigation in "
            "macOS settings - a browser setting the page cannot change, so a WebKit run would test the setting"
        )


def test_every_screen_meets_wcag_2_2_aa(shop, account, credentials, ui_barber, ui_haircut, shop_tz):
    shop.open()
    assert violations(shop.page) == [], "the sign-in screen"

    shop.sign_in_as(account)
    shop.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 4)).pick("13:00")
    assert violations(shop.page) == [], "the booking screen, a time chosen"

    shop.book(keep_popup=True)
    assert violations(shop.page) == [], "the popup"
    shop.close_popup()

    shop.by("logout").click()
    shop.sign_in(*credentials("owner"), navigate=False)
    expect(shop.by("owner")).to_be_visible()
    assert violations(shop.page) == [], "the owner's screen"


def test_a_whole_booking_and_its_cancellation_with_the_keyboard_alone(
    page, env_config, customers, sms_inbox, barbers, ui_haircut, shop_tz, keyboard
):
    ten_to_twelve = barbers.create_fake_barber(opening="10:00", closing="12:00")
    shop = BookingPage(page, env_config["url"]).open()
    phone = customers.new_phone()
    seen = sms_inbox.last_id(phone)

    # The shop's contact buttons come first, as they stand first on the screen -
    # when the shop has any - and then the first field.
    passed = []
    for _ in range(8):
        page.keyboard.press("Tab")
        if focused(page)["testid"] == "full-name":
            break
        passed.append(focused(page)["testid"])
    assert focused(page)["testid"] == "full-name", f"Tab never reached the first field: {passed}"
    assert all(t.startswith("shop-") for t in passed), f"something before the first field: {passed}"
    page.keyboard.type("דנה מקלדת")
    page.keyboard.press("Tab")
    page.keyboard.type(phone)
    page.keyboard.press("Enter")
    expect(shop.by("code-form")).to_be_visible()
    assert focused(page)["testid"] == "code", "the focus moves to the code"
    page.keyboard.type(sms_inbox.code_for(phone, after=seen))
    expect(shop.by("app")).to_be_visible()
    shop.settled()
    shop.choose(ten_to_twelve["id"], ui_haircut["id"], local_day(shop_tz, 5))

    shop.by("days").locator('td[tabindex="0"]').focus()
    for _ in range(10):
        page.keyboard.press("Tab")
        if focused(page)["testid"] == "slot":
            break
    assert focused(page)["text"] == "10:00", "Tab enters the times at the first one"
    page.keyboard.press("Tab")
    assert focused(page)["testid"] != "slot", "a second Tab leaves the times, it does not walk through them"
    page.keyboard.press("Shift+Tab")
    assert focused(page)["text"] == "10:00", "and Shift+Tab comes back to the same stop"

    page.keyboard.press("ArrowLeft")
    assert focused(page) == {
        "testid": "slot",
        "text": "10:15",
        "checked": "true",
    }, "right to left: the left arrow is the next time"
    page.keyboard.press("ArrowRight")
    assert focused(page)["text"] == "10:00"
    page.keyboard.press("End")
    assert focused(page)["text"] == "11:30"
    page.keyboard.press("Home")
    for _ in range(3):
        page.keyboard.press("ArrowLeft")
    assert focused(page) == {"testid": "slot", "text": "10:45", "checked": "true"}
    expect(shop.by("confirm")).to_be_visible()

    page.keyboard.press("Tab")
    assert (
        focused(page)["testid"] == "book"
    ), "the times are one stop: one Tab from the chosen one to the book button"
    page.keyboard.press("Enter")
    expect(shop.by("popup")).to_be_visible()
    assert focused(page)["testid"] == "popup-close", "the popup takes the focus"
    page.keyboard.press("Escape")
    expect(shop.by("popup")).to_be_hidden()
    expect(shop.row_at("10:45"), "the focus goes to the new booking, not the top of the page").to_be_focused()

    page.keyboard.press("Tab")
    assert focused(page)["testid"] == "move", "the gentler of the two comes first"
    page.keyboard.press("Tab")
    assert focused(page)["testid"] == "cancel"
    page.keyboard.press("Enter")
    expect(shop.row_at("10:45")).to_have_attribute("data-status", "cancelled")
    expect(shop.row_at("10:45"), "after cancelling, the focus stays on that booking").to_be_focused()


def test_every_stop_on_the_way_shows_where_the_focus_is(signed_in, keyboard):
    seen = []
    for _ in range(25):
        signed_in.page.keyboard.press("Tab")
        ring = signed_in.page.evaluate(
            """() => {
                const e = document.activeElement;
                if (e === document.body) return null;
                const s = getComputedStyle(e);
                return {what: `${e.tagName.toLowerCase()} ${e.dataset.testid || e.id}`, style: s.outlineStyle, width: parseFloat(s.outlineWidth)};
            }"""
        )
        if ring is not None:
            seen.append(ring)

    assert len(seen) >= 5, "the walk reached the page's controls"
    unmarked = [r["what"] for r in seen if r["style"] == "none" or r["width"] < 2]
    assert unmarked == [], f"focused with no visible ring: {unmarked}"


def test_the_accessibility_statement_is_one_step_from_every_screen_and_says_what_the_law_asks(shop, account):
    shop.open()
    expect(shop.by("accessibility-link")).to_be_visible()
    shop.sign_in_as(account)
    expect(shop.by("accessibility-link")).to_be_visible()

    shop.by("accessibility-link").click()
    statement = shop.page
    expect(statement).to_have_url(shop.base_url + "/accessibility")
    expect(statement.locator("html")).to_have_attribute("lang", "he")
    expect(statement.get_by_test_id("level")).to_contain_text("WCAG 2.2")
    expect(statement.get_by_test_id("level")).to_contain_text("5568")
    expect(statement.get_by_test_id("limits")).to_contain_text("קורא מסך")
    expect(statement.get_by_test_id("premises")).not_to_be_empty()
    expect(statement.get_by_test_id("contact").locator("a[href^='mailto:']")).to_have_count(1)
    expect(statement.get_by_test_id("updated")).to_contain_text("עודכן")
    assert "{{" not in statement.content(), "a placeholder was left unfilled"
    assert violations(statement) == [], "the statement itself"

    statement.get_by_test_id("back").click()
    expect(shop.by("app")).to_be_visible()
