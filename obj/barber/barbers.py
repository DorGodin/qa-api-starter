from __future__ import annotations

import secrets
from datetime import date

from faker import Faker

from obj.base import Base
from obj.client import Response

fake = Faker()
WEEK = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class Barbers(Base):
    resource = "barbers"

    @staticmethod
    def build_hours(opening: str = "00:00", closing: str = "24:00") -> dict:
        """The same hours every day of the week. Around the clock by default, so a
        test never depends on the hour it happens to run at."""
        return {"hours": dict.fromkeys(WEEK, [opening, closing])}

    def build_barber_payload(self, username: str | None = None, password: str | None = None) -> dict:
        return {
            "username": username or f"qa-barber-{secrets.token_hex(5)}",
            "password": password or secrets.token_urlsafe(12),
            "display_name": fake.first_name(),
        }

    def create_fake_barber(
        self, opening: str = "00:00", closing: str = "24:00", persona: str = "owner"
    ) -> dict:
        """A barber of the caller's own, with known hours - the unit of isolation
        on a product that cannot be reset."""
        payload = self.build_barber_payload()
        barber = self.create(payload, persona=persona).assert_ok(201).as_dict
        self.set_hours(barber["id"], self.build_hours(opening, closing), persona=persona)
        return {**barber, "username": payload["username"], "password": payload["password"]}

    def set_hours(self, barber_id: str, hours: dict, persona: str = "owner") -> Response:
        return self.client.request("PUT", f"{self.path}/{barber_id}/hours", persona=persona, json=hours)

    def add_time_off(self, barber_id: str, day: date, persona: str = "owner") -> Response:
        return self.client.request(
            "POST", f"{self.path}/{barber_id}/time-off", persona=persona, json={"date": day.isoformat()}
        )

    def availability(self, barber_id: str, day: date, service_id: str, persona: str = "customer") -> Response:
        return self.client.request(
            "GET",
            f"{self.path}/{barber_id}/availability",
            persona=persona,
            params={"date": day.isoformat(), "service_id": service_id},
        )

    def slots(self, barber_id: str, day: date, service_id: str, persona: str = "customer") -> list[dict]:
        return self.availability(barber_id, day, service_id, persona).assert_ok(200).as_dict["slots"]

    def sign_in_as_persona(self, barber: dict) -> str:
        """Log a barber made by create_fake_barber in as a persona of their own."""
        name = f"barber-{barber['username']}"
        self.client.register_persona(name, barber["username"], barber["password"])
        return name
