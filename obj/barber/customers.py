from __future__ import annotations

import secrets

from faker import Faker

from obj.base import Base

fake = Faker()


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

    def sign_up_as_persona(self, persona: str | None = None) -> str:
        """Sign up a new customer and log them in as a persona of their own."""
        payload = self.build_signup_payload()
        self.create(payload, persona=None).assert_ok(201)
        name = persona or f"customer-{payload['username']}"
        self.client.register_persona(name, payload["username"], payload["password"])
        return name
