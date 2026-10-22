"""The barbershop's booking page, driven by a real browser.

Collected only with --ui, and only when ENV's product is the barbershop. The
API fixtures are imported, not copied: a barber made for a UI test is made
exactly the way the API suites make one.
"""

from __future__ import annotations

import secrets

import pytest
from playwright.sync_api import expect

from obj.barber.booking_page import BookingPage, OwnerScreen, a_device
from obj.barber.customers import new_device_address
from tests.barber.conftest import (  # noqa: F401
    approval_rules,
    barbers,
    bookings,
    bookings_ahead_limit,
    courses,
    customers,
    fresh_address,
    new_customer,
    products,
    push,
    push_inbox,
    services,
    shop_tz,
    sms_inbox,
)


@pytest.fixture(scope="module")
def ui_barber(barbers):  # noqa: F811
    return barbers.create_fake_barber()


@pytest.fixture(scope="module")
def ui_haircut(services):  # noqa: F811
    return services.create_fake_service(duration_minutes=30, price_minor=8000)


@pytest.fixture
def account(customers, sms_inbox):  # noqa: F811
    """A customer of this test's own, signed in by an SMS code through the API -
    a persona, so the test can check through the API what the page did, and a
    token the page resumes with."""
    signed_in = customers.sign_in_by_code(sms_inbox)
    return {**signed_in, "display_name": signed_in["name"]}


@pytest.fixture
def shop(page, env_config) -> BookingPage:
    return BookingPage(page, env_config["url"])


@pytest.fixture
def signed_in(shop, account) -> BookingPage:
    return shop.sign_in_as(account)


@pytest.fixture
def owner_screen(page, env_config, credentials) -> OwnerScreen:
    """Signs in on first use, so a test can create what it needs first - the page
    reads its list of barbers once, at sign-in."""
    screen = OwnerScreen(page, env_config["url"])

    def _open() -> OwnerScreen:
        username, password = credentials("owner")
        return screen.sign_in(username, password)

    return _open


@pytest.fixture(autouse=True)
def every_browser_is_its_own_device(request):
    """The page a test gets comes from an address of its own, as a different
    person's phone would. The barbershop limits sign-ups and failed sign-ins by
    address; from one shared 127.0.0.1 a run's page tests would refuse each other.
    The contexts tests open themselves do the same (obj.barber.booking_page.a_device)."""
    if "page" in request.fixturenames:
        request.getfixturevalue("context").set_extra_http_headers({"X-Forwarded-For": new_device_address()})


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, device):
    """A desktop-sized window, so a recording shows the whole booking screen -
    the choice on the left and the list on the right - without scrolling.

    Unless --device names a phone: then the whole suite runs on that phone's
    screen, touch and user agent, and forcing a desktop window over it would
    quietly turn the mobile run back into a desktop one."""
    # Still, as for a person who asked for less motion (see a_device); test_fresh_look asks for it.
    # And without the page's worker: in WebKit the page's requests then go through it, and page.route - every test
    # that holds an answer back - sees none of them. The worker has its own tests (test_offline_page), which allow it.
    still = {**browser_context_args, "reduced_motion": "reduce", "service_workers": "block"}
    if device:
        return {**still, "record_video_size": browser_context_args["viewport"]}
    size = {"width": 1100, "height": 760}
    return {**still, "viewport": size, "record_video_size": size}


# The journeys' people: each a browser of their own, and an account opened on the screen.
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


@pytest.fixture
def signed_up(sms_inbox):  # noqa: F811
    """A person opening their account on the screen: name, phone, the code from
    the SMS - the first sign-in opens it."""

    def _sign_up(screen: BookingPage, account: dict, navigate: bool = True) -> BookingPage:
        screen.sign_in_by_code(account["name"], account["phone"], sms_inbox, navigate=navigate)
        expect(screen.by("app")).to_be_visible()
        screen.settled()
        return screen

    return _sign_up


@pytest.fixture
def diary_of(person, sms_inbox):  # noqa: F811
    """A barber opening their diary on a phone of their own: the mobile the owner typed for
    them, and the code sent to it - the customers' own sign-in, and what opens is the diary."""

    def _open(barber: dict) -> BookingPage:
        screen = person()
        screen.sign_in_by_code(barber["name"], barber["phone"], sms_inbox)
        expect(screen.by("app")).to_be_visible()
        return screen

    return _open
