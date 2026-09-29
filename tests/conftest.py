from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from config.loader import load_env_config
from obj import ApiClient, Assistant, Items, Orders
from utils.bug_filing import Failure, JiraTracker, file_failures, format_report
from utils import http_trace
from utils.artifacts import ArtifactLog, set_current_test
from utils.notify import notify
from utils.run_report import RunReport, TestOutcome
from utils.trends import compare

GATED = {
    "tests/unit": "--unit",
    "tests/edge-cases": "--edge-cases",
    "tests/ui": "--ui",
    "tests/llm": "--llm",
    "tests/security": "--security",
}
PASSWORDS = {"admin": "admin-secret", "member": "member-secret"}


def pytest_addoption(parser):
    parser.addoption("--unit", action="store_true", default=False, help="collect tests/unit")
    parser.addoption("--edge-cases", action="store_true", default=False, help="collect tests/edge-cases")
    parser.addoption("--ui", action="store_true", default=False, help="collect tests/ui (browser)")
    parser.addoption("--llm", action="store_true", default=False, help="collect tests/llm (LLM evaluation)")
    parser.addoption("--security", action="store_true", default=False, help="collect tests/security")
    parser.addoption("--notify", action="store_true", default=False, help="post a run summary to NOTIFY_WEBHOOK")
    parser.addoption("--notify-dry-run", action="store_true", default=False, help="print the summary, send nothing")
    parser.addoption("--file-bugs", action="store_true", default=False, help="open a ticket per failed test")
    parser.addoption("--file-bugs-dry-run", action="store_true", default=False, help="print the payloads, create nothing")


def pytest_ignore_collect(collection_path: Path, config):
    """Ignore a gated folder unless its flag was passed.

    Returns None for everything else. This hook is firstresult: answering False
    means "definitely collect this", which silently overrides pytest's own
    --ignore, --deselect and norecursedirs handling.
    """
    rel = collection_path.as_posix()
    for folder, flag in GATED.items():
        if f"/{folder}/" in f"{rel}/" or rel.endswith(folder):
            if not config.getoption(flag.lstrip("-").replace("-", "_")):
                return True
            return None
    return None


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
def artifact_log(request, env_config):
    log = ArtifactLog(env=env_config["env"])
    request.config._qa_artifact_log = log
    return log


@pytest.fixture(scope="session")
def items(api, artifact_log):
    return Items(api, log=artifact_log)


@pytest.fixture(scope="session")
def orders(api, artifact_log):
    return Orders(api, log=artifact_log)


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
_REPORT = RunReport(env=os.getenv("ENV", "local"))
_REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


def pytest_runtest_setup(item):
    set_current_test(item.nodeid)
    http_trace.reset(item.nodeid)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    report = (yield).get_result()
    if report.when == "call" or (report.when == "setup" and report.skipped):
        _REPORT.add(
            TestOutcome(
                nodeid=report.nodeid,
                outcome=report.outcome,
                duration=getattr(report, "duration", 0.0),
                message=str(report.longrepr) if report.longrepr else "",
            )
        )
    if report.when == "call" and report.failed:
        _FAILURES.append(
            Failure(
                nodeid=report.nodeid,
                message=str(report.longrepr),
                duration=report.duration,
                steps=http_trace.steps_for(report.nodeid),
            )
        )


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    written = _REPORT.write(_REPORTS_DIR)
    _append_history(session)
    _write_artifacts(session)
    _notify(session)
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line(f"run report: {written.relative_to(Path.cwd())}" if written.is_relative_to(Path.cwd()) else f"run report: {written}")

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


def _append_history(session) -> None:
    """One line per run, so a dashboard can show a trend rather than a moment."""
    counts = _REPORT.counts
    entry = {
        "started": _REPORT.started.isoformat(timespec="seconds"),
        "env": _REPORT.env,
        "verdict": _REPORT.verdict,
        "duration": round(_REPORT.duration, 2),
        "groups": _REPORT.by_group(),
        # the ids, not just the count: a skip that appeared is the finding
        "skipped_tests": [o.nodeid for o in _REPORT.skips()],
        **counts,
    }
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with (_REPORTS_DIR / "history.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def _write_artifacts(session) -> None:
    log = session.config._qa_artifact_log if hasattr(session.config, "_qa_artifact_log") else None
    if log is None or not log.items:
        return
    log.append_to(_REPORTS_DIR / "artifacts.jsonl")
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        created = ", ".join(f"{count} {resource}" for resource, count in log.summary().items())
        reporter.write_line(f"created on {log.env}: {created}")


def _notify(session) -> None:
    config = session.config
    dry_run = config.getoption("notify_dry_run")
    if not (config.getoption("notify") or dry_run):
        return

    from utils.artifacts import load

    findings = compare(load(_REPORTS_DIR / "history.jsonl"))
    message = notify(
        _REPORT,
        webhook=os.getenv("NOTIFY_WEBHOOK"),
        run_url=os.getenv("CI_RUN_URL"),
        findings=findings,
        dry_run=dry_run,
    )
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line("")
        reporter.write_line("notification " + ("(dry run, nothing sent):" if dry_run else "sent:"))
        for line in message.splitlines():
            reporter.write_line("  " + line)
