"""Compare a run against the ones before it.

A single run answers "did it pass". Only the history answers the questions that
actually precede an incident: did a group quietly shrink, did something become
skipped, is this getting slower.
"""

from __future__ import annotations

from dataclasses import dataclass

SLOWER_BY = 0.5  # 50% slower than the baseline median is worth saying out loud
MIN_SECONDS = 1.0  # below this, percentages are noise


@dataclass(frozen=True)
class Finding:
    kind: str
    message: str
    blocking: bool = True


def _comparable(runs: list[dict], latest: dict) -> list[dict]:
    """Runs worth judging this one against: same environment, same groups.

    Comparing a targeted run against a full one always "finds" a missing group,
    which trains everyone to ignore the check. A run with no comparable history
    is reported as such rather than measured against something else.
    """
    env, groups = latest.get("env"), set(latest.get("groups", {}))
    return [run for run in runs if run.get("env") == env and set(run.get("groups", {})) == groups]


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def compare(history: list[dict], baseline_size: int = 5) -> list[Finding]:
    """Findings about the last run, judged against earlier runs on the same environment."""
    if not history:
        return []

    latest = history[-1]
    baseline = _comparable(history[:-1], latest)[-baseline_size:]
    findings: list[Finding] = []

    if latest.get("verdict") == "NO TESTS RAN":
        findings.append(Finding("no-tests", "the run collected no tests at all"))

    if not baseline:
        findings.append(
            Finding("no-baseline", "no earlier run with the same groups on this environment", blocking=False)
        )
        return findings

    latest_groups = latest.get("groups", {})
    for name, counts in (baseline[-1].get("groups", {}) or {}).items():
        was = sum(counts.values())
        now = sum((latest_groups.get(name) or {}).values())
        if now < was:
            findings.append(Finding("group-shrank", f"group '{name}' went from {was} tests to {now}"))

    new_skips = set(latest.get("skipped_tests", [])) - set(baseline[-1].get("skipped_tests", []))
    for nodeid in sorted(new_skips):
        findings.append(Finding("new-skip", f"newly skipped: {nodeid}"))

    durations = [run.get("duration", 0.0) for run in baseline]
    typical, now = _median(durations), latest.get("duration", 0.0)
    if typical >= MIN_SECONDS and now > typical * (1 + SLOWER_BY):
        findings.append(
            Finding("slower", f"took {now:.1f}s against a typical {typical:.1f}s", blocking=False)
        )

    if latest.get("failed", 0) and not baseline[-1].get("failed", 0):
        findings.append(Finding("newly-failing", f"{latest['failed']} test(s) failed and none did last run"))

    return findings


def format_findings(findings: list[Finding]) -> str:
    if not findings:
        return "no regression against the previous runs"
    lines = ["regression check:"]
    for finding in findings:
        mark = "!" if finding.blocking else "-"
        lines.append(f"  {mark} {finding.kind}: {finding.message}")
    return "\n".join(lines)


def blocking(findings: list[Finding]) -> bool:
    return any(finding.blocking for finding in findings)
