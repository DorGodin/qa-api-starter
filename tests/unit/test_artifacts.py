from pathlib import Path

from utils.artifacts import Artifact, ArtifactLog, load, set_current_test, tail


def test_a_created_entity_is_recorded_with_its_id():
    set_current_test("tests/suites/a.py::t")
    log = ArtifactLog(env="qa")
    log.record("items", {"id": "itm-1", "name": "Lamp"}, persona="admin")

    assert log.items[0].resource == "items"
    assert log.items[0].entity_id == "itm-1"
    assert log.items[0].env == "qa"
    assert log.items[0].persona == "admin"
    assert log.items[0].test == "tests/suites/a.py::t"


def test_a_response_without_an_id_is_not_recorded():
    log = ArtifactLog(env="qa")
    log.record("items", {"detail": "not found"})
    log.record("items", None)
    log.record("items", {"id": ""})

    assert log.items == [], "only a real entity belongs in the ledger"


def test_ids_that_are_numbers_are_kept_as_text():
    log = ArtifactLog(env="qa")
    log.record("orders", {"id": 42})

    assert log.items[0].entity_id == "42"


def test_grouping_and_summary_count_per_resource():
    log = ArtifactLog(env="qa")
    for i in range(3):
        log.record("items", {"id": f"itm-{i}"})
    log.record("orders", {"id": "ord-1"})

    assert log.summary() == {"items": 3, "orders": 1}
    assert list(log.by_resource()) == ["items", "orders"]


def test_appending_keeps_earlier_runs(tmp_path: Path):
    path = tmp_path / "artifacts.jsonl"

    first = ArtifactLog(env="qa")
    first.record("items", {"id": "itm-1"})
    first.append_to(path)

    second = ArtifactLog(env="staging")
    second.record("orders", {"id": "ord-1"})
    second.append_to(path)

    records = load(path)
    assert [r["entity_id"] for r in records] == ["itm-1", "ord-1"]
    assert {r["env"] for r in records} == {"qa", "staging"}


def test_loading_a_missing_file_is_empty_not_an_error(tmp_path: Path):
    assert load(tmp_path / "nothing.jsonl") == []


def test_tail_returns_the_most_recent():
    assert tail([{"n": i} for i in range(10)], 3) == [{"n": 7}, {"n": 8}, {"n": 9}]
    assert len(tail([{"n": i} for i in range(10)], 0)) == 10
