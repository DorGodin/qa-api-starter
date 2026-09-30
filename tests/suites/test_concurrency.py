"""Two requests at the same moment.

Most money bugs are not wrong arithmetic. They are the same correct arithmetic
running twice before either result is written back.
"""

import pytest

from utils.concurrency import at_once

pytestmark = pytest.mark.usefixtures("fresh_state")


def submit_twice(orders, order_id):
    return sorted(r.status_code for r in at_once([lambda: orders.submit(order_id)] * 2))


def test_submitting_the_same_order_twice_at_once_spends_once(items, orders):
    start = orders.budget()
    item = items.create_fake_item(price=100.0)
    order = orders.create_fake_order(item["id"])

    statuses = submit_twice(orders, order["id"])

    assert statuses == [200, 409], f"exactly one submit may win, got {statuses}"
    assert orders.budget() == pytest.approx(start - 100.0), "the budget was charged twice"


def test_two_orders_racing_cannot_overdraw_the_budget(items, orders):
    budget = orders.budget()
    item = items.create_fake_item(price=budget * 0.75)
    first = orders.create_fake_order(item["id"])
    second = orders.create_fake_order(item["id"])

    statuses = sorted(
        r.status_code for r in at_once([lambda o=o: orders.submit(o["id"]) for o in (first, second)])
    )

    assert statuses == [200, 402], f"only one of the two fits in the budget, got {statuses}"
    assert orders.budget() >= 0, "the budget went negative under concurrency"


def test_parallel_reads_stay_consistent(items, orders):
    item = items.create_fake_item(price=25.0)
    orders.create_fake_order(item["id"], quantity=2)

    bodies = at_once([lambda: orders.find({"expand": "lines"})] * 8)

    totals = {body.assert_ok(200).content[0]["total_amount"] for body in bodies}
    assert totals == {50.0}, f"concurrent reads disagreed: {totals}"


def test_creating_many_orders_at_once_creates_exactly_that_many(items, orders):
    item = items.create_fake_item(price=1.0)

    created = at_once([lambda: orders.create_fake_order(item["id"])] * 10)

    assert len({o["id"] for o in created}) == 10, "two orders were given the same id"
    assert orders.find().assert_ok(200).as_dict["total"] == 10
