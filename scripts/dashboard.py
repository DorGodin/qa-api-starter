#!/usr/bin/env python3
"""Build a static dashboard from what the runs recorded.

No server, no database, no service to keep alive: the runs already append two
JSONL files, and this turns them into one HTML file you can open or attach to a
message.

    python scripts/dashboard.py            # writes reports/dashboard.html
    python scripts/dashboard.py --runs 50
"""

from __future__ import annotations

import argparse
import html
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.artifacts import load, tail  # noqa: E402

REPORTS = Path(__file__).resolve().parents[1] / "reports"

# The ledgers store UTC, which is the only sane thing to store. Display is a
# separate decision: show the reader their own clock, and label it, so "14:20"
# is never ambiguous. DASHBOARD_TZ overrides, e.g. DASHBOARD_TZ=Asia/Jerusalem.
DISPLAY_TZ = ZoneInfo(os.environ["DASHBOARD_TZ"]) if os.environ.get("DASHBOARD_TZ") else None


def local_time(value: str) -> str:
    """UTC in the file, the reader's clock on the screen, with the zone named."""
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return value.replace("T", " ")[:16]
    local = moment.astimezone(DISPLAY_TZ) if DISPLAY_TZ else moment.astimezone()
    return f"{local:%Y-%m-%d %H:%M} {local:%Z}".strip()


def heading(title: str) -> str:
    return f"<h2>{html.escape(title)}</h2>"


def column(title: str) -> str:
    return f"<th>{html.escape(title)}</th>"


CSS = """
:root{--ok:#0e7c66;--bad:#b4232c;--warn:#b26a00;--ink:#1f2933;--mut:#6b7280;--line:#e4e7eb;--bg:#f7f8fa}
*{box-sizing:border-box}
body{font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;background:var(--bg);color:var(--ink)}
header{background:#0e5c63;color:#fff;padding:22px 28px}
h1{margin:0;font-size:20px;letter-spacing:.5px}
header p{margin:6px 0 0;color:#bfe0e2;font-size:13px}
main{max-width:1060px;margin:22px auto;padding:0 18px 40px}
section{background:#fff;border:1px solid var(--line);border-radius:8px;padding:16px 18px;margin-bottom:18px}
h2{margin:0 0 12px;font-size:13px;letter-spacing:1.4px;text-transform:uppercase;color:#0e5c63}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--mut);font-weight:600;padding:6px 8px;border-bottom:2px solid var(--line)}
td{padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top;word-break:break-word}
td code{white-space:normal}
tr:last-child td{border-bottom:0}
code{font-family:ui-monospace,Menlo,monospace;font-size:12px;background:#f3f4f6;padding:1px 5px;border-radius:4px}
.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}.warn{color:var(--warn);font-weight:600}
.bar{display:flex;height:8px;border-radius:4px;overflow:hidden;background:var(--line);min-width:110px}
.bar span{display:block}
.bar .p{background:var(--ok)}.bar .f{background:var(--bad)}.bar .s{background:#cbd2d9}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.card{border:1px solid var(--line);border-radius:6px;padding:10px 12px}
.card b{display:block;font-size:22px}
.card span{color:var(--mut);font-size:12px}
.empty{color:var(--mut);font-style:italic}
.hint{color:var(--mut);font-size:12px;margin:4px 0 0}
.ok-note{color:var(--ok);margin:0}
.findings{margin:0;padding-left:18px}
.findings li{margin:3px 0;font-size:13px}
.findings span{font-weight:600;margin-right:6px}
td.n{white-space:nowrap}
.trend-note{margin:2px 0 0;font-size:12px}
h3{margin:14px 0 6px;font-size:12px;font-weight:600;color:var(--ink)}
section h3:first-of-type{margin-top:0}
"""


def verdict_class(verdict: str) -> str:
    return {"PASSED": "ok", "FAILED": "bad", "NO TESTS RAN": "bad", "THRESHOLDS BREACHED": "bad"}.get(
        verdict, "warn"
    )


def bar(passed: int, failed: int, skipped: int) -> str:
    total = max(passed + failed + skipped, 1)
    parts = [("p", passed), ("f", failed), ("s", skipped)]
    return (
        '<div class="bar">'
        + "".join(
            f'<span class="{cls}" style="width:{count / total * 100:.1f}%"></span>' for cls, count in parts
        )
        + "</div>"
    )


