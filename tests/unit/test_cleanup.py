import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import cleanup  # noqa: E402


def record(resource="items", entity_id="itm-1", env="qa", created_at="2026-09-29T10:00:00+00:00"):
    return {
        "resource": resource,
        "entity_id": entity_id,
        "env": env,
        "persona": "admin",
        "test": "tests/suites/a.py::t",
        "created_at": created_at,
    }


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class FakeClient:
    config = {"admin_persona": "admin"}

    def __init__(self, statuses=None):
        self.statuses = statuses or {}
        self.deleted = []

    def request(self, method, path, persona="__active__", **kwargs):
        self.deleted.append((method, path))
        return FakeResponse(self.statuses.get(path, 204))


def test_only_the_named_environment_is_selected():
    records = [record(env="qa"), record(entity_id="itm-2", env="staging")]
    assert [r["entity_id"] for r in cleanup.select(records, "qa")] == ["itm-1"]


def test_a_resource_filter_narrows_it_further():
    records = [record(), record(resource="orders", entity_id="ord-1")]
    assert [r["resource"] for r in cleanup.select(records, "qa", resource="orders")] == ["orders"]


def test_a_since_filter_drops_older_objects():
    records = [
        record(entity_id="old", created_at="2026-09-01T10:00:00+00:00"),
        record(entity_id="new", created_at="2026-09-29T10:00:00+00:00"),
    ]
    selected = cleanup.select(records, "qa", since="2026-09-20")
    assert [r["entity_id"] for r in selected] == ["new"]


def test_the_newest_objects_come_first():
    records = [record(entity_id="first"), record(entity_id="second")]
    assert [r["entity_id"] for r in cleanup.select(records, "qa")] == ["second", "first"]


def test_an_object_recorded_twice_is_deleted_once():
    records = [record(entity_id="itm-1"), record(entity_id="itm-1")]
    assert len(cleanup.select(records, "qa")) == 1


def test_every_outcome_is_counted_rather_than_assumed(monkeypatch):
    monkeypatch.setenv("ENV", "qa")
    client = FakeClient(statuses={"/items/gone": 404, "/items/locked": 403, "/items/broken": 500})
    records = [record(entity_id=eid) for eid in ("ok", "gone", "locked", "broken")]

    outcome = cleanup.delete_all(client, records)

    assert {k: v for k, v in outcome.items() if v} == {
        "deleted": 1,
        "not found": 1,
        "refused": 1,
        "failed": 1,
    }


def test_cleanup_refuses_to_run_against_production(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    with pytest.raises(AssertionError, match="never run against prod"):
        cleanup.delete_all(FakeClient(), [record()])


def test_the_summary_reads_as_a_sentence():
    assert cleanup.summarise([record(), record(resource="orders")]) == "1 items, 1 orders"
    assert cleanup.summarise([]) == "nothing"


def test_a_resource_with_no_delete_endpoint_is_reported_and_never_called(monkeypatch):
    monkeypatch.setenv("ENV", "qa")
    client = FakeClient()
    records = [record(resource="customers", entity_id="c-1"), record(resource="items", entity_id="i-1")]

    outcome = cleanup.delete_all(client, records, deletable={"items"})

    assert outcome["no delete endpoint"] == 1 and outcome["deleted"] == 1
    assert client.deleted == [("DELETE", "/items/i-1")], "a DELETE that cannot exist was sent"


def test_a_404_is_gone_only_when_the_product_says_it_can_delete(monkeypatch):
    monkeypatch.setenv("ENV", "qa")
    client = FakeClient(statuses={"/items/i-1": 404})

    assert cleanup.delete_all(client, [record(entity_id="i-1")], deletable={"items"})["already gone"] == 1
    assert cleanup.delete_all(client, [record(entity_id="i-1")], deletable=None)["not found"] == 1


def test_the_delete_endpoints_are_read_from_the_openapi_operations():
    operations = (
        ("DELETE", "/items/{item_id}"),
        ("GET", "/customers/{customer_id}"),
        ("DELETE", "/barbers/{barber_id}/time-off/{day}"),
        ("POST", "/orders"),
    )

    assert cleanup.deletable_resources(operations) == {"items"}, "a nested DELETE does not delete the parent"
