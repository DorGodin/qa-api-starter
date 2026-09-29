from __future__ import annotations

from faker import Faker

from obj.base import Base

fake = Faker()


class Orders(Base):
    resource = "orders"

    def build_line(self, item_id: str, quantity: int = 1) -> dict:
        return {"item_id": item_id, "quantity": quantity}

    def build_order_payload(self, lines: list[dict], note: str | None = None) -> dict:
        return {"lines": lines, "note": note if note is not None else fake.sentence(nb_words=6)}

    def create_fake_order(self, item_id: str, quantity: int = 1, persona: str = "member", **kwargs):
        payload = self.build_order_payload([self.build_line(item_id, quantity)], **kwargs)
        return self.create(payload, persona=persona).assert_ok(201).as_dict

    def submit(self, order_id: str, persona: str = "member"):
        return self.client.request("POST", f"{self.path}/{order_id}/submit", persona=persona)

    def approve(self, order_id: str, persona: str = "admin"):
        return self.client.request("POST", f"{self.path}/{order_id}/approve", persona=persona)

    def budget(self, persona: str = "member") -> float:
        resp = self.client.request("GET", "/me/budget", persona=persona).assert_ok(200)
        return resp.as_dict["budget"]
