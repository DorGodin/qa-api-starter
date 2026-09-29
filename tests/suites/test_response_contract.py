"""Shape, not just status.

A field that silently disappears breaks every consumer, and a suite that only
asserts status codes will not notice.
"""
import pytest

pytestmark = pytest.mark.usefixtures("fresh_state")

ITEM_FIELDS = {"id": str, "name": str, "price": float, "active": bool}
ORDER_FIELDS = {"id": str, "owner": str, "status": str, "total_amount": float, "line_count": int}
LINE_FIELDS = {"item_id": str, "name": str, "unit_price": float, "quantity": int, "line_total": float}


def assert_shape(payload: dict, expected: dict[str, type], label: str) -> None:
    missing = [name for name in expected if name not in payload]
    assert not missing, f"{label} is missing {missing}"

    wrong = {
        name: type(payload[name]).__name__
        for name, kind in expected.items()
        if not isinstance(payload[name], kind) and not (kind is float and isinstance(payload[name], int))
    }
    assert not wrong, f"{label} has the wrong type for {wrong}"


def test_an_item_keeps_its_shape(items):
    assert_shape(items.create_fake_item(), ITEM_FIELDS, "item")


def test_a_listing_always_carries_total_and_content(items):
    items.create_fake_item()
    body = items.find().assert_ok(200).as_dict

    assert set(body) >= {"total", "content"}
    assert isinstance(body["total"], int)
    assert isinstance(body["content"], list)


def test_an_order_keeps_its_shape_and_its_lines(items, orders):
    item = items.create_fake_item(price=20.0)
    order = orders.create_fake_order(item["id"], quantity=2)

    assert_shape(order, ORDER_FIELDS, "order")
    assert order["lines"], "the create response returns its lines"
    for line in order["lines"]:
        assert_shape(line, LINE_FIELDS, "order line")


def test_no_field_comes_back_null(items, orders):
    item = items.create_fake_item()
    order = orders.create_fake_order(item["id"])

    for payload, label in ((item, "item"), (order, "order")):
        nulls = [name for name, value in payload.items() if value is None and name != "note"]
        assert not nulls, f"{label} returned null for {nulls}"


def test_money_is_never_returned_as_a_string(items, orders):
    item = items.create_fake_item(price=19.99)
    order = orders.create_fake_order(item["id"], quantity=3)

    assert isinstance(item["price"], (int, float))
    assert isinstance(order["total_amount"], (int, float))
    assert order["total_amount"] == pytest.approx(59.97)


def test_money_is_rounded_to_two_decimals(items, orders):
    item = items.create_fake_item(price=0.07)
    order = orders.create_fake_order(item["id"], quantity=3)

    assert order["total_amount"] == pytest.approx(0.21), "0.07 * 3 must not leak float noise"
    assert round(order["total_amount"], 2) == order["total_amount"]


def test_a_collapsed_order_reports_its_line_count_honestly(items, orders):
    item = items.create_fake_item(price=5.0)
    created = orders.create_fake_order(item["id"], quantity=1)

    collapsed = orders.get_by_id(created["id"], persona="member").assert_ok(200).as_dict
    assert collapsed["lines"] == []
    assert collapsed["line_count"] == 1, "hiding the lines must not hide that there are any"
