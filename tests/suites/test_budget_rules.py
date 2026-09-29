import pytest

pytestmark = pytest.mark.usefixtures("fresh_state")


def test_an_order_equal_to_the_budget_is_allowed(items, orders):
    budget = orders.budget()
    item = items.create_fake_item(price=budget)
    order = orders.create_fake_order(item["id"])

    orders.submit(order["id"]).assert_ok(200)
    assert orders.budget() == pytest.approx(0.0), "spending the exact budget must be allowed"


def test_one_unit_over_the_budget_is_refused(items, orders):
    budget = orders.budget()
    item = items.create_fake_item(price=budget + 0.01)
    order = orders.create_fake_order(item["id"])

    assert orders.submit(order["id"]).status_code == 402
    assert orders.budget() == pytest.approx(budget)


def test_spending_accumulates_across_orders(items, orders):
    start = orders.budget()
    item = items.create_fake_item(price=50.0)

    for expected_spend in (50.0, 100.0, 150.0):
        order = orders.create_fake_order(item["id"])
        orders.submit(order["id"]).assert_ok(200)
        assert orders.budget() == pytest.approx(start - expected_spend, abs=0.01)


def test_a_refusal_leaves_the_budget_exactly_where_it_was(items, orders):
    cheap = items.create_fake_item(price=100.0)
    orders.submit(orders.create_fake_order(cheap["id"])["id"]).assert_ok(200)
    after_first = orders.budget()

    expensive = items.create_fake_item(price=after_first + 1)
    assert orders.submit(orders.create_fake_order(expensive["id"])["id"]).status_code == 402
    assert orders.budget() == pytest.approx(after_first), "a rejected order must not spend anything"


def test_quantity_multiplies_the_cost_against_the_budget(items, orders):
    start = orders.budget()
    item = items.create_fake_item(price=30.0)
    order = orders.create_fake_order(item["id"], quantity=4)

    assert order["total_amount"] == pytest.approx(120.0)
    orders.submit(order["id"]).assert_ok(200)
    assert orders.budget() == pytest.approx(start - 120.0)


def test_a_draft_does_not_reserve_anything(items, orders):
    start = orders.budget()
    item = items.create_fake_item(price=80.0)
    orders.create_fake_order(item["id"])

    assert orders.budget() == pytest.approx(start), "only submitting spends the budget"
