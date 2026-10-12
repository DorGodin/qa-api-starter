from __future__ import annotations

import base64
import secrets

from obj.base import Base
from obj.client import Response


class Products(Base):
    """The shop's shelf, and what a customer asked to be kept for a booking."""

    resource = "products"

    def build_product_payload(
        self, name: str | None = None, line: str = "100 מ״ל", price_minor: int | None = 6500
    ) -> dict:
        return {"name": name or f"מוצר QA {secrets.token_hex(3)}", "line": line, "price_minor": price_minor}

    def create_fake_product(self, persona: str = "owner", **kwargs) -> dict:
        return self.create(self.build_product_payload(**kwargs), persona=persona).assert_ok(201).as_dict

    def withdraw(self, product_id: str, persona: str = "owner") -> dict:
        return self.update_by_id(product_id, {"active": False}, persona=persona).assert_ok(200).as_dict

    def run_out(self, product_id: str, persona: str = "owner") -> dict:
        return self.update_by_id(product_id, {"in_stock": False}, persona=persona).assert_ok(200).as_dict

    def set_image(self, product_id: str, raw: bytes, persona: str = "owner") -> Response:
        body = {"data": base64.b64encode(raw).decode()}
        return self.client.request("PUT", f"{self.path}/{product_id}/image", persona=persona, json=body)

    def remove_image(self, product_id: str, persona: str = "owner") -> Response:
        return self.client.request("DELETE", f"{self.path}/{product_id}/image", persona=persona)

    def listing(self, persona: str) -> list[dict]:
        return self.find(persona=persona).assert_ok(200).as_dict["content"]

    def one(self, product_id: str, persona: str = "owner") -> dict:
        return next(p for p in self.listing(persona) if p["id"] == product_id)

    def keep(self, booking_id: str, product_id: str, persona: str) -> Response:
        """Ask the shop to keep the product for the booking."""
        return self.client.request("PUT", f"/bookings/{booking_id}/products/{product_id}", persona=persona)

    def release(self, booking_id: str, product_id: str, persona: str) -> Response:
        return self.client.request("DELETE", f"/bookings/{booking_id}/products/{product_id}", persona=persona)
