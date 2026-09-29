"""One test, ten scenarios, none of them in Python.

Adding a pricing case means adding a line to data/scenarios/order_pricing.csv.
"""
import pytest

from utils.scenarios import as_float, load_csv

pytestmark = pytest.mark.usefixtures("fresh_state")

SCENARIOS = load_csv("order_pricing.csv")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["case"].replace(" ", "-") for s in SCENARIOS])
def test_order_pricing(items, orders, scenario):
    price = as_float(scenario["unit_price"])
    quantity = int(scenario["quantity"])
    expected_status = int(scenario["expected_status"])

    item = items.create_fake_item(price=price)
    resp = orders.create(
        orders.build_order_payload([orders.build_line(item["id"], quantity)]),
        persona="member",
    )

    assert resp.status_code == expected_status, f"{scenario['case']}: {resp.as_dict}"

    expected_total = as_float(scenario["expected_total"])
    if expected_total is not None:
        assert resp.as_dict["total_amount"] == pytest.approx(expected_total, abs=0.001), scenario["case"]


def test_the_scenario_file_is_not_silently_empty():
    assert len(SCENARIOS) >= 5, "a shrunken scenario file means lost coverage that nothing else reports"
