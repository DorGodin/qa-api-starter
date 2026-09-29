import pytest

from utils.functions.seed import seed_catalogue


def test_create_read_update_delete(items):
    created = items.create_fake_item(price=30.0)

    fetched = items.get_by_id(created["id"]).assert_ok(200).as_dict
    assert fetched == created

    updated = items.update_by_id(created["id"], {"price": 45.5}, persona="admin").assert_ok(200).as_dict
    assert updated["price"] == pytest.approx(45.5)

    items.delete_by_id(created["id"], persona="admin").assert_ok(204)
    assert items.get_by_id(created["id"]).status_code == 404


def test_find_filters_and_paginates(items):
    for price in (10.0, 20.0, 30.0):
        items.create_fake_item(name=f"Widget {price:g}", price=price)
    items.create_fake_item(name="Gadget", price=99.0)

    page = items.find(params={"name": "widget", "limit": 2}).assert_ok(200)
    assert page.as_dict["total"] == 3
    assert len(page.content) == 2


def test_seed_helper_is_idempotent(items):
    first = seed_catalogue(items, count=3)
    second = seed_catalogue(items, count=3)

    assert len(first) == 3
    assert [i["id"] for i in first] == [i["id"] for i in second]
