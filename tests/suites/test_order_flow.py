import pytest

pytestmark = pytest.mark.usefixtures("api")


def assert_summary_math(order: dict) -> None:
    for line in order["lines"]:
        assert line["line_total"] == pytest.approx(line["unit_price"] * line["quantity"], abs=0.01), line
    assert order["total_amount"] == pytest.approx(
        sum(line["line_total"] for line in order["lines"]), abs=0.01
    )


@pytest.mark.dependency()
def test_member_creates_draft_order(items, orders, ctx):
    item = items.create_fake_item(price=25.0)
    order = orders.create_fake_order(item["id"], quantity=3)

    assert order["status"] == "draft"
    assert order["total_amount"] == pytest.approx(75.0)
    assert_summary_math(order)
    ctx["order_id"] = order["id"]


@pytest.mark.dependency(depends=["test_member_creates_draft_order"])
def test_submitting_draws_from_budget(orders, ctx):
    before = orders.budget()
    order = orders.submit(ctx["order_id"]).assert_ok(200).as_dict

    assert order["status"] == "submitted"
    assert orders.budget() == pytest.approx(before - order["total_amount"], abs=0.01)


@pytest.mark.dependency(depends=["test_submitting_draws_from_budget"])
def test_admin_approves_submitted_order(orders, ctx):
    order = orders.approve(ctx["order_id"]).assert_ok(200).as_dict
    assert order["status"] == "approved"


def test_member_cannot_approve(items, orders):
    item = items.create_fake_item(price=10.0)
    order = orders.create_fake_order(item["id"])
    orders.submit(order["id"]).assert_ok(200)

    assert orders.approve(order["id"], persona="member").status_code == 403


def test_order_over_budget_is_rejected(items, orders):
    before = orders.budget()
    item = items.create_fake_item(price=before + 100)
    order = orders.create_fake_order(item["id"])

    assert orders.submit(order["id"]).status_code == 402
    assert orders.budget() == pytest.approx(before), "a rejected submit must not touch the budget"


def test_double_submit_is_a_conflict(items, orders):
    item = items.create_fake_item(price=15.0)
    order = orders.create_fake_order(item["id"])
    orders.submit(order["id"]).assert_ok(200)

    assert orders.submit(order["id"]).status_code == 409


def test_lines_are_hidden_unless_expanded(items, orders):
    item = items.create_fake_item(price=12.5)
    order = orders.create_fake_order(item["id"], quantity=2)

    plain = orders.get_by_id(order["id"], persona="member").assert_ok(200).as_dict
    assert plain["lines"] == [] and plain["line_count"] == 1

    expanded = (
        orders.get_by_id(order["id"], params={"expand": "lines"}, persona="member").assert_ok(200).as_dict
    )
    assert_summary_math(expanded)


def test_admin_sees_orders_that_members_cannot(items, orders):
    item = items.create_fake_item(price=20.0)
    order = orders.create_fake_order(item["id"])

    assert orders.get_by_id(order["id"], persona="admin").status_code == 200
    member_view = orders.find(params={"status": "draft"}, persona="member").assert_ok(200)
    assert all(row["owner"] == "member" for row in member_view.content)
