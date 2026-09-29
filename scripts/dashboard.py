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
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.artifacts import load, tail  # noqa: E402

REPORTS = Path(__file__).resolve().parents[1] / "reports"

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
td{padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
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
"""


def verdict_class(verdict: str) -> str:
    return {"PASSED": "ok", "FAILED": "bad", "NO TESTS RAN": "bad"}.get(verdict, "warn")


def bar(passed: int, failed: int, skipped: int) -> str:
    total = max(passed + failed + skipped, 1)
    parts = [("p", passed), ("f", failed), ("s", skipped)]
    return '<div class="bar">' + "".join(
        f'<span class="{cls}" style="width:{count / total * 100:.1f}%"></span>' for cls, count in parts
    ) + "</div>"


def runs_table(runs: list[dict]) -> str:
    if not runs:
        return '<p class="empty">No runs recorded yet.</p>'
    rows = []
    for run in reversed(runs):
        groups = ", ".join(run.get("groups", {})) or "—"
        rows.append(
            "<tr>"
            f"<td>{html.escape(run['started'].replace('T', ' ')[:16])}</td>"
            f"<td><code>{html.escape(run['env'])}</code></td>"
            f"<td class='{verdict_class(run['verdict'])}'>{html.escape(run['verdict'])}</td>"
            f"<td>{run['passed']}</td><td>{run['failed']}</td><td>{run['skipped']}</td>"
            f"<td>{bar(run['passed'], run['failed'], run['skipped'])}</td>"
            f"<td>{run['duration']}s</td><td>{html.escape(groups)}</td>"
            "</tr>"
        )
    return (
        "<table><tr><th>When (UTC)</th><th>Env</th><th>Verdict</th><th>Pass</th><th>Fail</th>"
        "<th>Skip</th><th></th><th>Time</th><th>Groups</th></tr>" + "".join(rows) + "</table>"
    )


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
        f"<td>{html.escape(item['created_at'].replace('T', ' ')[:16])}</td>"
        "</tr>"
        for item in reversed(items[-limit:])
    ]
    return (
        "<table><tr><th>Resource</th><th>Id</th><th>Env</th><th>Created as</th><th>By test</th>"
        "<th>When (UTC)</th></tr>" + "".join(rows) + "</table>"
    )


def cards(runs: list[dict], items: list[dict]) -> str:
    by_resource = Counter(item["resource"] for item in items)
    latest = runs[-1] if runs else None
    tiles = [
        ("Runs recorded", len(runs)),
        ("Objects created", len(items)),
        ("Environments", len({item["env"] for item in items} | {run["env"] for run in runs})),
    ]
    tiles += [(f"{resource} created", count) for resource, count in by_resource.most_common(3)]
    if latest:
        tiles.insert(0, ("Last verdict", latest["verdict"]))
    return '<div class="cards">' + "".join(
        f'<div class="card"><b>{html.escape(str(value))}</b><span>{html.escape(label)}</span></div>'
        for label, value in tiles
    ) + "</div>"


def build(reports_dir: Path = REPORTS, run_limit: int = 25) -> Path:
    runs = tail(load(reports_dir / "history.jsonl"), run_limit)
    items = load(reports_dir / "artifacts.jsonl")
    latest = runs[-1] if runs else None
    subtitle = (
        f"Last run {latest['started'].replace('T', ' ')[:16]} UTC on {latest['env']}"
        if latest
        else "No runs recorded yet"
    )

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>QA dashboard</title><style>{CSS}</style></head><body>
<header><h1>QA DASHBOARD</h1><p>{html.escape(subtitle)}</p></header>
<main>
<section><h2>At a glance</h2>{cards(runs, items)}</section>
<section><h2>Runs</h2>{runs_table(runs)}</section>
<section><h2>Objects created by the tests</h2>{artifacts_table(items)}</section>
</main></body></html>"""

    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / "dashboard.html"
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=25, help="how many recent runs to show")
    args = parser.parse_args()
    print(f"dashboard written to {build(run_limit=args.runs)}")
