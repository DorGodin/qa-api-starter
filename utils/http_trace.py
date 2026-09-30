"""What the failing test actually did, in order.

Steps to reproduce are the point of a bug report, and a command that runs a test
is not a step — it tells a developer to install the suite before they can look at
the defect. Every call goes through `ApiClient.request`, so the real sequence is
already passing through one place.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_STEPS = 25

# Calls the harness makes, not the user. Registering a persona and resetting the
# environment are how the suite gets to the starting line; neither belongs in a
# report a developer is meant to follow.
HARNESS_PATHS = ("/auth/token", "/_test/")


@dataclass(frozen=True)
class Call:
    method: str
    path: str
    status: int
    persona: str | None = None

    def as_step(self) -> str:
        who = f" as {self.persona}" if self.persona else ""
        return f"{self.method} {self.path}{who} -> {self.status}"


_calls: dict[str, list[Call]] = {}


def record(test: str, call: Call) -> None:
    calls = _calls.setdefault(test, [])
    if len(calls) < MAX_STEPS:
        calls.append(call)


def is_harness(call: Call) -> bool:
    return call.path.startswith(HARNESS_PATHS)


def steps_for(test: str, include_harness: bool = False) -> list[str]:
    calls = _calls.get(test, [])
    if not include_harness:
        calls = [call for call in calls if not is_harness(call)]
    return [call.as_step() for call in calls]


def reset(test: str) -> None:
    """A test reproduces from its own calls, never from the previous test's."""
    _calls.pop(test, None)


def clear() -> None:
    _calls.clear()
