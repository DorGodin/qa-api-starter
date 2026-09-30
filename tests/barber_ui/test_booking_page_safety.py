"""What the page must never do: show the wrong time, run somebody's name as
code, or give away which half of a login was wrong."""

import pytest
from playwright.sync_api import expect

from obj.barber.booking_page import BARBER, DATE, PASSWORD, SERVICE, USERNAME, YOUR_NAME, BookingPage
from utils.local_time import local_day


@pytest.mark.browser_context_args(timezone_id="America/New_York")
def test_times_are_shown_on_the_shop_clock_whatever_the_browsers_time_zone(
    shop, account, barbers, ui_haircut, shop_tz
):
    nine_to_seven = barbers.create_fake_barber(opening="09:00", closing="19:00")
    shop.sign_in(account["username"], account["password"])
    assert shop.page.evaluate("Intl.DateTimeFormat().resolvedOptions().timeZone") == "America/New_York"

    shop.choose(nine_to_seven["id"], ui_haircut["id"], local_day(shop_tz, 3))

    assert shop.times()[0] == "09:00", "the shop opens at 09:00 on its own clock, wherever the customer is"
    assert shop.times()[-1] == "18:30", "the last 30 minute haircut starts at 18:30 shop time"
    shop.pick("09:00").book()
    expect(shop.row_at("09:00")).to_be_visible()


def test_a_name_that_looks_like_html_is_shown_as_text_and_never_run(shop, customers):
    payload = customers.build_signup_payload(display_name='<img src=x onerror="window.__ran=1">')

    shop.sign_up(payload["display_name"], payload["username"], payload["password"])

    expect(shop.by("display-name")).to_contain_text('<img src=x onerror="window.__ran=1">')
    assert shop.page.evaluate("window.__ran") is None, "a display name was executed as code"


def test_a_wrong_password_and_an_unknown_user_look_the_same(page, env_config, credentials):
    owner, _ = credentials("owner")
    answers = []
    for username in (owner, "nobody-at-all"):
        screen = BookingPage(page, env_config["url"]).open()
        page.get_by_label(USERNAME, exact=True).first.fill(username)
        page.get_by_label(PASSWORD, exact=True).first.fill("wrong-password")
        screen.by("login").click()
        expect(screen.by("login-error")).to_be_visible()
        answers.append(screen.by("login-error").inner_text())
        expect(screen.by("app")).to_be_hidden()

    assert answers[0] == answers[1], f"the page tells an attacker which usernames exist: {answers}"


def test_every_field_has_a_label_a_screen_reader_can_read(shop, account):
    shop.open()
    for label in (USERNAME, PASSWORD, YOUR_NAME):
        expect(shop.page.get_by_label(label, exact=True).first).to_be_visible()

    shop.sign_in(account["username"], account["password"])
    for label in (BARBER, SERVICE, DATE):
        expect(shop.page.get_by_label(label, exact=True)).to_be_visible()
    # Booked, taken, cancelled: every outcome is announced, not only painted.
    expect(shop.page.get_by_role("status")).to_have_count(1)
