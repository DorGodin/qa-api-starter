"""Turn a k6 summary into one line of history, and read those lines back.

A single load run answers "is it fast enough right now". Only the history
answers the question that actually costs a release: is p95 creeping up? A 4%
climb per week never breaches a threshold and is invisible in any one run.

Two things about k6's summary export are worth knowing before reading this,
because both are easy to get backwards:

1. A threshold's boolean is TRUE when the threshold was CROSSED - that is, when
   it FAILED. `{"p(95)<400": false}` means the run was fine. The whole file
   normalises this once, in `_breached`, so nothing downstream has to remember
   it.
2. The export carries `setup_data`, which for the write path holds the member's
   bearer token. Only the fields named below are ever recorded, so the token
   never reaches a report, a dashboard, or an attachment.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ENDPOINT = re.compile(r"^http_req_duration\{name:(?P<name>.+)\}$")

# Trend stats k6 does not compute unless asked. p(99) is in the thresholds, so
# it has to be in the summary too or the history records it as missing.
TREND_STATS = "avg,min,med,max,p(90),p(95),p(99)"


@dataclass(frozen=True)
class PerfFinding:
    kind: str
    message: str
    blocking: bool


def _breached(metric: dict[str, Any]) -> list[str]:
    """The expressions this metric crossed. True means crossed - see the note above."""
    return [expr for expr, crossed in (metric.get("thresholds") or {}).items() if crossed]


def _round(value: Any, digits: int = 2) -> Any:
    return round(value, digits) if isinstance(value, (int, float)) else value


def normalise(
    summary: dict[str, Any],
    *,
    scenario: str,
    profile: str,
    env: str,
    base_url: str,
    started: str,
    duration: float,
    exit_code: int,
) -> dict[str, Any]:
    """One history row. Nothing from `setup_data` is carried across."""
    metrics = summary.get("metrics", {})

    def value(name: str, key: str, default: Any = None) -> Any:
        return metrics.get(name, {}).get(key, default)

    endpoints = {}
    for key, metric in metrics.items():
        match = ENDPOINT.match(key)
        if match is None:
            continue
        endpoints[match.group("name")] = {
            stat: _round(metric.get(stat)) for stat in ("avg", "med", "p(95)", "p(99)", "max")
        }

    breached = sorted(f"{name} {expr}" for name, metric in metrics.items() for expr in _breached(metric))

    return {
        "started": started,
        "scenario": scenario,
        "profile": profile,
        "env": env,
        "base_url": base_url,
        "duration": round(duration, 2),
        "vus_max": value("vus_max", "value"),
        "iterations": value("iterations", "count"),
        "requests": value("http_reqs", "count"),
        "rps": _round(value("http_reqs", "rate")),
        "error_rate": _round(value("http_req_failed", "value", 0.0), 4),
        "checks_rate": _round(value("checks", "value"), 4),
        "p95": _round(value("http_req_duration", "p(95)")),
        "p99": _round(value("http_req_duration", "p(99)")),
        "avg": _round(value("http_req_duration", "avg")),
        "max": _round(value("http_req_duration", "max")),
        "endpoints": endpoints,
        # The correctness gates. They are the reason this is a test and not a
        # benchmark, so they are recorded by name even when they are zero.
        "wrong_totals": value("wrong_totals", "count"),
        "budget_rejections": value("budget_rejections", "count"),
        "server_errors": _round(value("server_errors", "value"), 4),
        "breached": breached,
        "exit_code": exit_code,
        "verdict": "PASSED" if not breached and exit_code == 0 else "THRESHOLDS BREACHED",
    }


def append(row: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def shape(row: dict) -> tuple:
    """What makes two runs comparable. Defined once, because the trend check and
    the dashboard lines must agree on it.

    VUs are part of the shape: p95 at 25 users against p95 at 4 users is the
    load level, not a regression. Leaving them out made the first version of
    this report a 31% "rise" that was nothing but a bigger run.
    """
    return (row.get("scenario"), row.get("profile"), row.get("env"), row.get("vus_max"))


def _at(latest: dict) -> str:
    """ " at 4 VUs", or nothing: k6 samples vus_max about once a second, so a run
    shorter than that - the smoke test - never records one."""
    vus = latest.get("vus_max")
    return f" at {vus} VUs" if vus is not None else ""


def comparable(history: list[dict], latest: dict) -> list[dict]:
    """Earlier runs of the same shape that are fit to be a baseline.

    A run that crossed a threshold is left out. Its latency is not a
    measurement of the product: the write path returns early when a total is
    wrong, so a broken run looks fast, and would make the next healthy run
    look like a regression.
    """
    return [row for row in history if shape(row) == shape(latest) and not row.get("breached")]


def compare(history: list[dict], baseline_size: int = 5, tolerance: float = 0.25) -> list[PerfFinding]:
    """What changed against recent runs of the same shape.

    Latency is noisy, so a single slower run is not a finding - the baseline is
    a median of several, and the tolerance is wide. A check that fires on normal
    variance is a check people learn to ignore.
    """
    if not history:
        return [PerfFinding("empty", "No perf run has been recorded yet.", blocking=False)]

    latest = history[-1]
    findings = []

    for expr in latest.get("breached", []):
        findings.append(
            PerfFinding(
                "threshold", f"{latest['scenario']}/{latest['profile']} crossed {expr}", blocking=True
            )
        )

    baseline = comparable(history[:-1], latest)[-baseline_size:]
    if not baseline:
        findings.append(
            PerfFinding(
                "no-baseline",
                f"No earlier healthy {latest['scenario']}/{latest['profile']} run"
                f"{_at(latest)} on {latest['env']} to compare against.",
                blocking=False,
            )
        )
        return findings

    previous = sorted(row["p95"] for row in baseline if isinstance(row.get("p95"), (int, float)))
    if not previous or not isinstance(latest.get("p95"), (int, float)):
        return findings

    median = previous[len(previous) // 2]
    if median > 0 and latest["p95"] > median * (1 + tolerance):
        findings.append(
            PerfFinding(
                "p95-rise",
                f"{latest['scenario']}/{latest['profile']} p95 is {latest['p95']}ms against {median}ms across the previous "
                f"{len(baseline)} runs{_at(latest)}, a {latest['p95'] / median - 1:.0%} rise.",
                blocking=False,
            )
        )
    return findings


def format_findings(findings: list[PerfFinding]) -> str:
    if not findings:
        return "no perf regression against the previous runs of the same shape"
    lines = ["perf check:"]
    for finding in findings:
        mark = "!" if finding.blocking else "-"
        lines.append(f"  {mark} {finding.kind}: {finding.message}")
    return "\n".join(lines)


def blocking(findings: list[PerfFinding]) -> bool:
    return any(finding.blocking for finding in findings)
