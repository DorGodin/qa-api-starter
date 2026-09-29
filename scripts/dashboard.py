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

HEBREW = {
    "At a glance": "מבט מהיר",
    "Runs": "ריצות",
    "Objects created by the tests": "אובייקטים שהבדיקות יצרו",
}
COLUMN_HE = {
    "When": "מתי", "Env": "סביבה", "Verdict": "תוצאה", "Pass": "עברו", "Fail": "נכשלו",
    "Skip": "דולגו", "Time": "משך", "Groups": "קבוצות", "Resource": "משאב", "Id": "מזהה",
    "Created as": "נוצר בתור", "By test": "על ידי הטסט",
}


def local_time(value: str) -> str:
    """UTC in the file, the reader's clock on the screen, with the zone named."""
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return value.replace("T", " ")[:16]
    local = moment.astimezone(DISPLAY_TZ) if DISPLAY_TZ else moment.astimezone()
    return f"{local:%Y-%m-%d %H:%M} {local:%Z}".strip()


def heading(title: str) -> str:
    hebrew = HEBREW.get(title, "")
    suffix = f'<span dir="rtl" class="he">({html.escape(hebrew)})</span>' if hebrew else ""
    return f"<h2>{html.escape(title)}{suffix}</h2>"


def column(title: str) -> str:
    hebrew = COLUMN_HE.get(title, "")
    suffix = f'<span dir="rtl" class="he">({html.escape(hebrew)})</span>' if hebrew else ""
    return f"<th>{html.escape(title)}{suffix}</th>"

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
.he{display:block;color:#7b8794;font-weight:400;letter-spacing:0;text-transform:none;
    font-size:12px;unicode-bidi:isolate;margin-top:2px;text-align:left}
th .he{font-size:11px;margin-top:1px}
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
            f"<td>{html.escape(local_time(run['started']))}</td>"
            f"<td><code>{html.escape(run['env'])}</code></td>"
            f"<td class='{verdict_class(run['verdict'])}'>{html.escape(run['verdict'])}</td>"
            f"<td>{run['passed']}</td><td>{run['failed']}</td><td>{run['skipped']}</td>"
            f"<td>{bar(run['passed'], run['failed'], run['skipped'])}</td>"
            f"<td>{run['duration']}s</td><td>{html.escape(groups)}</td>"
            "</tr>"
        )
    header = "".join(column(name) for name in
                     ("When", "Env", "Verdict", "Pass", "Fail", "Skip")) + "<th></th>" + \
        "".join(column(name) for name in ("Time", "Groups"))
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
    header = "".join(column(name) for name in
                     ("Resource", "Id", "Env", "Created as", "By test", "When"))
    return f"<table><tr>{header}</tr>" + "".join(rows) + "</table>"


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
        f"Last run {local_time(latest['started'])} on {latest['env']}"
        if latest
        else "No runs recorded yet"
    )

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>QA dashboard</title><style>{CSS}</style></head><body>
<header><h1>QA DASHBOARD</h1><p>{html.escape(subtitle)}</p></header>
<main>
<section>{heading("At a glance")}{cards(runs, items)}</section>
<section>{heading("Runs")}{runs_table(runs)}</section>
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
