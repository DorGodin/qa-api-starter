from __future__ import annotations

from faker import Faker

from utils.helpers import assert_not_prod

fake = Faker()


def seed_catalogue(items_api, count: int = 3, price: float | None = None) -> list[dict]:
    """Resolve-or-seed: returns `count` active items, creating only what is missing."""
    assert_not_prod("seed_catalogue")

    existing = items_api.find(params={"active": True, "limit": count}).content
    if len(existing) >= count:
        return existing[:count]

    created = list(existing)
    while len(created) < count:
        created.append(
            items_api.create_fake_item(price=price if price is not None else round(fake.pyfloat(min_value=5, max_value=80), 2))
        )
    return created
