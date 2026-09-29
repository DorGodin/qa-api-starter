from __future__ import annotations

import os
from pathlib import Path

import pytest

from config.loader import load_env_config
from obj import ApiClient, Assistant, Items, Orders
from utils.bug_filing import Failure, JiraTracker, file_failures, format_report

GATED = {
    "tests/unit": "--unit",
    "tests/edge-cases": "--edge-cases",
    "tests/ui": "--ui",
    "tests/llm": "--llm",
}
PASSWORDS = {"admin": "admin-secret", "member": "member-secret"}


def pytest_addoption(parser):
    parser.addoption("--unit", action="store_true", default=False, help="collect tests/unit")
    parser.addoption("--edge-cases", action="store_true", default=False, help="collect tests/edge-cases")
    parser.addoption("--ui", action="store_true", default=False, help="collect tests/ui (browser)")
    parser.addoption("--llm", action="store_true", default=False, help="collect tests/llm (LLM evaluation)")
    parser.addoption("--file-bugs", action="store_true", default=False, help="open a ticket per failed test")
    parser.addoption("--file-bugs-dry-run", action="store_true", default=False, help="print the payloads, create nothing")


def pytest_ignore_collect(collection_path: Path, config):
    rel = collection_path.as_posix()
    for folder, flag in GATED.items():
        if f"/{folder}/" in f"{rel}/" or rel.endswith(folder):
            return not config.getoption(flag.lstrip("-").replace("-", "_"))
    return False


def _only_unit(config) -> bool:
    targets = config.args or []
    return bool(targets) and all("tests/unit" in str(t) for t in targets)


@pytest.fixture(scope="session")
def env_config():
    return load_env_config()


@pytest.fixture(scope="session")
def api(request, env_config):
    """Session client with both personas registered.

    Fails fast and loudly: a broken environment must not surface later as a
    confusing assertion inside a test.
    """
    if _only_unit(request.config):
        pytest.skip("unit-only run does not need the API")

    client = ApiClient()
    try:
        health = client.request("GET", "/health", persona=None)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"cannot reach {client.base_url} (ENV={env_config['env']}). "
            "Start it with `make api` or point ENV at a running environment."
        ) from exc
    if health.status_code != 200:
        raise RuntimeError(f"health check on {client.base_url} returned {health.status_code}")

    for persona in ("admin", "member"):
        client.register_persona(persona, env_config[f"{persona}_user"], PASSWORDS[persona])
    return client


@pytest.fixture(scope="session")
def items(api):
    return Items(api)


@pytest.fixture(scope="session")
def orders(api):
    return Orders(api)


@pytest.fixture(scope="session")
def assistant(api):
    return Assistant(api)


@pytest.fixture(scope="module", autouse=True)
def _clean_state(request):
    """Reset once per module so an ordered flow keeps its state, and modules
    never leak into each other."""
    if "api" not in getattr(request, "fixturenames", []):
        return
    request.getfixturevalue("api").request("POST", "/_test/reset", persona="admin").assert_ok(204)


@pytest.fixture
def fresh_state(api):
    """Opt in to a pristine environment for one test.

    The module scoped reset above keeps an ordered flow's state alive, which is
    what a flow needs and exactly what a test asserting an absolute value cannot
    tolerate. A module whose tests each need a clean slate declares
    `pytestmark = pytest.mark.usefixtures("fresh_state")`.
    """
    api.request("POST", "/_test/reset", persona="admin").assert_ok(204)


@pytest.fixture(scope="module")
def ctx():
    """Shared state for ordered tests inside one module."""
    return {}


# --- run level bug filing -------------------------------------------------
# A test asserts, the run reports. Both flags are off by default, so a normal
# run and CI file nothing.

_FAILURES: list[Failure] = []


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    report = (yield).get_result()
    if report.when == "call" and report.failed:
        _FAILURES.append(
            Failure(nodeid=report.nodeid, message=str(report.longrepr), duration=report.duration)
        )


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    dry_run = config.getoption("file_bugs_dry_run")
    if not (config.getoption("file_bugs") or dry_run) or not _FAILURES:
        return

    project = os.getenv("TRACKER_PROJECT", "QA")
    routing = {"suites": os.getenv("TRACKER_ASSIGNEE_SUITES", ""), "edge-cases": os.getenv("TRACKER_ASSIGNEE_EDGE", "")}
    routing = {k: v for k, v in routing.items() if v}

    if dry_run:
        actions = file_failures(_FAILURES, _NullTracker(), project, routing, dry_run=True)
    else:
        actions = file_failures(_FAILURES, JiraTracker(), project, routing, run_url=os.getenv("CI_RUN_URL"))

    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line("")
        reporter.write_line(format_report(actions))


class _NullTracker:
    """Dry run only: answers as if nothing had ever been filed."""

    def search(self, marker):
        return []

    def create(self, payload):  # pragma: no cover - never reached in a dry run
        raise AssertionError("dry run must not create")

    def comment(self, key, body):  # pragma: no cover - never reached in a dry run
        raise AssertionError("dry run must not comment")
