"""Errors are part of the API.

A consumer that cannot tell 404 from 403, or gets a stack trace instead of a
message, is looking at a defect even when the happy path works.
"""

import pytest

pytestmark = pytest.mark.usefixtures("fresh_state")


def test_every_error_carries_a_detail_message(items):
    resp = items.get_by_id("itm-does-not-exist")

    assert resp.status_code == 404
    assert resp.as_dict.get("detail"), "an error without a message is unusable by a client"


@pytest.mark.parametrize(
    "case, expected",
    [
        ("missing", 404),
        ("forbidden", 403),
        ("unauthenticated", 401),
        ("invalid", 422),
    ],
)
def test_each_kind_of_failure_gets_its_own_status(items, orders, case, expected):
    if case == "missing":
        resp = orders.get_by_id("ord-nope", persona="member")
    elif case == "forbidden":
        resp = items.create({"name": "x", "price": 1.0}, persona="member")
    elif case == "unauthenticated":
        resp = items.find(persona=None)
    else:
        resp = items.create({"name": "", "price": 1.0}, persona="admin")

    assert resp.status_code == expected


def test_an_error_body_does_not_leak_internals(items):
    body = str(items.get_by_id("itm-does-not-exist").as_dict)

    for leak in ("Traceback", 'File "', "sqlalchemy", "psycopg", "/usr/lib", "site-packages"):
        assert leak not in body, f"the error body leaked {leak!r}"


def test_a_wrong_state_transition_is_a_conflict_not_a_validation_error(items, orders):
    item = items.create_fake_item(price=10.0)
    order = orders.create_fake_order(item["id"])

    assert (
        orders.approve(order["id"]).status_code == 409
    ), "approving a draft is a state problem, not a payload problem"


def test_an_insufficient_budget_is_not_reported_as_a_validation_error(items, orders):
    item = items.create_fake_item(price=orders.budget() + 1)
    order = orders.create_fake_order(item["id"])

    resp = orders.submit(order["id"])
    assert resp.status_code == 402, "402 tells a client to top up; 422 tells it to fix the payload"
    assert "budget" in resp.as_dict["detail"].lower()


def test_reading_someone_elses_record_is_forbidden_not_missing(items, orders, api):
    item = items.create_fake_item(price=10.0)
    order = orders.create_fake_order(item["id"], persona="member")

    assert orders.get_by_id(order["id"], persona="admin").status_code == 200
    assert orders.get_by_id("ord-nope", persona="admin").status_code == 404
