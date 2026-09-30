"""The spec is a contract. Check the product against its own document.

A field that changes type, or a response that stops matching what the API
advertises, breaks every generated client without breaking a single assertion in
a hand-written test.
"""

import pytest

from utils.openapi import documented_operations, load_spec, validate

pytestmark = pytest.mark.usefixtures("fresh_state")


@pytest.fixture(scope="session")
def spec(api):
    return load_spec(api.base_url)


def test_the_document_is_published_and_describes_the_product(spec):
    assert spec["openapi"].startswith("3."), spec["openapi"]
    assert spec["info"]["title"]
    assert spec["paths"], "the API publishes no paths"


def test_every_documented_operation_declares_a_success_response(spec):
    undocumented = [
        f"{method} {path}"
        for path, operations in spec["paths"].items()
        for method, operation in operations.items()
        if not any(code.startswith("2") for code in operation.get("responses", {}))
    ]
    assert not undocumented, f"no success response is declared for: {undocumented}"


def test_a_created_item_matches_its_declared_schema(api, items, spec):
    created = items.create(items.build_item_payload(), persona="admin").assert_ok(201)
    validate(spec, created.as_dict, "POST", "/items", 201)


def test_a_listing_matches_its_declared_schema(api, items, spec):
    items.create_fake_item()
    validate(spec, items.find().assert_ok(200).as_dict, "GET", "/items", 200)


def test_an_order_matches_its_declared_schema(api, items, orders, spec):
    item = items.create_fake_item(price=12.0)
    created = orders.create(orders.build_order_payload([orders.build_line(item["id"], 2)]), persona="member")
    validate(spec, created.assert_ok(201).as_dict, "POST", "/orders", 201)


def test_a_validation_error_matches_the_declared_error_shape(api, items, spec):
    resp = items.create({"name": "", "price": 1.0}, persona="admin")
    assert resp.status_code == 422
    validate(spec, resp.as_dict, "POST", "/items", 422)


def test_every_operation_the_tests_use_is_actually_documented(api):
    documented = set(documented_operations(api.base_url))
    used = {
        ("POST", "/items"),
        ("GET", "/items"),
        ("GET", "/items/{item_id}"),
        ("POST", "/orders"),
        ("GET", "/orders"),
        ("GET", "/orders/{order_id}"),
        ("POST", "/auth/token"),
        ("GET", "/me/budget"),
    }

    missing = sorted(f"{m} {p}" for m, p in used - documented)
    assert not missing, f"the suite calls operations the spec does not describe: {missing}"
