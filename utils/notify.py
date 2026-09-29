"""Tell a channel what the run did.

Short enough to read without opening anything, specific enough to act on. The
sender is injected so the message can be tested without a network, and the whole
thing is off unless a run asks for it.
"""
from __future__ import annotations

from typing import Callable, Protocol

MAX_FAILURES_LISTED = 5


class Report(Protocol):
    env: str

    @property
    def verdict(self) -> str: ...
    @property
    def counts(self) -> dict[str, int]: ...
    def failures(self) -> list: ...
    def skips(self) -> list: ...


ICON = {"PASSED": "✅", "PASSED WITH SKIPS": "⚠️", "FAILED": "❌", "NO TESTS RAN": "❌"}


def build_message(report: Report, run_url: str | None = None, findings: list | None = None) -> str:
    counts = report.counts
    lines = [
        f"{ICON.get(report.verdict, '•')} *{report.verdict}* on `{report.env}`",
        f"{counts['passed']} passed · {counts['failed']} failed · {counts['skipped']} skipped",
    ]

    failures = report.failures()
    if failures:
        lines.append("")
        for failure in failures[:MAX_FAILURES_LISTED]:
            lines.append(f"• `{failure.nodeid}`")
            if getattr(failure, "first_line", ""):
                lines.append(f"    {failure.first_line}")
        if len(failures) > MAX_FAILURES_LISTED:
            lines.append(f"• and {len(failures) - MAX_FAILURES_LISTED} more")

    skips = report.skips()
    if skips:
        lines.append("")
        lines.append(f"{len(skips)} skipped — each one is a question this run did not answer")

    for finding in findings or []:
        lines.append(f"⚑ {finding.kind}: {finding.message}")

    if run_url:
        lines += ["", run_url]
    return "\n".join(lines)


def post(webhook: str, message: str) -> int:
    """Slack and Teams both accept a plain {"text": ...} body."""
    import requests

    response = requests.post(webhook, json={"text": message}, timeout=15)
    if not response.ok:
        raise RuntimeError(f"notification failed: {response.status_code} {response.text[:200]}")
    return response.status_code


def notify(
    report: Report,
    webhook: str | None,
    run_url: str | None = None,
    findings: list | None = None,
    dry_run: bool = False,
    sender: Callable[[str, str], int] = post,
) -> str:
    """Returns the message, and says plainly when nothing was sent."""
    message = build_message(report, run_url, findings)
    if dry_run:
        return message
    if not webhook:
        raise RuntimeError("no webhook configured. Set NOTIFY_WEBHOOK or use the dry run.")
    sender(webhook, message)
    return message
