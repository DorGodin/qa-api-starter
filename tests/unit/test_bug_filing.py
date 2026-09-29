import pytest

from utils.bug_filing import (
    Action,
    Failure,
    assertion_line,
    humanise,
    prefix_for,
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


def test_title_says_what_broke_in_words_then_the_mismatch(failure):
    title = build_title(failure)

    assert title.startswith("BE - Totals:"), title
    assert "75.0 != 80.0" in title
    assert "test_" not in title, "a reader should not have to parse a function name"
    assert "\n" not in title


def test_title_is_capped_for_trackers_that_reject_long_summaries():
    long_failure = Failure(nodeid="tests/suites/a.py::t", message="x" * 500)
    assert len(build_title(long_failure)) <= 200


def test_description_follows_the_team_template_in_order(failure):
    body = build_description(failure, run_url="https://ci.example/run/1", env="qa", platform="API")

    sections = ["*ENV(+mobile type):*", "*Precondition:*", "*Steps to reproduce:*",
                "*Actual result:*", "*Expected result:*", "*Notes:*"]
    positions = [body.index(section) for section in sections]
    assert positions == sorted(positions), "the sections must appear in the template's order"


def test_description_carries_the_marker_the_evidence_and_the_environment(failure):
    body = build_description(failure, run_url="https://ci.example/run/1", env="qa", platform="API")

    assert marker_for(failure.nodeid) in body
    assert "75.0 != 80.0" in body
    assert "https://ci.example/run/1" in body
    assert "qa" in body


def test_steps_give_the_exact_command_with_the_right_flag():
    ui = Failure(nodeid="tests/ui/test_x.py::test_y", message="boom")
    body = build_description(ui, env="staging")

    assert "ENV=staging pytest --ui tests/ui/test_x.py::test_y" in body


def test_the_expected_result_is_labelled_as_derived(failure):
    body = build_description(failure, env="qa")

    assert "Totals" in body
    assert "derived from the test name" in body, "a machine guess must not read like a human wrote it"


def test_the_prefix_is_derived_from_where_the_test_lives():
    ui = Failure(nodeid="tests/ui/test_x.py::test_y", message="boom")
    api = Failure(nodeid="tests/suites/test_x.py::test_y", message="boom")

    assert prefix_for(ui) == "FE"
    assert prefix_for(api) == "BE"
    assert build_title(ui).startswith("FE - ")
    assert build_title(api).startswith("BE - ")


def test_an_explicit_prefix_still_wins(failure):
    assert build_title(failure, prefix="OPS").startswith("OPS - ")


def test_the_evidence_leads_with_the_assertion_then_keeps_the_full_trace(failure):
    body = build_description(failure, env="qa")

    actual = body.split("*Actual result:*")[1].split("*Expected result:*")[0]
    assert actual.strip().startswith("AssertionError"), "a reader must see the point before the trace"
    assert "{code}" in actual, "the full trace is still there for whoever needs it"


def test_the_notes_keep_the_teams_standing_line(failure):
    body = build_description(failure, env="qa")

    notes = body.split("*Notes:*")[1]
    assert notes.strip().splitlines()[0] == "Video\\image\\api\\console error attached"


def test_the_assertion_is_taken_from_the_line_pytest_marked():
    message = "    def test_x():\n>       assert a == b\nE       AssertionError: assert 1 == 2\n"
    assert assertion_line(message) == "AssertionError: assert 1 == 2"
    assert assertion_line("") == "assertion failed"


def test_humanise_turns_a_test_name_into_a_sentence():
    assert humanise("test_submitting_draws_from_budget") == "Submitting draws from budget"
    assert humanise("test_") == ""


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
