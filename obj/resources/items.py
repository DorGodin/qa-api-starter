from __future__ import annotations

from faker import Faker

from obj.base import Base

fake = Faker()


class Items(Base):
    resource = "items"

    def build_item_payload(self, name: str | None = None, price: float | None = None, active: bool = True) -> dict:
        return {
            "name": name or f"{fake.word().capitalize()} {fake.word()}",
            "price": price if price is not None else round(fake.pyfloat(min_value=5, max_value=80), 2),
            "active": active,
        }

    def create_fake_item(self, **kwargs):
        resp = self.create(self.build_item_payload(**kwargs), persona="admin")
        return resp.assert_ok(201).as_dict
