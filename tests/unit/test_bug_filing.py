import pytest

from utils.bug_filing import (
    Action,
    Failure,
    build_description,
    build_payload,
    build_title,
    file_failures,
    format_report,
    marker_for,
    route,
)


class FakeTracker:
    def __init__(self, existing=None):
        self.existing = existing or {}
        self.created = []
        self.comments = []

    def search(self, marker):
        return self.existing.get(marker, [])

    def create(self, payload):
        self.created.append(payload)
        return {"key": f"QA-{len(self.created)}"}

    def comment(self, key, body):
        self.comments.append((key, body))
        return {"id": "1"}


@pytest.fixture
def failure():
    return Failure(
        nodeid="tests/suites/test_order_flow.py::test_totals",
        message="AssertionError: total_amount 75.0 != 80.0\n  and a second line",
    )


def test_area_comes_from_the_folder(failure):
    assert failure.area == "suites"
    assert Failure(nodeid="tests/edge-cases/test_validation.py::test_x", message="").area == "edge-cases"


def test_title_names_the_defect_not_the_area(failure):
    title = build_title(failure)
    assert title.startswith("BE - test_totals:")
    assert "75.0 != 80.0" in title
    assert "\n" not in title


def test_title_is_capped_for_trackers_that_reject_long_summaries():
    long_failure = Failure(nodeid="tests/suites/a.py::t", message="x" * 500)
    assert len(build_title(long_failure)) <= 200


def test_description_carries_the_marker_and_the_evidence(failure):
    body = build_description(failure, run_url="https://ci.example/run/1")
    assert marker_for(failure.nodeid) in body
    assert "75.0 != 80.0" in body
    assert "https://ci.example/run/1" in body
    assert body.index("TL;DR") < body.index("Evidence"), "plain language must come first"


def test_routing_falls_back_to_wildcard_then_to_nobody(failure):
    assert route(failure, {"suites": "acc-1"}) == "acc-1"
    assert route(failure, {"*": "acc-fallback"}) == "acc-fallback"
    assert route(failure, {"edge-cases": "acc-2"}) is None
    assert route(failure, None) is None


def test_unassigned_payload_has_no_assignee_key(failure):
    assert "assignee" not in build_payload(failure, "QA")


def test_first_failure_creates_one_ticket(failure):
    tracker = FakeTracker()
    actions = file_failures([failure], tracker, "QA")

    assert [a.kind for a in actions] == ["create"]
    assert len(tracker.created) == 1
    assert tracker.comments == []


def test_known_failure_comments_instead_of_filing_a_duplicate(failure):
    tracker = FakeTracker(existing={marker_for(failure.nodeid): [{"key": "QA-7"}]})
    actions = file_failures([failure], tracker, "QA")

    assert [a.kind for a in actions] == ["comment"]
    assert actions[0].key == "QA-7"
    assert tracker.created == []
    assert tracker.comments[0][0] == "QA-7"


def test_dry_run_creates_and_comments_nothing(failure):
    tracker = FakeTracker()
    actions = file_failures([failure], tracker, "QA", dry_run=True)

    assert actions[0].kind == "dry-run:create"
    assert actions[0].payload["summary"]
    assert tracker.created == [] and tracker.comments == []


def test_each_failing_test_gets_its_own_ticket():
    failures = [
        Failure(nodeid=f"tests/suites/test_a.py::test_{i}", message=f"boom {i}") for i in range(3)
    ]
    tracker = FakeTracker()
    actions = file_failures(failures, tracker, "QA")

    assert len(tracker.created) == 3
    assert len({a.nodeid for a in actions}) == 3


def test_report_lists_every_action(failure):
    text = format_report([Action(kind="create", nodeid=failure.nodeid, key="QA-1")])
    assert "QA-1" in text and failure.nodeid in text
    assert format_report([]) == "bug filing: nothing to report"
