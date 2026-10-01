from __future__ import annotations

import secrets

from faker import Faker

from obj.base import Base

fake = Faker()


def new_device_address() -> str:
    """A client address of its own, sent as X-Forwarded-For: a different person's
    phone. The barbershop counts sign-ups and failed sign-ins by address, and
    everything a test does would otherwise come from 127.0.0.1 - a handful of runs
    and every test is refused. The server takes the header only from 127.0.0.1
    (uvicorn's FORWARDED_ALLOW_IPS), where the suites reach it from.

    IPv6's documentation range, 2001:db8::/32, never routed: 2**96 addresses. The
    first version drew from 198.18.0.0/15 - 130,000 - and a page test drew the very
    address a sign-in test had locked on purpose, and was refused. With hundreds of
    addresses drawn a run and a few locked at any moment, that is once in some
    hundreds of runs: rare, and a flaky test all the same."""
    return "2001:db8:" + ":".join(f"{secrets.randbelow(65536):x}" for _ in range(6))


class Customers(Base):
    """Sign-up is public, so a test can make as many customers as it needs -
    the product's own isolation, with no reset endpoint behind it."""

    resource = "customers"

    def build_signup_payload(
        self, username: str | None = None, password: str | None = None, display_name: str | None = None
    ) -> dict:
        return {
            "username": username or f"qa-{secrets.token_hex(5)}",
            "password": password or secrets.token_urlsafe(12),
            "display_name": display_name or fake.first_name(),
        }

    def create(self, data: dict, persona: str | None = None, headers: dict[str, str] | None = None):
        """A sign-up, from a device of its own unless the caller names one - one
        address may make only a few accounts an hour."""
        return super().create(
            data, persona=persona, headers={"X-Forwarded-For": new_device_address(), **(headers or {})}
        )

    def sign_up_as_persona(self, persona: str | None = None) -> str:
        """Sign up a new customer and log them in as a persona of their own."""
        payload = self.build_signup_payload()
        self.create(payload, persona=None).assert_ok(201)
        name = persona or f"customer-{payload['username']}"
        self.client.register_persona(name, payload["username"], payload["password"])
        return name
