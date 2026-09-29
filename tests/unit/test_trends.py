from utils.trends import Finding, blocking, compare, format_findings


def run(env="qa", verdict="PASSED", duration=10.0, groups=None, skipped_tests=None, failed=0, passed=10):
    return {
        "started": "2026-09-29T12:00:00+00:00", "env": env, "verdict": verdict, "duration": duration,
        "groups": groups if groups is not None else {"suites": {"passed": 10, "failed": 0, "skipped": 0}},
        "skipped_tests": skipped_tests or [], "passed": passed, "failed": failed, "skipped": 0,
    }


def kinds(findings):
    return [f.kind for f in findings]


def test_no_history_is_not_a_finding():
    assert compare([]) == []


def test_a_first_run_says_there_is_nothing_to_compare_against():
    findings = compare([run()])

    assert kinds(findings) == ["no-baseline"]
    assert not blocking(findings), "a first run must not fail a pipeline"


def test_a_targeted_run_is_not_compared_against_a_full_one():
    """Running one group on purpose is not a regression."""
    full = run(groups={"suites": {"passed": 10}, "unit": {"passed": 5}})
    targeted = run(groups={"unit": {"passed": 5}})

    assert kinds(compare([full, targeted])) == ["no-baseline"]


def test_a_group_that_shrank_is_blocking():
    before = run(groups={"suites": {"passed": 10, "failed": 0, "skipped": 0}})
    after = run(groups={"suites": {"passed": 7, "failed": 0, "skipped": 0}})

    findings = compare([before, after])
    assert kinds(findings) == ["group-shrank"]
    assert blocking(findings)
    assert "10" in findings[0].message and "7" in findings[0].message


def test_a_group_that_grew_is_not_a_finding():
    before = run(groups={"suites": {"passed": 10}})
    after = run(groups={"suites": {"passed": 12}})

    assert compare([before, after]) == []


def test_a_newly_skipped_test_is_named():
    before = run(skipped_tests=[])
    after = run(skipped_tests=["tests/suites/a.py::test_x"])

    findings = compare([before, after])
    assert kinds(findings) == ["new-skip"]
    assert "tests/suites/a.py::test_x" in findings[0].message


def test_a_test_that_was_already_skipped_is_not_reported_again():
    skipped = ["tests/suites/a.py::test_x"]
    assert compare([run(skipped_tests=skipped), run(skipped_tests=skipped)]) == []


def test_a_run_that_collected_nothing_is_blocking():
    findings = compare([run(), run(verdict="NO TESTS RAN", groups={})])

    assert "no-tests" in kinds(findings)
    assert blocking(findings)


def test_getting_slower_is_reported_but_does_not_block():
    history = [run(duration=10.0) for _ in range(3)] + [run(duration=20.0)]
    findings = compare(history)

    assert kinds(findings) == ["slower"]
    assert not blocking(findings), "speed is a conversation, not a gate"


def test_a_short_suite_is_not_judged_on_percentages():
    history = [run(duration=0.2) for _ in range(3)] + [run(duration=0.5)]
    assert compare(history) == [], "percentages on sub-second runs are noise"


def test_a_new_failure_is_reported():
    findings = compare([run(failed=0), run(failed=2, verdict="FAILED")])
    assert "newly-failing" in kinds(findings)


def test_the_report_marks_blocking_findings_differently():
    text = format_findings([Finding("a", "blocking one"), Finding("b", "advisory", blocking=False)])

    assert "! a:" in text and "- b:" in text
    assert format_findings([]) == "no regression against the previous runs"
