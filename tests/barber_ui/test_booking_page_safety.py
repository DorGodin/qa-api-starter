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


def test_a_wrong_password_and_an_unknown_user_look_the_same(page, env_config, credentials, fresh_address):
    owner, _ = credentials("owner")
    page.set_extra_http_headers({"X-Forwarded-For": fresh_address()})
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


def test_too_many_wrong_passwords_are_refused_in_hebrew_with_how_long_to_wait(shop, account, fresh_address):
    shop.page.set_extra_http_headers({"X-Forwarded-For": fresh_address()})
    shop.open()
    for password in ["not-the-password"] * 5 + [account["password"]]:
        shop.page.get_by_label(USERNAME, exact=True).first.fill(account["username"])
        shop.page.get_by_label(PASSWORD, exact=True).first.fill(password)
        with shop.page.expect_response(lambda r: "/auth/token" in r.url):
            shop.by("login").click()

    error = shop.text(shop.by("login-error"))
    assert "יותר מדי ניסיונות" in error and "דקות" in error, error
    expect(shop.by("app")).to_be_hidden()


WATCH_POLICY = """
window.__violations = [];
document.addEventListener("securitypolicyviolation", (e) => window.__violations.push(`${e.violatedDirective} ${e.blockedURI}`));
"""


def test_a_whole_booking_and_the_owners_screen_run_without_a_single_policy_violation(
    page, env_config, account, credentials, ui_barber, ui_haircut, shop_tz
):
    page.add_init_script(WATCH_POLICY)
    shop = BookingPage(page, env_config["url"]).sign_in(account["username"], account["password"])
    shop.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 3)).pick("12:00").book()
    expect(shop.row_at("12:00")).to_be_visible()
    shop.by("logout").click()
    shop.sign_in(*credentials("owner"), navigate=False)
    expect(shop.by("owner")).to_be_visible()

    assert page.evaluate("window.__violations") == [], "the policy blocks part of the page itself"


def test_a_script_that_gets_past_the_escaping_is_still_not_run(page, env_config, account):
    page.add_init_script(WATCH_POLICY)
    BookingPage(page, env_config["url"]).sign_in(account["username"], account["password"])

    page.evaluate(
        """() => {
            document.body.insertAdjacentHTML("beforeend", '<img src="data:," onerror="window.__ran = true">');
            const script = document.createElement("script");
            script.textContent = "window.__ran = true";
            document.body.append(script);
        }"""
    )
    page.wait_for_function("window.__violations.length >= 2")

    assert page.evaluate("window.__ran") is None, "injected code ran, and could read the sign-in"
    assert all(v.startswith("script-src") for v in page.evaluate("window.__violations"))


def test_signing_out_on_the_page_ends_the_sign_in_on_the_server_too(shop, account, api):
    shop.sign_in(account["username"], account["password"])
    token = shop.page.evaluate("() => sessionStorage.getItem('barber.session')")

    with shop.page.expect_response(lambda r: "/auth/logout" in r.url and r.status == 204):
        shop.by("logout").click()

    stolen = {"Authorization": f"Bearer {token}"}
    assert (
        api.request("GET", "/me", persona=None, headers=stolen).status_code == 401
    ), "a copy taken before the sign-out still works"


def test_signing_out_with_no_connection_still_signs_this_device_out(shop, account):
    shop.sign_in(account["username"], account["password"])
    shop.page.route("**/auth/logout", lambda route: route.abort())

    shop.by("logout").click()
    shop.reload()

    expect(shop.by("login-form")).to_be_visible()
    expect(shop.by("app")).to_be_hidden()


def test_too_many_accounts_from_one_device_are_refused_in_hebrew_with_how_long_to_wait(
    shop, customers, fresh_address
):
    device = fresh_address()
    shop.page.set_extra_http_headers({"X-Forwarded-For": device})
    for _ in range(5):
        customers.create(customers.build_signup_payload(), headers={"X-Forwarded-For": device}).assert_ok(201)
    payload = customers.build_signup_payload()

    shop.sign_up(payload["display_name"], payload["username"], payload["password"])

    expect(shop.by("signup-error")).to_be_visible()
    error = shop.text(shop.by("signup-error"))
    assert "יותר מדי חשבונות" in error and "דקות" in error, error
    expect(shop.by("app")).to_be_hidden()
