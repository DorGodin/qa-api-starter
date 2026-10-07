from __future__ import annotations

from datetime import datetime

from faker import Faker

from obj.base import Base
from obj.client import Response
from utils.helpers import to_iso

fake = Faker()


class Bookings(Base):
    resource = "bookings"

    @staticmethod
    def build_booking_payload(barber_id: str, service_id: str, start: datetime | str) -> dict:
        return {
            "barber_id": barber_id,
            "service_id": service_id,
            "start": start if isinstance(start, str) else to_iso(start),
        }

    def book(
        self,
        barber_id: str,
        service_id: str,
        start: datetime | str,
        persona: str,
        idempotency_key: str | None = None,
    ) -> Response:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self.client.request(
            "POST",
            self.path,
            persona=persona,
            json=self.build_booking_payload(barber_id, service_id, start),
            headers=headers,
        )

    def book_guest(
        self,
        barber_id: str,
        service_id: str,
        start: datetime | str,
        guest_name: str | None = None,
        persona: str = "owner",
    ) -> Response:
        """The owner books, by name, someone with no account."""
        name = guest_name if guest_name is not None else fake.first_name()
        payload = {**self.build_booking_payload(barber_id, service_id, start), "guest_name": name}
        return self.client.request("POST", f"{self.path}/guest", persona=persona, json=payload)

    def create_booking(self, barber_id: str, service_id: str, start: datetime | str, persona: str) -> dict:
        resp = self.book(barber_id, service_id, start, persona=persona).assert_ok(201)
        if self.log is not None:
            self.log.record(self.resource, resp.as_dict, persona)
        return resp.as_dict

    @staticmethod
    def build_move_payload(start: datetime | str) -> dict:
        return {"start": start if isinstance(start, str) else to_iso(start)}

    def move(self, booking_id: str, start: datetime | str, persona: str) -> Response:
        """The same booking at another time - same barber, service and price."""
        return self.client.request(
            "POST", f"{self.path}/{booking_id}/move", persona=persona, json=self.build_move_payload(start)
        )

    def approve(self, booking_id: str, persona: str) -> Response:
        return self.client.request("POST", f"{self.path}/{booking_id}/approve", persona=persona)

    def decline(self, booking_id: str, persona: str) -> Response:
        return self.client.request("POST", f"{self.path}/{booking_id}/decline", persona=persona)

    def book_group(self, barber_id: str, start: datetime | str, people: list[dict], persona: str) -> Response:
        """The customer's own booking and someone else's, back to back with one barber."""
        payload = {
            "barber_id": barber_id,
            "start": start if isinstance(start, str) else to_iso(start),
            "people": people,
        }
        return self.client.request("POST", f"{self.path}/group", persona=persona, json=payload)

    def create_group(
        self, barber_id: str, start: datetime | str, people: list[dict], persona: str
    ) -> list[dict]:
        return self.book_group(barber_id, start, people, persona=persona).assert_ok(201).as_dict["bookings"]

    def book_group(self, barber_id: str, start: datetime | str, people: list[dict], persona: str) -> Response:
        """The customer's own booking and someone else's, back to back with one barber."""
        payload = {
            "barber_id": barber_id,
            "start": start if isinstance(start, str) else to_iso(start),
            "people": people,
        }
        return self.client.request("POST", f"{self.path}/group", persona=persona, json=payload)

    def create_group(
        self, barber_id: str, start: datetime | str, people: list[dict], persona: str
    ) -> list[dict]:
        return self.book_group(barber_id, start, people, persona=persona).assert_ok(201).as_dict["bookings"]

    def review(self, booking_id: str, persona: str, stars: int = 5, text: str | None = None) -> Response:
        body = {"stars": stars, **({"text": text} if text is not None else {})}
        return self.client.request("POST", f"{self.path}/{booking_id}/review", persona=persona, json=body)

    def review_words(self, booking_id: str, text: str, persona: str) -> Response:
        return self.client.request(
            "PATCH", f"{self.path}/{booking_id}/review", persona=persona, json={"text": text}
        )

    def cancel(self, booking_id: str, persona: str) -> Response:
        return self.client.request("POST", f"{self.path}/{booking_id}/cancel", persona=persona)

    def listing(self, persona: str, **params) -> dict:
        return self.find(params=params or None, persona=persona).assert_ok(200).as_dict
