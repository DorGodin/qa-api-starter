"""One report per run, in the same shape every time.

A run that only prints to a terminal is gone when the terminal is. This writes
what someone would actually ask afterwards: what failed, what was skipped and
why, what is getting slow, and which environment it ran against.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

GROUP_ORDER = ("suites", "unit", "edge-cases", "security", "ui", "llm", "other")


@dataclass
class TestOutcome:
    nodeid: str
    outcome: str  # passed | failed | skipped
    duration: float = 0.0
    message: str = ""

    @property
    def group(self) -> str:
        parts = self.nodeid.split("::", 1)[0].split("/")
        return parts[1] if len(parts) > 1 and parts[1] in GROUP_ORDER else "other"

    @property
    def first_line(self) -> str:
        """The assertion, not the source line above it.

        pytest's longrepr starts with the function under test, so taking the
        first non-empty line reports `def test_x():` and tells nobody anything.
        The error itself is on the lines pytest marks with `E`.
        """
        lines = [line.rstrip() for line in (self.message or "").splitlines()]
        errors = [line.strip()[1:].strip() for line in lines if line.strip().startswith("E ")]
        if errors:
            return errors[0][:160]
        for line in lines:
            if line.strip():
                return line.strip()[:160]
        return ""


@dataclass
class RunReport:
    env: str
    outcomes: list[TestOutcome] = field(default_factory=list)
    started: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add(self, outcome: TestOutcome) -> None:
        self.outcomes.append(outcome)

    @property
    def counts(self) -> dict[str, int]:
        counts = {"passed": 0, "failed": 0, "skipped": 0}
        for outcome in self.outcomes:
            counts[outcome.outcome] = counts.get(outcome.outcome, 0) + 1
        return counts

    @property
    def duration(self) -> float:
        return sum(o.duration for o in self.outcomes)

    def by_group(self) -> dict[str, dict[str, int]]:
        groups: dict[str, dict[str, int]] = {}
        for outcome in self.outcomes:
            bucket = groups.setdefault(outcome.group, {"passed": 0, "failed": 0, "skipped": 0})
            bucket[outcome.outcome] = bucket.get(outcome.outcome, 0) + 1
        return {name: groups[name] for name in GROUP_ORDER if name in groups}

    def failures(self) -> list[TestOutcome]:
        return [o for o in self.outcomes if o.outcome == "failed"]

    def skips(self) -> list[TestOutcome]:
        return [o for o in self.outcomes if o.outcome == "skipped"]

    def slowest(self, limit: int = 5) -> list[TestOutcome]:
        return sorted(self.outcomes, key=lambda o: o.duration, reverse=True)[:limit]

    @property
    def verdict(self) -> str:
        if self.failures():
            return "FAILED"
        return "PASSED WITH SKIPS" if self.skips() else "PASSED"

    def to_markdown(self) -> str:
        counts = self.counts
        lines = [
            f"# Run report — {self.verdict}",
            "",
            f"**Environment:** `{self.env}`  ·  **When:** {self.started:%Y-%m-%d %H:%M UTC}  "
            f"·  **Duration:** {self.duration:.2f}s",
            "",
            f"**{counts['passed']} passed · {counts['failed']} failed · {counts['skipped']} skipped**",
            "",
            "## By group",
            "",
            "| Group | Passed | Failed | Skipped |",
            "|---|---|---|---|",
        ]
        for name, bucket in self.by_group().items():
            lines.append(f"| {name} | {bucket['passed']} | {bucket['failed']} | {bucket['skipped']} |")

        if self.failures():
            lines += ["", "## Failures", ""]
            for outcome in self.failures():
                lines.append(f"- `{outcome.nodeid}`")
                if outcome.first_line:
                    lines.append(f"  - {outcome.first_line}")
        else:
            lines += ["", "## Failures", "", "None."]

        lines += ["", "## Skips", ""]
        if self.skips():
            lines.append("Each skip is a question this run did not answer.")
            lines.append("")
            for outcome in self.skips():
                reason = outcome.first_line or "no reason recorded"
                lines.append(f"- `{outcome.nodeid}` — {reason}")
        else:
            lines.append("None.")

        lines += ["", "## Slowest", "", "| Test | Seconds |", "|---|---|"]
        for outcome in self.slowest():
            lines.append(f"| `{outcome.nodeid}` | {outcome.duration:.2f} |")

        lines.append("")
        return "\n".join(lines)

    def write(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "last-run.md"
        path.write_text(self.to_markdown(), encoding="utf-8")
        return path
