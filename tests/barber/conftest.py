"""Fixtures for the barbershop product. Collected only when ENV points at it.

The product has no reset, so nothing here resets. Each module gets barbers of its
own, created by the owner through the ordinary API, and each test signs up the
customers it needs. Two runs, or two suites, never book into each other.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

import pytest

from obj.barber import Barbers, Bookings, Customers, Services
from obj.barber.customers import new_device_address


@pytest.fixture
def fresh_address():
    """A client address the test names itself, for a test about the limits that
    count by address - sign-ins and sign-ups. Why, and from where: see
    obj.barber.customers.new_device_address."""

    return new_device_address


@pytest.fixture(scope="session")
def shop_tz(env_config) -> ZoneInfo:
    if "shop_tz" not in env_config:
        raise KeyError(
            f"ENV={env_config['env']} has no shop_tz; the barbershop suites need the shop's time zone"
        )
    return ZoneInfo(env_config["shop_tz"])


@pytest.fixture(scope="session")
def customers(api, artifact_log):
    return Customers(api, log=artifact_log)


@pytest.fixture(scope="session")
def services(api, artifact_log):
    return Services(api, log=artifact_log)


@pytest.fixture(scope="session")
def barbers(api, artifact_log):
    return Barbers(api, log=artifact_log)


@pytest.fixture(scope="session")
def bookings(api, artifact_log):
    return Bookings(api, log=artifact_log)


@pytest.fixture(scope="module")
def barber(barbers) -> dict:
    """This module's own barber, working around the clock."""
    return barbers.create_fake_barber()


@pytest.fixture(scope="module")
def haircut(services) -> dict:
    """This module's own 30 minute service. Its own, so a test that changes a
    price never changes another module's arithmetic."""
    return services.create_fake_service(duration_minutes=30, price_minor=8000)


@pytest.fixture(scope="module")
def trim(services) -> dict:
    return services.create_fake_service(duration_minutes=15, price_minor=4000)


@pytest.fixture
def new_customer(customers):
    """A customer of the test's own, logged in: call it once per customer needed."""
    return customers.sign_up_as_persona