def runs_table(runs: list[dict]) -> str:
    if not runs:
        return '<p class="empty">No runs recorded yet.</p>'
    rows = []
    for run in reversed(runs):
        groups = ", ".join(run.get("groups", {})) or "—"
        rows.append(
            "<tr>"
            f"<td>{html.escape(local_time(run['started']))}</td>"
            f"<td><code>{html.escape(run['env'])}</code></td>"
            f"<td class='{verdict_class(run['verdict'])}'>{html.escape(run['verdict'])}</td>"
            f"<td>{run['passed']}</td><td>{run['failed']}</td><td>{run['skipped']}</td>"
            f"<td>{bar(run['passed'], run['failed'], run['skipped'])}</td>"
            f"<td>{run['duration']}s</td><td>{html.escape(groups)}</td>"
            "</tr>"
        )
    header = (
        "".join(column(name) for name in ("When", "Env", "Verdict", "Pass", "Fail", "Skip"))
        + "<th></th>"
        + "".join(column(name) for name in ("Time", "Groups"))
    )
    return f"<table><tr>{header}</tr>" + "".join(rows) + "</table>"


def artifacts_table(items: list[dict], limit: int = 200) -> str:
    if not items:
        return '<p class="empty">No objects recorded yet. They appear here as soon as a run creates one.</p>'
    rows = [
        "<tr>"
        f"<td><code>{html.escape(item['resource'])}</code></td>"
        f"<td><code>{html.escape(item['entity_id'])}</code></td>"
        f"<td><code>{html.escape(item['env'])}</code></td>"
        f"<td>{html.escape(item.get('persona') or '—')}</td>"
        f"<td><code>{html.escape(item['test'])}</code></td>"
        f"<td>{html.escape(local_time(item['created_at']))}</td>"
        "</tr>"
        for item in reversed(items[-limit:])
    ]
    header = "".join(column(name) for name in ("Resource", "Id", "Env", "Created as", "By test", "When"))
    return f"<table><tr>{header}</tr>" + "".join(rows) + "</table>"


def instability(runs: list[dict], limit: int = 8) -> list[tuple[str, int]]:
    """Tests ranked by how many recorded runs they failed in.

    A test that fails every time is broken and somebody already knows. A test
    that fails in three runs out of twenty is the one nobody has pinned down,
    and it is the reason people re-run a pipeline instead of reading it.
    """
    failures: Counter = Counter()
    for run in runs:
        for nodeid in set(run.get("failed_tests", [])):
            failures[nodeid] += 1
    return failures.most_common(limit)


def group_rows(run: dict) -> list[tuple[str, int, int, int]]:
    rows = []
    for name, counts in (run.get("groups") or {}).items():
        rows.append((name, counts.get("passed", 0), counts.get("failed", 0), counts.get("skipped", 0)))
    return rows


def artifacts_by_env(items: list[dict]) -> list[tuple[str, int, str]]:
    """What is still recorded per environment, so cleanup has a target."""
    by_env: dict[str, Counter] = {}
    for item in items:
        by_env.setdefault(item["env"], Counter())[item["resource"]] += 1
    return [
        (env, sum(counts.values()), ", ".join(f"{n} {r}" for r, n in sorted(counts.items())))
        for env, counts in sorted(by_env.items())
    ]


def sparkline(runs: list[dict], width: int = 560, height: int = 44) -> str:
    """Pass rate per run, drawn inline. No chart library, no CDN, no network."""
    if len(runs) < 2:
        return '<p class="empty">Two runs are needed before a trend means anything.</p>'

    rates = []
    for run in runs:
        total = run.get("passed", 0) + run.get("failed", 0)
        rates.append(run["passed"] / total if total else 0.0)

    # One failure in sixty is 98%, which against a 0-100 axis is a flat line. Scale
    # to the observed range so the dip is visible, and label it so nobody reads
    # the shape as a bigger drop than it was.
    low = min(rates)
    span = max(1.0 - low, 0.02)

    def y(rate: float) -> float:
        return height - ((rate - low) / span) * (height - 8) - 4

    step = width / (len(rates) - 1)
    points = " ".join(f"{i * step:.1f},{y(rate):.1f}" for i, rate in enumerate(rates))
    dots = "".join(
        f'<circle cx="{i * step:.1f}" cy="{y(rate):.1f}" r="2.5" '
        f'fill="{"#b4232c" if rate < 1 else "#0e7c66"}"/>'
        for i, rate in enumerate(rates)
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img" '
        f'aria-label="pass rate per run">'
        f'<polyline points="{points}" fill="none" stroke="#0e5c63" stroke-width="2"/>{dots}</svg>'
        f'<p class="hint">Pass rate across the last {len(rates)} runs, oldest on the left. '
        f"The axis covers {low:.0%} to 100%, so a small dip is still visible.</p>"
    )


