"""Can someone reach the product without a mouse, and does a screen reader
have anything to announce?

These are the cheapest accessibility checks that catch the most common defects.
They are not a full audit and do not pretend to be.
"""

import pytest
from playwright.sync_api import expect


def test_every_input_has_a_name_a_screen_reader_can_announce(page, ui_base_url):
    page.goto(ui_base_url)

    for field in ("username", "password"):
        element = page.get_by_test_id(field)
        label = element.get_attribute("aria-label") or element.get_attribute("placeholder")
        assert label, f"the {field} field has nothing to announce"


def test_the_password_field_is_masked(page, ui_base_url):
    page.goto(ui_base_url)
    assert page.get_by_test_id("password").get_attribute("type") == "password"


def test_the_whole_sign_in_works_from_the_keyboard_alone(page, ui_base_url, credentials):
    username, password = credentials("member")
    page.goto(ui_base_url)

    page.get_by_test_id("username").focus()
    page.keyboard.type(username)
    page.keyboard.press("Tab")
    page.keyboard.type(password)
    page.keyboard.press("Tab")
    page.keyboard.press("Enter")

    expect(page.get_by_test_id("budget")).to_be_visible()


def test_tab_order_follows_the_order_on_screen(page, ui_base_url):
    page.goto(ui_base_url)
    page.get_by_test_id("username").focus()

    order = []
    for _ in range(3):
        order.append(page.evaluate("document.activeElement.dataset.testid"))
        page.keyboard.press("Tab")

    assert order == ["username", "password", "login"], f"tab order was {order}"


def test_the_page_declares_a_language(page, ui_base_url):
    page.goto(ui_base_url)
    assert page.locator("html").get_attribute(
        "lang"
    ), "a missing lang attribute breaks screen reader pronunciation"


def test_the_page_has_a_title(page, ui_base_url):
    page.goto(ui_base_url)
    assert page.title().strip(), "the tab is unidentifiable without a title"


@pytest.mark.parametrize("width, height", [(375, 812), (768, 1024)], ids=["phone", "tablet"])
def test_the_sign_in_form_is_usable_on_a_small_screen(page, ui_base_url, width, height):
    page.set_viewport_size({"width": width, "height": height})
    page.goto(ui_base_url)

    for field in ("username", "password", "login"):
        expect(page.get_by_test_id(field)).to_be_visible()

    box = page.get_by_test_id("login").bounding_box()
    assert box["width"] >= 44 and box["height"] >= 24, f"the sign in button is too small to tap: {box}"
