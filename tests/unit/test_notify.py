import pytest

from utils.notify import build_message, notify
from utils.run_report import RunReport, TestOutcome
from utils.trends import Finding


def report(env="qa", outcomes=()):
    built = RunReport(env=env)
    for outcome in outcomes:
        built.add(outcome)
    return built


def outcome(nodeid, result="passed", message=""):
    return TestOutcome(nodeid=nodeid, outcome=result, duration=0.1, message=message)


def test_a_clean_run_reads_in_one_line():
    message = build_message(report(outcomes=[outcome("tests/suites/a.py::x")]))

    assert "PASSED" in message and "`qa`" in message
    assert "1 passed" in message


def test_failures_are_named_with_the_assertion():
    message = build_message(report(outcomes=[
        outcome("tests/suites/a.py::x", "failed", "E   AssertionError: 75.0 != 80.0"),
    ]))

    assert "tests/suites/a.py::x" in message
    assert "75.0 != 80.0" in message


def test_a_long_list_of_failures_is_capped():
    outcomes = [outcome(f"tests/suites/a.py::t{i}", "failed", "E   boom") for i in range(12)]
    message = build_message(report(outcomes=outcomes))

    assert "and 7 more" in message
    assert message.count("tests/suites/a.py::t") == 5


def test_skips_are_described_as_unanswered_questions():
    message = build_message(report(outcomes=[outcome("tests/unit/a.py::x", "skipped")]))
    assert "did not answer" in message


def test_regression_findings_ride_along():
    message = build_message(report(outcomes=[outcome("a::b")]),
                            findings=[Finding("group-shrank", "unit went from 10 to 7")])
    assert "group-shrank" in message and "10 to 7" in message


def test_a_run_url_goes_last():
    message = build_message(report(outcomes=[outcome("a::b")]), run_url="https://ci.example/1")
    assert message.strip().endswith("https://ci.example/1")


def test_a_dry_run_sends_nothing_and_needs_no_webhook():
    sent = []
    message = notify(report(outcomes=[outcome("a::b")]), webhook=None, dry_run=True,
                     sender=lambda url, text: sent.append((url, text)))

    assert sent == []
    assert "PASSED" in message


def test_sending_without_a_webhook_fails_loudly():
    with pytest.raises(RuntimeError, match="no webhook configured"):
        notify(report(outcomes=[outcome("a::b")]), webhook=None)


def test_the_message_reaches_the_sender_unchanged():
    sent = []
    message = notify(report(outcomes=[outcome("a::b")]), webhook="https://hooks.example/x",
                     sender=lambda url, text: sent.append((url, text)) or 200)

    assert sent[0][0] == "https://hooks.example/x"
    assert sent[0][1] == message