def instability_table(ranked: list[tuple[str, int]], total_runs: int = 0) -> str:
    if not ranked:
        return '<p class="empty">No test has failed in the recorded runs.</p>'
    rows = "".join(
        f"<tr><td><code>{html.escape(nodeid)}</code></td><td>{failures}</td></tr>"
        for nodeid, failures in ranked
    )
    suffix = f" of {total_runs}" if total_runs else ""
    return f"<table><tr><th>Test</th><th>Runs it failed in{suffix}</th></tr>{rows}</table>"


def groups_table(run: dict | None) -> str:
    if not run or not group_rows(run):
        return '<p class="empty">No group data for the last run.</p>'
    rows = "".join(
        f"<tr><td><code>{html.escape(name)}</code></td><td>{p}</td><td>{f}</td><td>{s}</td>"
        f"<td>{bar(p, f, s)}</td></tr>"
        for name, p, f, s in group_rows(run)
    )
    return (
        f"<table><tr><th>Group</th><th>Passed</th><th>Failed</th><th>Skipped</th><th></th></tr>{rows}</table>"
    )


def env_table(rows: list[tuple[str, int, str]]) -> str:
    if not rows:
        return '<p class="empty">Nothing recorded yet.</p>'
    body = "".join(
        f"<tr><td><code>{html.escape(env)}</code></td><td>{total}</td><td>{html.escape(detail)}</td>"
        f"<td><code>make cleanup ENV={html.escape(env)}</code></td></tr>"
        for env, total, detail in rows
    )
    return (
        f"<table><tr><th>Environment</th><th>Objects</th><th>What</th><th>Remove with</th></tr>{body}</table>"
    )


def findings_list(findings: list) -> str:
    if not findings:
        return '<p class="ok-note">No regression against the earlier runs.</p>'
    items = "".join(
        f'<li><span class="{"bad" if f.blocking else "warn"}">{html.escape(f.kind)}</span> '
        f"{html.escape(f.message)}</li>"
        for f in findings
    )
    return f"<ul class='findings'>{items}</ul>"


def cards(runs: list[dict], items: list[dict], perf: list[dict] | None = None) -> str:
    perf = perf or []
    by_resource = Counter(item["resource"] for item in items)
    latest = runs[-1] if runs else None
    tiles = [
        ("Runs recorded", len(runs)),
        ("Objects created", len(items)),
        (
            "Environments",
            len(
                {item["env"] for item in items} | {run["env"] for run in runs} | {row["env"] for row in perf}
            ),
        ),
    ]
    if perf:
        tiles.append(("Load runs recorded", len(perf)))
        tiles.append(("Last load verdict", perf[-1]["verdict"]))
    tiles += [(f"{resource} created", count) for resource, count in by_resource.most_common(3)]
    if latest:
        tiles.insert(0, ("Last verdict", latest["verdict"]))
    return (
        '<div class="cards">'
        + "".join(
            f'<div class="card"><b>{html.escape(str(value))}</b><span>{html.escape(label)}</span></div>'
            for label, value in tiles
        )
        + "</div>"
    )


def series_label(key: tuple) -> str:
    scenario, profile, env, vus = key
    users = f" · {vus} VUs" if vus is not None else ""
    return f"{scenario} / {profile} @ {env}{users}"


def perf_series(rows: list[dict]) -> dict[tuple, list[dict]]:
    """Runs grouped by shape - the same key the trend check uses, so a line on
    this page and a finding above it always describe the same runs."""
    from utils.perf_history import shape

    grouped: dict[tuple, list[dict]] = {}
    for row in rows:
        grouped.setdefault(shape(row), []).append(row)
    return grouped


def _ms(value) -> str:
    return f"{value}ms" if isinstance(value, (int, float)) else "—"


def _or_dash(value) -> str:
    """A key that is present but null is still missing. `.get(k, "—")` shows "None"."""
    return "—" if value is None else html.escape(str(value))


def _gate(value, *, rate: bool = False) -> str:
    """The correctness gates. Zero is the only healthy value, so anything else is red."""
    if value is None:
        return "—"
    shown = f"{value:.2%}" if rate else str(value)
    return f"<span class='{'ok' if value == 0 else 'bad'}'>{html.escape(shown)}</span>"


