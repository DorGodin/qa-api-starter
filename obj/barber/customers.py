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

    @staticmethod
    def new_phone() -> str:
        """A mobile number of the test's own: 05 and eight random digits."""
        return f"05{secrets.randbelow(10**8):08d}"

    def request_code(self, phone: str, full_name: str, address: str | None = None):
        return self.client.request(
            "POST",
            "/auth/otp",
            persona=None,
            json={"full_name": full_name, "phone": phone},
            headers={"X-Forwarded-For": address or new_device_address()},
        )

    def verify_code(self, phone: str, code: str):
        return self.client.request(
            "POST", "/auth/otp/verify", persona=None, json={"phone": phone, "code": code}
        )

    def sign_in_by_code(self, inbox, full_name: str | None = None, phone: str | None = None) -> dict:
        """Sign in the way a customer does now: a code by SMS, read from the fake
        provider's inbox. The first time opens the account. Registered as a
        persona of its own; the token is kept too, for a browser to resume with."""
        phone = phone or self.new_phone()
        full_name = full_name or f"{fake.first_name()} {fake.last_name()}"
        seen = inbox.last_id(phone)
        self.request_code(phone, full_name).assert_ok(202)
        token = (
            self.verify_code(phone, inbox.code_for(phone, after=seen)).assert_ok(200).as_dict["access_token"]
        )
        persona = f"customer-{phone}"
        self.client.register_persona_headers(persona, {"Authorization": f"Bearer {token}"})
        return {"name": full_name, "phone": phone, "persona": persona, "token": token}

    def sign_up_as_persona(self, persona: str | None = None) -> str:
        """Sign up a new customer and log them in as a persona of their own."""
        payload = self.build_signup_payload()
        self.create(payload, persona=None).assert_ok(201)
        name = persona or f"customer-{payload['username']}"
        self.client.register_persona(name, payload["username"], payload["password"])
        return name
