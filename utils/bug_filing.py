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


def build_title(failure: Failure, prefix: str = "BE") -> str:
    """Name the defect, not the area. The reader should know what broke."""
    first_line = failure.message.strip().splitlines()[0] if failure.message.strip() else "assertion failed"
    return f"{prefix} - {failure.test_name}: {first_line}"[:200]


def build_description(failure: Failure, run_url: str | None = None) -> str:
    lines = [
        "*TL;DR for product / non-engineers*",
        f"An automated check named {failure.test_name} failed. "
        "The behaviour below is what the product did, not what it should do.",
        "",
        "*Evidence*",
        "{code}",
        failure.message.strip() or "(no message captured)",
        "{code}",
        "",
        "*Notes*",
        f"Test: {failure.nodeid}",
        f"Area: {failure.area}",
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
    title_prefix: str = "BE",
    run_url: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project": project,
        "issuetype": "Bug",
        "summary": build_title(failure, title_prefix),
        "description": build_description(failure, run_url),
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
    title_prefix: str = "BE",
    run_url: str | None = None,
    dry_run: bool = False,
) -> list[Action]:
    """One ticket per failing test, deduplicated on the test nodeid.

    A re-run of an already reported failure comments on the open ticket instead
    of opening a second one.
    """
    actions: list[Action] = []
    for failure in failures:
        payload = build_payload(failure, project, routing, title_prefix, run_url)
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