def perf_latest_table(rows: list[dict]) -> str:
    if not rows:
        return (
            '<p class="empty">No load run recorded yet. Run <code>make perf-write</code> '
            "and it will appear here.</p>"
        )
    body = []
    for key, runs in perf_series(rows).items():
        last = runs[-1]
        body.append(
            "<tr>"
            f"<td><code>{html.escape(series_label(key))}</code></td>"
            f"<td>{html.escape(local_time(last['started']))}</td>"
            f"<td class='{verdict_class(last['verdict'])}'>{html.escape(last['verdict'])}</td>"
            f"<td class='n'>{_ms(last.get('p95'))}</td><td class='n'>{_ms(last.get('p99'))}</td>"
            f"<td class='n'>{_or_dash(last.get('rps'))}</td><td class='n'>{_or_dash(last.get('iterations'))}</td>"
            f"<td class='n'>{_gate(last.get('wrong_totals'))}</td>"
            f"<td class='n'>{_gate(last.get('budget_rejections'))}</td>"
            f"<td class='n'>{_gate(last.get('server_errors'), rate=True)}</td>"
            "</tr>"
        )
    header = "".join(
        column(name)
        for name in (
            "Shape",
            "When",
            "Verdict",
            "p95",
            "p99",
            "Req/s",
            "Iterations",
            "Wrong totals",
            "Budget 402s",
            "5xx",
        )
    )
    return (
        f"<table><tr>{header}</tr>{''.join(body)}</table>"
        '<p class="hint">The last three columns are correctness, not speed: a fast run that '
        "computed a wrong total is a failed run. Zero is the only healthy value.</p>"
    )


def perf_sparkline(runs: list[dict], width: int = 560, height: int = 44) -> str:
    """p95 per run for ONE shape, inline SVG, no network."""
    points_in = [(row["p95"], row.get("verdict")) for row in runs if isinstance(row.get("p95"), (int, float))]
    if len(points_in) < 2:
        return '<p class="empty">Two runs of this shape are needed before a trend means anything.</p>'

    values = [value for value, _ in points_in]
    low, high = min(values), max(values)
    axis = (
        f"p95 held at {low}ms in every run."
        if low == high
        else f"The axis covers {low}ms to {high}ms, so a slow climb is visible."
    )
    # Same reasoning as the pass-rate line: a 2ms to 2.4ms climb is flat on an
    # axis from zero. Scale to what was observed, and say so in the caption.
    span = max(high - low, max(high * 0.05, 0.01))

    def y(value: float) -> float:
        return height - ((value - low) / span) * (height - 8) - 4

    step = width / (len(values) - 1)
    line = " ".join(f"{i * step:.1f},{y(value):.1f}" for i, value in enumerate(values))
    dots = "".join(
        f'<circle cx="{i * step:.1f}" cy="{y(value):.1f}" r="2.5" '
        f'fill="{"#b4232c" if verdict != "PASSED" else "#0e7c66"}"/>'
        for i, (value, verdict) in enumerate(points_in)
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img" '
        f'aria-label="p95 per run">'
        f'<polyline points="{line}" fill="none" stroke="#0e5c63" stroke-width="2"/>{dots}</svg>'
        f'<p class="hint">p95 across the last {len(values)} runs, oldest on the left, red where a '
        f"threshold was crossed. {axis}</p>"
    )


def series_note(runs: list[dict]) -> str:
    """This line's own trend check, under the line.

    The findings panel follows `make perf-trends` and looks only at the latest run,
    so a rise on one shape drops out of it as soon as another shape runs. The line
    keeps it: here it is dated and sits next to the points it describes, so it
    reads as history rather than as an alarm that never clears.
    """
    from utils.perf_history import compare as compare_perf

    rises = [f for f in compare_perf(runs) if f.kind == "p95-rise"]
    return "".join(
        f'<p class="trend-note"><span class="warn">p95-rise</span> '
        f"{html.escape(f.message)} Last run {html.escape(local_time(runs[-1]['started']))}.</p>"
        for f in rises
    )


def perf_trend_panel(rows: list[dict], per_series: int = 25) -> str:
    grouped = perf_series(rows)
    if not grouped:
        return '<p class="empty">No load run recorded yet.</p>'
    return "".join(
        f"<h3><code>{html.escape(series_label(key))}</code></h3>"
        f"{perf_sparkline(tail(runs, per_series))}{series_note(runs)}"
        for key, runs in grouped.items()
    )


def slowest_endpoints(rows: list[dict], limit: int = 8) -> list[tuple[str, str, object, object]]:
    """Where the time goes, from the latest run of each shape."""
    ranked = []
    for key, runs in perf_series(rows).items():
        for endpoint, stats in (runs[-1].get("endpoints") or {}).items():
            p95 = stats.get("p(95)")
            if isinstance(p95, (int, float)):
                ranked.append((series_label(key), endpoint, p95, stats.get("p(99)")))
    return sorted(ranked, key=lambda row: row[2], reverse=True)[:limit]


