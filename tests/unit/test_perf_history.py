import json
from pathlib import Path

from utils.perf_history import TREND_STATS, append, comparable, compare, normalise, shape

TOKEN = "SECRET-TOKEN-MUST-NOT-LEAK"


def k6_export(*, wrong_totals=0, p95=2.0, vus=4, crossed=()):
    """The structure k6 v2.3.0 writes with --summary-export, key for key.

    The threshold booleans are k6's, not tidied: TRUE means the threshold was
    CROSSED. `crossed` names which expressions to mark that way.
    """

    def gates(*exprs):
        return {expr: expr in crossed for expr in exprs}

    return {
        "root_group": {"name": "", "checks": {}},
        "setup_data": {"token": TOKEN, "itemId": "itm-1"},
        "metrics": {
            "http_req_duration": {
                "avg": 1.1,
                "med": 1.0,
                "max": 9.5,
                "p(90)": 1.8,
                "p(95)": p95,
                "p(99)": p95 + 0.4,
            },
            "http_req_duration{name:POST /orders}": {
                "avg": 1.2,
                "med": 1.1,
                "max": 9.5,
                "p(95)": p95 + 0.1,
                "p(99)": p95 + 0.5,
                "thresholds": gates("p(95)<400", "p(99)<900"),
            },
            "http_req_failed": {"passes": 0, "fails": 100, "value": 0, "thresholds": gates("rate<0.01")},
            "http_reqs": {"count": 200, "rate": 2000.0},
            "iterations": {"count": 100, "rate": 1000.0},
            "checks": {"passes": 400, "fails": 0, "value": 1, "thresholds": gates("rate>0.99")},
            "vus_max": {"value": vus, "min": vus, "max": vus},
            "wrong_totals": {"count": wrong_totals, "rate": 0, "thresholds": gates("count==0")},
            "budget_rejections": {"count": 0, "rate": 0, "thresholds": gates("count==0")},
            "server_errors": {"passes": 0, "fails": 200, "value": 0, "thresholds": gates("rate==0")},
        },
    }


def row(export=None, *, exit_code=0, profile="load", env="local", scenario="write_path"):
    return normalise(
        export or k6_export(),
        scenario=scenario,
        profile=profile,
        env=env,
        base_url="http://127.0.0.1:8000",
        started="2026-09-30T09:00:00+00:00",
        duration=10.0,
        exit_code=exit_code,
    )


def test_a_false_threshold_is_a_pass_not_a_failure():
    recorded = row(k6_export())

    assert recorded["breached"] == []
    assert recorded["verdict"] == "PASSED"


def test_a_true_threshold_is_recorded_as_crossed():
    recorded = row(k6_export(wrong_totals=12, crossed=("count==0",)), exit_code=99)

    assert "wrong_totals count==0" in recorded["breached"]
    assert recorded["verdict"] == "THRESHOLDS BREACHED"
    assert recorded["wrong_totals"] == 12


def test_the_bearer_token_in_setup_data_never_reaches_the_history():
    assert TOKEN not in json.dumps(row())


def test_a_non_zero_exit_is_never_recorded_as_a_pass():
    recorded = row(k6_export(), exit_code=107)

    assert recorded["breached"] == []
    assert recorded["verdict"] == "THRESHOLDS BREACHED"


def test_each_tagged_endpoint_is_recorded_under_its_own_name():
    recorded = row()

    assert set(recorded["endpoints"]) == {"POST /orders"}
    assert recorded["endpoints"]["POST /orders"]["p(95)"] == 2.1


def test_a_run_too_short_to_sample_vus_records_none_instead_of_crashing():
    export = k6_export()
    del export["metrics"]["vus_max"]

    assert row(export)["vus_max"] is None


def test_p99_is_requested_because_k6_leaves_it_out_by_default():
    assert "p(99)" in TREND_STATS.split(",")


def test_the_same_scenario_at_a_different_load_level_is_not_comparable():
    at_four = row(k6_export(vus=4))
    at_twenty = row(k6_export(vus=20))

    assert shape(at_four) != shape(at_twenty)
    assert comparable([at_twenty], at_four) == []


def test_a_breached_run_is_never_a_baseline():
    broken = row(k6_export(p95=1.0, crossed=("count==0",)), exit_code=99)

    assert comparable([broken], row()) == []


def test_a_real_rise_at_the_same_load_level_is_reported_but_does_not_block():
    history = [row(k6_export(p95=2.0)), row(k6_export(p95=2.0)), row(k6_export(p95=8.8))]

    findings = compare(history)

    assert [f.kind for f in findings] == ["p95-rise"]
    assert not findings[0].blocking
    assert "at 4 VUs" in findings[0].message


def test_normal_variance_is_not_a_finding():
    history = [row(k6_export(p95=2.0)), row(k6_export(p95=2.0)), row(k6_export(p95=2.3))]

    assert compare(history) == []


def test_a_bigger_run_is_not_reported_as_a_regression():
    history = [row(k6_export(p95=1.5, vus=3)), row(k6_export(p95=2.1, vus=4))]

    assert [f.kind for f in compare(history)] == ["no-baseline"]


def test_a_fast_broken_run_does_not_make_the_next_healthy_run_look_slow():
    history = [
        row(k6_export(p95=2.0)),
        row(k6_export(p95=0.2, crossed=("count==0",)), exit_code=99),
        row(k6_export(p95=2.0)),
    ]

    assert compare(history) == []


def test_a_crossed_threshold_blocks():
    history = [row(k6_export(wrong_totals=3, crossed=("count==0",)), exit_code=99)]

    assert any(f.kind == "threshold" and f.blocking for f in compare(history))


def test_an_unknown_vu_count_is_left_out_of_the_message_rather_than_printed_as_none():
    export = k6_export()
    del export["metrics"]["vus_max"]

    messages = " ".join(f.message for f in compare([row(export, scenario="smoke", profile="smoke")]))

    assert "None" not in messages


def test_rows_are_appended_one_per_line(tmp_path: Path):
    ledger = tmp_path / "reports" / "perf.jsonl"

    append(row(), ledger)
    append(row(), ledger)

    assert len(ledger.read_text().splitlines()) == 2
