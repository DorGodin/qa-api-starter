import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import dashboard  # noqa: E402


def run(env="qa", verdict="PASSED", passed=10, failed=0, skipped=0):
    return {
        "started": "2026-09-29T12:00:00+00:00", "env": env, "verdict": verdict,
        "duration": 1.5, "groups": {"suites": {}}, "passed": passed,
        "failed": failed, "skipped": skipped,
    }


def artifact(resource="items", entity_id="itm-1", env="qa"):
    return {
        "resource": resource, "entity_id": entity_id, "env": env, "persona": "admin",
        "test": "tests/suites/a.py::t", "created_at": "2026-09-29T12:00:00+00:00",
    }


def test_a_failed_run_is_coloured_as_a_failure():
    assert dashboard.verdict_class("FAILED") == "bad"
    assert dashboard.verdict_class("NO TESTS RAN") == "bad", "an empty run must not look like a pass"
    assert dashboard.verdict_class("PASSED") == "ok"
    assert dashboard.verdict_class("PASSED WITH SKIPS") == "warn"


def test_the_bar_is_proportional_and_never_divides_by_zero():
    assert "50.0%" in dashboard.bar(1, 1, 0)
    assert dashboard.bar(0, 0, 0).startswith('<div class="bar">')


def test_empty_sections_say_so_instead_of_rendering_a_blank_table():
    assert "No runs recorded" in dashboard.runs_table([])
    assert "No objects recorded" in dashboard.artifacts_table([])


def test_the_newest_run_is_listed_first():
    older, newer = run(env="old"), run(env="new")
    html = dashboard.runs_table([older, newer])

    assert html.index("new") < html.index("old")


def test_object_ids_and_the_test_that_made_them_are_both_shown():
    html = dashboard.artifacts_table([artifact(entity_id="itm-77")])

    assert "itm-77" in html
    assert "tests/suites/a.py::t" in html


def test_values_are_escaped_so_a_payload_cannot_inject_markup():
    html = dashboard.artifacts_table([artifact(entity_id="<script>alert(1)</script>")])

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_the_page_is_written_and_self_contained(tmp_path: Path):
    (tmp_path / "history.jsonl").write_text('{"started":"2026-09-29T12:00:00+00:00","env":"qa","verdict":"PASSED","duration":1.0,"groups":{},"passed":3,"failed":0,"skipped":0}\n')
    out = dashboard.build(reports_dir=tmp_path)

    page = out.read_text(encoding="utf-8")
    assert out.name == "dashboard.html"
    assert "<style>" in page and "http://" not in page, "the dashboard must not depend on a CDN"
