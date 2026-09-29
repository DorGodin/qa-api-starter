"""Two requests at the same moment.

Most money bugs are not wrong arithmetic. They are the same correct arithmetic
running twice before either result is written back.
"""
from concurrent.futures import ThreadPoolExecutor

import pytest

pytestmark = pytest.mark.usefixtures("fresh_state")


def submit_twice(orders, order_id):
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(orders.submit, order_id) for _ in range(2)]
        return sorted(f.result().status_code for f in futures)


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

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(orders.submit, o["id"]) for o in (first, second)]
        statuses = sorted(f.result().status_code for f in futures)

    assert statuses == [200, 402], f"only one of the two fits in the budget, got {statuses}"
    assert orders.budget() >= 0, "the budget went negative under concurrency"


def test_parallel_reads_stay_consistent(items, orders):
    item = items.create_fake_item(price=25.0)
    orders.create_fake_order(item["id"], quantity=2)

    with ThreadPoolExecutor(max_workers=8) as pool:
        bodies = [f.result() for f in [pool.submit(orders.find, {"expand": "lines"}) for _ in range(8)]]

    totals = {body.assert_ok(200).content[0]["total_amount"] for body in bodies}
    assert totals == {50.0}, f"concurrent reads disagreed: {totals}"


def test_creating_many_orders_at_once_creates_exactly_that_many(items, orders):
    item = items.create_fake_item(price=1.0)

    with ThreadPoolExecutor(max_workers=10) as pool:
        created = [f.result() for f in [pool.submit(orders.create_fake_order, item["id"]) for _ in range(10)]]

    assert len({o["id"] for o in created}) == 10, "two orders were given the same id"
    assert orders.find().assert_ok(200).as_dict["total"] == 10
