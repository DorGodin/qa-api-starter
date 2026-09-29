"""Run level bug filing.

A test asserts; the run reports. Nothing here is called from inside a test, and
nothing files anything unless the run was started with --file-bugs.

The tracker is a protocol so the suite never depends on one vendor, and so the
unit tests can exercise every path without a network.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

MARKER_PREFIX = "qa-autofile"
MARKER_RE = re.compile(rf"{MARKER_PREFIX}:(?P<nodeid>\S+)")


@dataclass(frozen=True)
class Failure:
    """One failed test, reduced to what a tracker needs."""

    nodeid: str
    message: str
    duration: float = 0.0

    @property
    def test_name(self) -> str:
        return self.nodeid.rsplit("::", 1)[-1]

    @property
    def area(self) -> str:
        """Top folder under tests/, used for routing. `tests/suites/x.py` -> `suites`."""
        path = self.nodeid.split("::", 1)[0]
        parts = [p for p in path.split("/") if p]
        return parts[1] if len(parts) > 1 else "unknown"


@dataclass(frozen=True)
class Action:
    kind: str  # "create" | "comment" | "skip"
    nodeid: str
    key: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class Tracker(Protocol):
    def search(self, marker: str) -> list[dict[str, Any]]: ...
    def create(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def comment(self, key: str, body: str) -> dict[str, Any]: ...


def marker_for(nodeid: str) -> str:
    return f"{MARKER_PREFIX}:{nodeid}"


def humanise(test_name: str) -> str:
    """`test_submitting_draws_from_budget` -> `Submitting draws from budget`.

    A test name is the closest thing to a stated expectation that a filer can
    read without guessing, so it becomes the expected result, labelled as
    derived rather than presented as if a person wrote it.
    """
    words = test_name.removeprefix("test_").replace("_", " ").strip()
    return words[:1].upper() + words[1:] if words else ""


FRONTEND_AREAS = {"ui"}


def prefix_for(failure: Failure) -> str:
    """A browser test failing is a front end finding; everything else is back end.

    The prefix routes the ticket, so it is derived rather than typed.
    """
    return "FE" if failure.area in FRONTEND_AREAS else "BE"


def assertion_line(message: str) -> str:
    """The assertion pytest reported, without its `E` gutter marker."""
    for line in (message or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("E "):
            return stripped[1:].strip()
    for line in (message or "").splitlines():
        if line.strip():
            return line.strip()
    return "assertion failed"


def build_title(failure: Failure, prefix: str | None = None) -> str:
    """Name the defect in words, then the mismatch.

    `test_submitting_draws_from_budget` says more about what broke than the
    traceback does, so it leads.
    """
    prefix = prefix or prefix_for(failure)
    return f"{prefix} - {humanise(failure.test_name)}: {assertion_line(failure.message)}"[:200]


def command_for(failure: Failure, env: str | None = None) -> str:
    """The exact command that reproduces this one failure, flag and env included."""
    flags = {"unit": "--unit", "edge-cases": "--edge-cases", "ui": "--ui",
             "llm": "--llm", "security": "--security"}
    flag = flags.get(failure.area)
    return f"ENV={env or '<env>'} pytest {flag + ' ' if flag else ''}{failure.nodeid}"


def build_description(
    failure: Failure,
    run_url: str | None = None,
    env: str | None = None,
    platform: str | None = None,
) -> str:
    """The team's bug template, filled with what the run actually knows.

    Anything the run cannot know is marked for a person to complete, never
    invented.
    """
    environment = " · ".join(part for part in (env, platform) if part) or "(env unknown)"
    evidence = failure.message.strip() or "(no message captured)"

    lines = [
        "*ENV(+mobile type):*",
        environment,
        "",
        "*Precondition:*",
        f"The state the test builds for itself. See {failure.nodeid}.",
        "",
        "*Steps to reproduce:*",
        f"# {command_for(failure, env)}",
        "# The failure below reproduces from a clean state.",
        "",
        "*Actual result:*",
        assertion_line(failure.message),
        "{code}",
        evidence,
        "{code}",
        "",
        "*Expected result:*",
        f"{humanise(failure.test_name)} _(derived from the test name - confirm before sending)_",
        "",
        "*Notes:*",
        "Video\\image\\api\\console error attached",
        "Opened automatically from a failed run.",
        f"Test: {failure.nodeid}",
    ]
    if run_url:
        lines.append(f"Run: {run_url}")
    lines += ["", f"_{marker_for(failure.nodeid)}_"]
    return "\n".join(lines)


def route(failure: Failure, routing: dict[str, str] | None) -> str | None:
    """Pick an assignee from the area. Unknown areas stay unassigned on purpose."""
    if not routing:
        return None
    return routing.get(failure.area) or routing.get("*")


def build_payload(
    failure: Failure,
    project: str,
    routing: dict[str, str] | None = None,
    title_prefix: str | None = None,
    run_url: str | None = None,
    env: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project": project,
        "issuetype": "Bug",
        "summary": build_title(failure, title_prefix),
        "description": build_description(failure, run_url, env=env, platform=platform),
    }
    assignee = route(failure, routing)
    if assignee:
        payload["assignee"] = assignee
    return payload


def file_failures(
    failures: Iterable[Failure],
    tracker: Tracker,
    project: str,
    routing: dict[str, str] | None = None,
    title_prefix: str | None = None,
    run_url: str | None = None,
    env: str | None = None,
    platform: str | None = None,
    dry_run: bool = False,
) -> list[Action]:
    """One ticket per failing test, deduplicated on the test nodeid.

    A re-run of an already reported failure comments on the open ticket instead
    of opening a second one.
    """
    actions: list[Action] = []
    for failure in failures:
        payload = build_payload(failure, project, routing, title_prefix, run_url, env, platform)
        existing = tracker.search(marker_for(failure.nodeid))

        if dry_run:
            kind = "comment" if existing else "create"
            key = existing[0]["key"] if existing else None
            actions.append(Action(kind=f"dry-run:{kind}", nodeid=failure.nodeid, key=key, payload=payload))
            continue

        if existing:
            key = existing[0]["key"]
            tracker.comment(key, f"Still failing on a later run.\n\n_{marker_for(failure.nodeid)}_")
            actions.append(Action(kind="comment", nodeid=failure.nodeid, key=key))
        else:
            created = tracker.create(payload)
            actions.append(Action(kind="create", nodeid=failure.nodeid, key=created.get("key"), payload=payload))
    return actions


def format_report(actions: list[Action]) -> str:
    if not actions:
        return "bug filing: nothing to report"
    rows = [f"  {a.kind:<18} {a.key or '-':<10} {a.nodeid}" for a in actions]
    return "bug filing:\n" + "\n".join(rows)


class JiraTracker:
    """Minimal Jira REST client. Credentials come from the environment, never from code."""

    def __init__(self, base_url: str | None = None, email: str | None = None, token: str | None = None):
        import requests

        self.base_url = (base_url or os.environ["TRACKER_URL"]).rstrip("/")
        self.auth = (email or os.environ["TRACKER_EMAIL"], token or os.environ["TRACKER_TOKEN"])
        self._session = requests.Session()

    def _call(self, method: str, path: str, **kwargs):
        resp = self._session.request(method, f"{self.base_url}{path}", auth=self.auth, timeout=30, **kwargs)
        if not resp.ok:
            raise RuntimeError(f"tracker {method} {path} -> {resp.status_code}: {resp.text[:300]}")
        return resp.json() if resp.content else {}

    def search(self, marker: str) -> list[dict[str, Any]]:
        jql = f'text ~ "{marker}" AND statusCategory != Done'
        return self._call("GET", "/rest/api/3/search", params={"jql": jql, "maxResults": 5}).get("issues", [])

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        fields = {
            "project": {"key": payload["project"]},
            "issuetype": {"name": payload["issuetype"]},
            "summary": payload["summary"],
            "description": payload["description"],
        }
        if "assignee" in payload:
            fields["assignee"] = {"accountId": payload["assignee"]}
        return self._call("POST", "/rest/api/3/issue", json={"fields": fields})

    def comment(self, key: str, body: str) -> dict[str, Any]:
        return self._call("POST", f"/rest/api/3/issue/{key}/comment", json={"body": body})
