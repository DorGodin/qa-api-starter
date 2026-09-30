import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import dashboard  # noqa: E402


def run(env="qa", verdict="PASSED", passed=10, failed=0, skipped=0):
    return {
        "started": "2026-09-29T12:00:00+00:00",
        "env": env,
        "verdict": verdict,
        "duration": 1.5,
        "groups": {"suites": {}},
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
    }


def artifact(resource="items", entity_id="itm-1", env="qa"):
    return {
        "resource": resource,
        "entity_id": entity_id,
        "env": env,
        "persona": "admin",
        "test": "tests/suites/a.py::t",
        "created_at": "2026-09-29T12:00:00+00:00",
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


def test_times_are_shown_in_a_local_clock_with_the_zone_named():
    """The ledgers store UTC. The screen must not, or 14:20 means nothing."""
    rendered = dashboard.local_time("2026-09-29T14:24:00+00:00")

    assert "2026-09-29" in rendered
    assert rendered != "2026-09-29 14:24", "the time was not converted from UTC"
    assert rendered.split()[-1], "the timezone must be named so the reading is unambiguous"


def test_an_unparseable_timestamp_degrades_instead_of_crashing():
    assert dashboard.local_time("not-a-date") == "not-a-date"


def test_headings_and_columns_are_plain_and_escaped():
    assert dashboard.heading("Runs") == "<h2>Runs</h2>"
    assert dashboard.column("When") == "<th>When</th>"
    assert "&lt;b&gt;" in dashboard.heading("<b>x</b>")


def test_the_page_is_written_and_self_contained(tmp_path: Path):
    (tmp_path / "history.jsonl").write_text(
        '{"started":"2026-09-29T12:00:00+00:00","env":"qa","verdict":"PASSED","duration":1.0,"groups":{},"passed":3,"failed":0,"skipped":0}\n'
    )
    out = dashboard.build(reports_dir=tmp_path)

    page = out.read_text(encoding="utf-8")
    assert out.name == "dashboard.html"
    assert "<style>" in page and "http://" not in page, "the dashboard must not depend on a CDN"


def run_with(failed=(), groups=None, passed=10, failed_count=0):
    return {
        "started": "2026-09-29T12:00:00+00:00",
        "env": "qa",
        "verdict": "PASSED",
        "duration": 1.0,
        "groups": groups
        if groups is not None
        else {"suites": {"passed": passed, "failed": failed_count, "skipped": 0}},
        "failed_tests": list(failed),
        "skipped_tests": [],
        "passed": passed,
        "failed": failed_count,
        "skipped": 0,
    }


def test_instability_ranks_by_how_many_runs_a_test_failed_in():
    history = [
        run_with(failed=["a::x", "b::y"]),
        run_with(failed=["a::x"]),
        run_with(failed=["a::x", "c::z"]),
    ]
    assert dashboard.instability(history) == [("a::x", 3), ("b::y", 1), ("c::z", 1)]


def test_a_test_failing_twice_in_one_run_still_counts_once():
    assert dashboard.instability([run_with(failed=["a::x", "a::x"])]) == [("a::x", 1)]


def test_instability_is_empty_when_nothing_ever_failed():
    assert dashboard.instability([run_with(), run_with()]) == []
    assert "No test has failed" in dashboard.instability_table([])


def test_the_group_table_shows_each_group_of_the_last_run():
    html_out = dashboard.groups_table(run_with(groups={"suites": {"passed": 5, "failed": 1, "skipped": 0}}))

    assert "suites" in html_out and ">5<" in html_out and ">1<" in html_out
    assert "No group data" in dashboard.groups_table(None)


def test_objects_are_grouped_per_environment_with_a_cleanup_command():
    items = [
        {
            "resource": "items",
            "entity_id": "i1",
            "env": "qa",
            "persona": "admin",
            "test": "t",
            "created_at": "x",
        },
        {
            "resource": "orders",
            "entity_id": "o1",
            "env": "qa",
            "persona": "admin",
            "test": "t",
            "created_at": "x",
        },
        {
            "resource": "items",
            "entity_id": "i2",
            "env": "staging",
            "persona": "admin",
            "test": "t",
            "created_at": "x",
        },
    ]
    rows = dashboard.artifacts_by_env(items)

    assert rows == [("qa", 2, "1 items, 1 orders"), ("staging", 1, "1 items")]
    assert "make cleanup ENV=qa" in dashboard.env_table(rows)


def test_a_trend_needs_more_than_one_run():
    assert "Two runs are needed" in dashboard.sparkline([run_with()])


def test_the_sparkline_is_inline_svg_with_no_network_call():
    svg = dashboard.sparkline([run_with(passed=10), run_with(passed=8, failed_count=2)])

    assert svg.startswith("<svg") and "polyline" in svg
    assert "http" not in svg


def test_findings_are_marked_blocking_or_advisory():
    from utils.trends import Finding

    html_out = dashboard.findings_list(
        [Finding("group-shrank", "went from 10 to 7"), Finding("slower", "took longer", blocking=False)]
    )

    assert 'class="bad"' in html_out and 'class="warn"' in html_out
    assert "No regression" in dashboard.findings_list([])


def test_the_sparkline_axis_adapts_so_a_small_dip_is_visible():
    """One failure in sixty is 98%, which on a 0-100 axis is a flat line."""
    runs = [
        run_with(passed=60, failed_count=0),
        run_with(passed=59, failed_count=1),
        run_with(passed=60, failed_count=0),
    ]
    svg = dashboard.sparkline(runs)

    ys = [float(point.split(",")[1]) for point in svg.split('points="')[1].split('"')[0].split()]
    assert max(ys) - min(ys) > 10, "the dip was flattened into a straight line"
    assert "98%" in svg, "the axis range must be stated, or the shape overstates the drop"


def test_a_perfect_history_draws_a_flat_line_without_dividing_by_zero():
    svg = dashboard.sparkline([run_with(), run_with(), run_with()])
    assert svg.startswith("<svg")


def perf(p95=2.0, vus=4, verdict="PASSED", breached=(), profile="load", scenario="write_path", **extra):
    return {
        "started": "2026-09-30T09:00:00+00:00",
        "scenario": scenario,
        "profile": profile,
        "env": "local",
        "base_url": "http://127.0.0.1:8000",
        "duration": 10.0,
        "vus_max": vus,
        "iterations": 100,
        "rps": 2000.0,
        "p95": p95,
        "p99": p95 + 0.4,
        "endpoints": {"POST /orders": {"p(95)": p95 + 0.1, "p(99)": p95 + 0.5}},
        "wrong_totals": 0,
        "budget_rejections": 0,
        "server_errors": 0,
        "breached": list(breached),
        "exit_code": 0 if not breached else 99,
        "verdict": verdict,
        **extra,
    }


def test_with_no_load_history_the_panel_says_how_to_get_one():
    assert "make perf-write" in dashboard.perf_latest_table([])


def test_a_breached_load_run_is_coloured_as_a_failure():
    assert dashboard.verdict_class("THRESHOLDS BREACHED") == "bad"


def test_a_non_zero_correctness_gate_is_red_even_when_latency_was_fine():
    table = dashboard.perf_latest_table([perf(wrong_totals=3)])

    assert "<span class='bad'>3</span>" in table


def test_runs_at_different_load_levels_are_drawn_as_separate_lines():
    grouped = dashboard.perf_series([perf(vus=4), perf(vus=25), perf(vus=4)])

    assert sorted(len(runs) for runs in grouped.values()) == [1, 2]


def test_a_flat_trend_says_it_held_rather_than_quoting_an_empty_range():
    line = dashboard.perf_sparkline([perf(p95=1.93), perf(p95=1.93)])

    assert "held at 1.93ms" in line
    assert "1.93ms to 1.93ms" not in line


def test_a_missing_value_is_a_dash_and_never_the_word_none():
    page = dashboard.perf_runs_table([perf(vus=None)])

    assert ">None<" not in page


def test_the_perf_panel_gives_the_same_answer_as_the_cli():
    from utils.perf_history import compare

    stale_breach = perf(vus=2, verdict="THRESHOLDS BREACHED", breached=["wrong_totals count==0"])
    rows = [stale_breach, perf(), perf()]

    shown = dashboard.perf_findings(rows)

    assert [f.kind for f in shown] == [f.kind for f in compare(rows) if f.kind != "empty"]
    assert not any(
        f.kind == "threshold" for f in shown
    ), "a breach from an old experiment is not a current finding"


def test_the_slowest_endpoints_come_first():
    ranked = dashboard.slowest_endpoints([perf(p95=2.0), perf(p95=9.0, profile="spike")])

    assert ranked[0][2] == 9.1


def test_load_values_are_escaped_so_a_scenario_name_cannot_inject_markup():
    page = dashboard.perf_runs_table([perf(scenario="<script>x</script>")])

    assert "<script>x" not in page


def test_the_page_stays_self_contained_when_load_history_exists(tmp_path: Path):
    import json

    (tmp_path / "perf.jsonl").write_text(json.dumps(perf()) + "\n" + json.dumps(perf(p95=2.1)) + "\n")

    page = dashboard.build(reports_dir=tmp_path).read_text(encoding="utf-8")

    assert dashboard.heading("Load: the latest run of each shape") in page
    assert "write_path / load @ local · 4 VUs" in page
    assert "http://" not in page, "base_url is recorded but must not turn into a link to a live host"


def test_a_rise_on_one_shape_stays_under_its_line_after_another_shape_runs():
    rows = [
        perf(p95=2.0),
        perf(p95=2.0),
        perf(p95=8.8),
        perf(p95=1.0, scenario="smoke", profile="smoke", vus=None),
    ]

    assert not any(f.kind == "p95-rise" for f in dashboard.perf_findings(rows)), "the panel follows the CLI"
    assert "p95-rise" in dashboard.perf_trend_panel(rows), "the line keeps what the panel dropped"


def test_numbers_and_their_units_never_wrap_apart():
    table = dashboard.perf_latest_table([perf()])

    assert "<td class='n'>2.0ms</td>" in table
