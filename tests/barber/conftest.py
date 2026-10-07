"""Fixtures for the barbershop product. Collected only when ENV points at it.

The product has no reset, so nothing here resets. Each module gets barbers of its
own, created by the owner through the ordinary API, and each test signs up the
customers it needs. Two runs, or two suites, never book into each other.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pytest
import requests

from obj.barber import ApprovalRules, Barbers, Bookings, Courses, Customers, Push, PushInbox, Services
from obj.barber.customers import new_device_address
from obj.barber.sms_inbox import SmsInbox


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
def sms_inbox(env_config):
    """The fake SMS provider the barbershop sends its codes to (utils/fake_sms.py),
    started for the run when nothing answers on its port, and stopped after."""
    url = env_config.get("sms_inbox")
    if not url:
        raise KeyError(f"ENV={env_config['env']} has no sms_inbox; the barbershop signs in by SMS code")
    try:
        requests.get(f"{url}/health", timeout=1).raise_for_status()
        yield SmsInbox(url)
        return
    except requests.RequestException:
        pass
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "utils.fake_sms",
            "--port",
            str(urlparse(url).port),
            "--host",
            env_config.get("sms_inbox_bind", "127.0.0.1"),
        ],
        cwd=Path(__file__).resolve().parents[2],
    )
    try:
        for _ in range(50):
            try:
                if requests.get(f"{url}/health", timeout=1).ok:
                    break
            except requests.RequestException:
                time.sleep(0.1)
        else:
            raise RuntimeError(f"the fake SMS provider did not start on {url}")
        yield SmsInbox(url)
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="session")
def push(api, artifact_log):
    return Push(api, log=artifact_log)


@pytest.fixture(scope="session")
def push_inbox(env_config):
    """The fake push service the barbershop posts its news to (utils/fake_push.py), started for the run
    when nothing answers on its port, and stopped after. An environment without one - the Docker image,
    which cannot reach it - skips what needs it."""
    url = env_config.get("push_inbox")
    if not url:
        pytest.skip(f"ENV={env_config['env']} has no push_inbox")
    try:
        requests.get(f"{url}/health", timeout=1).raise_for_status()
        yield PushInbox(url)
        return
    except requests.RequestException:
        pass
    proc = subprocess.Popen(
        [sys.executable, "-m", "utils.fake_push", "--port", str(urlparse(url).port)],
        cwd=Path(__file__).resolve().parents[2],
    )
    try:
        for _ in range(50):
            try:
                if requests.get(f"{url}/health", timeout=1).ok:
                    break
            except requests.RequestException:
                time.sleep(0.1)
        else:
            raise RuntimeError(f"the fake push service did not start on {url}")
        yield PushInbox(url)
    finally:
        proc.terminate()
        proc.wait(timeout=10)


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


@pytest.fixture
def courses(api, artifact_log):
    """The shop's courses are shared by everyone who signs in, and the product cannot be
    reset: what a test makes it withdraws, so a customer in another test never reads it."""
    made = []
    kept = Courses(api, log=artifact_log)
    create = kept.create_fake_course

    def tracked(**kwargs):
        course = create(**kwargs)
        made.append(course["id"])
        return course

    kept.create_fake_course = tracked
    yield kept
    for course_id in made:
        kept.withdraw(course_id)


@pytest.fixture
def approval_rules(api, artifact_log):
    """When a booking waits for its barber is one setting for the whole shop, and the
    product cannot be reset: what a test changes it puts back."""
    rules = ApprovalRules(api, log=artifact_log)
    before = rules.current()
    yield rules
    rules.save(before).assert_ok(200)


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
def new_customer(customers, sms_inbox):
    """A customer of the test's own, signed in by an SMS code as a customer is:
    call it once per customer needed. Returns the persona's name."""
    return lambda: customers.sign_in_by_code(sms_inbox)["persona"]
