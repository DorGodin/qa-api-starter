"""Opt-in: `pytest --edge-cases`. Broken payloads go through obj.create directly."""

import pytest


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"name": "", "price": 10}, 422),
        ({"name": "ok", "price": 0}, 422),
        ({"name": "ok", "price": -5}, 422),
        ({"name": "ok"}, 422),
        ({"price": 10}, 422),
    ],
    ids=["empty-name", "zero-price", "negative-price", "no-price", "no-name"],
)
def test_item_payload_validation(items, payload, expected):
    assert items.create(payload, persona="admin").status_code == expected


@pytest.mark.parametrize("quantity", [0, -1, 100])
def test_order_quantity_bounds(items, orders, quantity):
    item = items.create_fake_item(price=10.0)
    payload = {"lines": [{"item_id": item["id"], "quantity": quantity}]}
    assert orders.create(payload, persona="member").status_code == 422


def test_order_with_unknown_item(orders):
    assert (
        orders.create(
            {"lines": [{"item_id": "itm-does-not-exist", "quantity": 1}]}, persona="member"
        ).status_code
        == 422
    )


def test_order_with_inactive_item(items, orders):
    item = items.create_fake_item(price=10.0, active=False)
    assert (
        orders.create({"lines": [{"item_id": item["id"], "quantity": 1}]}, persona="member").status_code
        == 422
    )


def test_requests_without_a_token_are_rejected(items):
    assert items.find(persona=None).status_code == 401
