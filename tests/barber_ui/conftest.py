"""The barbershop's booking page, driven by a real browser.

Collected only with --ui, and only when ENV's product is the barbershop. The
API fixtures are imported, not copied: a barber made for a UI test is made
exactly the way the API suites make one.
"""

from __future__ import annotations

import pytest

from obj.barber.booking_page import BookingPage
from tests.barber.conftest import barbers, bookings, customers, services, shop_tz  # noqa: F401


@pytest.fixture(scope="module")
def ui_barber(barbers):  # noqa: F811
    return barbers.create_fake_barber()


@pytest.fixture(scope="module")
def ui_haircut(services):  # noqa: F811
    return services.create_fake_service(duration_minutes=30, price_minor=8000)


@pytest.fixture
def account(customers):  # noqa: F811
    """A customer of this test's own, created through the API and also logged in
    as a persona, so the test can check through the API what the page did."""
    payload = customers.build_signup_payload()
    customers.create(payload, persona=None).assert_ok(201)
    persona = f"customer-{payload['username']}"
    customers.client.register_persona(persona, payload["username"], payload["password"])
    return {**payload, "persona": persona}


@pytest.fixture
def shop(page, env_config) -> BookingPage:
    return BookingPage(page, env_config["url"])


@pytest.fixture
def signed_in(shop, account) -> BookingPage:
    return shop.sign_in(account["username"], account["password"])


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """A desktop-sized window, so a recording shows the whole booking screen -
    the choice on the left and the list on the right - without scrolling."""
    size = {"width": 1100, "height": 760}
    return {**browser_context_args, "viewport": size, "record_video_size": size}
