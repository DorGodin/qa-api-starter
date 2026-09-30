from utils.run_report import RunReport, TestOutcome


def outcome(nodeid, result="passed", duration=0.1, message=""):
    return TestOutcome(nodeid=nodeid, outcome=result, duration=duration, message=message)


def report_with(*outcomes, env="qa"):
    report = RunReport(env=env)
    for item in outcomes:
        report.add(item)
    return report


def test_group_comes_from_the_folder():
    assert outcome("tests/suites/test_a.py::t").group == "suites"
    assert outcome("tests/edge-cases/test_a.py::t").group == "edge-cases"
    assert outcome("tests/nowhere/test_a.py::t").group == "other"


def test_counts_cover_every_outcome():
    report = report_with(
        outcome("tests/suites/a.py::x"),
        outcome("tests/suites/b.py::y", "failed"),
        outcome("tests/unit/c.py::z", "skipped"),
    )

    assert report.counts == {"passed": 1, "failed": 1, "skipped": 1}


def test_groups_keep_a_stable_order():
    report = report_with(
        outcome("tests/llm/a.py::x"), outcome("tests/suites/b.py::y"), outcome("tests/unit/c.py::z")
    )

    assert list(report.by_group()) == ["suites", "unit", "llm"]


def test_a_run_that_collected_nothing_is_not_a_pass():
    """Zero tests with a zero exit code is how a suite stops protecting anything."""
    assert RunReport(env="qa").verdict == "NO TESTS RAN"


def test_the_verdict_distinguishes_a_clean_pass_from_one_with_skips():
    assert report_with(outcome("tests/suites/a.py::x")).verdict == "PASSED"
    assert report_with(outcome("tests/suites/a.py::x", "skipped")).verdict == "PASSED WITH SKIPS"
    assert report_with(outcome("tests/suites/a.py::x", "failed")).verdict == "FAILED"


REAL_LONGREPR = """
    def test_totals():
        item = items.create_fake_item(price=25.0)
>       assert order["total_amount"] == 80.0
E       AssertionError: assert 75.0 == 80.0
E        +  where 75.0 = order["total_amount"]

tests/suites/test_order_flow.py:42: AssertionError
"""


def test_a_failure_reports_the_assertion_not_the_source_line():
    """The shape pytest actually produces, not a tidied version of it."""
    item = outcome("tests/suites/test_order_flow.py::test_totals", "failed", message=REAL_LONGREPR)

    assert item.first_line == "AssertionError: assert 75.0 == 80.0"
    assert "def test_totals" not in item.first_line


def test_a_message_with_no_error_marker_falls_back_to_its_first_line():
    assert outcome("a::b", "failed", message="\nConnection refused\nmore").first_line == "Connection refused"


def test_a_failure_shows_its_first_meaningful_line():
    item = outcome("tests/suites/a.py::x", "failed", message="\n\nE   AssertionError: 75.0 != 80.0\n  more")
    assert item.first_line == "AssertionError: 75.0 != 80.0"


def test_a_very_long_message_is_trimmed():
    assert len(outcome("a::b", "failed", message="x" * 500).first_line) <= 160


def test_slowest_is_ordered_and_capped():
    report = report_with(*[outcome(f"tests/suites/a.py::t{i}", duration=i) for i in range(10)])
    slowest = report.slowest(limit=3)

    assert [o.duration for o in slowest] == [9, 8, 7]


def test_the_markdown_names_the_environment_and_the_verdict():
    text = report_with(
        outcome("tests/suites/a.py::x", "failed", message="E   boom"), env="staging"
    ).to_markdown()

    assert "FAILED" in text
    assert "`staging`" in text
    assert "boom" in text


def test_skips_are_presented_as_unanswered_questions():
    text = report_with(
        outcome("tests/unit/a.py::x", "skipped", message="TICKET-1: waiting on a fix")
    ).to_markdown()

    assert "did not answer" in text
    assert "TICKET-1" in text


def test_the_report_is_written_where_it_is_asked_for(tmp_path):
    path = report_with(outcome("tests/suites/a.py::x")).write(tmp_path / "reports")

    assert path.name == "last-run.md"
    assert "Run report" in path.read_text(encoding="utf-8")


def test_an_empty_run_still_produces_a_readable_report():
    text = RunReport(env="local").to_markdown()

    assert "0 passed" in text
    assert "None." in text
    assert "NO TESTS RAN" in text, "the report must say so rather than look like a pass"
