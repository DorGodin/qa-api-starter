from __future__ import annotations

import secrets

from obj.base import Base


class Services(Base):
    resource = "services"

    def build_service_payload(
        self,
        name: str | None = None,
        duration_minutes: int = 30,
        price_minor: int = 8000,
        currency: str = "ILS",
        requires_approval: bool = False,
        any_time: bool = False,
    ) -> dict:
        return {
            "name": name or f"QA service {secrets.token_hex(4)}",
            "duration_minutes": duration_minutes,
            "price_minor": price_minor,
            "currency": currency,
            "requires_approval": requires_approval,
            "any_time": any_time,
        }

    def create_fake_service(self, persona: str = "owner", **kwargs) -> dict:
        return self.create(self.build_service_payload(**kwargs), persona=persona).assert_ok(201).as_dict

    def set_price(self, service_id: str, price_minor: int, persona: str = "owner") -> dict:
        return (
            self.update_by_id(service_id, {"price_minor": price_minor}, persona=persona)
            .assert_ok(200)
            .as_dict
        )

    def deactivate(self, service_id: str, persona: str = "owner") -> dict:
        return self.update_by_id(service_id, {"active": False}, persona=persona).assert_ok(200).as_dict