def endpoints_table(ranked: list[tuple[str, str, object, object]]) -> str:
    if not ranked:
        return '<p class="empty">No per-endpoint timings recorded yet.</p>'
    body = "".join(
        f"<tr><td><code>{html.escape(endpoint)}</code></td><td class='n'>{_ms(p95)}</td><td class='n'>{_ms(p99)}</td>"
        f"<td><code>{html.escape(shape)}</code></td></tr>"
        for shape, endpoint, p95, p99 in ranked
    )
    return f"<table><tr><th>Endpoint</th><th>p95</th><th>p99</th><th>Shape</th></tr>{body}</table>"


def perf_runs_table(rows: list[dict]) -> str:
    if not rows:
        return '<p class="empty">No load run recorded yet.</p>'
    body = []
    for row in reversed(rows):
        crossed = ", ".join(row.get("breached") or []) or "—"
        body.append(
            "<tr>"
            f"<td>{html.escape(local_time(row['started']))}</td>"
            f"<td><code>{html.escape(row['scenario'])}</code></td>"
            f"<td>{html.escape(row['profile'])}</td>"
            f"<td><code>{html.escape(row['env'])}</code></td>"
            f"<td class='{verdict_class(row['verdict'])}'>{html.escape(row['verdict'])}</td>"
            f"<td class='n'>{_or_dash(row.get('vus_max'))}</td><td class='n'>{_ms(row.get('p95'))}</td>"
            f"<td class='n'>{_or_dash(row.get('duration'))}s</td><td>{html.escape(crossed)}</td>"
            "</tr>"
        )
    header = "".join(
        column(name)
        for name in ("When", "Scenario", "Profile", "Env", "Verdict", "VUs", "p95", "Time", "Crossed")
    )
    return f"<table><tr>{header}</tr>{''.join(body)}</table>"


def perf_findings(rows: list[dict]) -> list:
    """The same answer `make perf-trends` gives: the latest run against its shape.

    Not the latest run of EVERY shape. A shape that ran once and never again -
    a local experiment at an odd VU count - would then keep its verdict on this
    panel forever, and a panel that is always red is one nobody reads. Every
    shape's last verdict is still on the page, dated, in the table below.
    """
    from utils.perf_history import compare as compare_perf

    return [f for f in compare_perf(rows) if f.kind != "empty"] if rows else []


def build(reports_dir: Path = REPORTS, run_limit: int = 25) -> Path:
    all_runs = load(reports_dir / "history.jsonl")
    runs = tail(all_runs, run_limit)
    items = load(reports_dir / "artifacts.jsonl")
    perf = load(reports_dir / "perf.jsonl")
    latest = runs[-1] if runs else None

    try:
        from utils.trends import compare

        findings = compare(all_runs)
    except Exception:  # a dashboard must render even when the analysis cannot
        findings = []
    try:
        findings += perf_findings(perf)
    except Exception:
        pass
    subtitle = (
        f"Last run {local_time(latest['started'])} on {latest['env']}" if latest else "No runs recorded yet"
    )

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>QA dashboard</title><style>{CSS}</style></head><body>
<header><h1>QA DASHBOARD</h1><p>{html.escape(subtitle)}</p></header>
<main>
<section>{heading("At a glance")}{cards(runs, items, perf)}</section>
<section>{heading("Regression against earlier runs")}{findings_list(findings)}</section>
<section>{heading("Pass rate")}{sparkline(runs)}</section>
<section>{heading("The last run, by group")}{groups_table(latest)}</section>
<section>{heading("Tests that fail most often")}{instability_table(instability(all_runs), len(all_runs))}</section>
<section>{heading("Load: the latest run of each shape")}{perf_latest_table(perf)}</section>
<section>{heading("Load: p95 over time")}{perf_trend_panel(perf)}</section>
<section>{heading("Load: slowest endpoints")}{endpoints_table(slowest_endpoints(perf))}</section>
<section>{heading("What is left on each environment")}{env_table(artifacts_by_env(items))}</section>
<section>{heading("Runs")}{runs_table(runs)}</section>
<section>{heading("Load runs")}{perf_runs_table(tail(perf, run_limit))}</section>
<section>{heading("Objects created by the tests")}{artifacts_table(items)}</section>
</main></body></html>"""

    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / "dashboard.html"
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=25, help="how many recent runs to show")
    parser.add_argument("--tz", help="display timezone, e.g. Asia/Jerusalem (default: this machine's)")
    args = parser.parse_args()
    if args.tz:
        DISPLAY_TZ = ZoneInfo(args.tz)  # noqa: F841 - set before build reads it
        globals()["DISPLAY_TZ"] = ZoneInfo(args.tz)
    print(f"dashboard written to {build(run_limit=args.runs)}")
