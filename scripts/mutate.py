#!/usr/bin/env python3
"""Mutation testing: break the product one rule at a time, and check a suite notices.

A green suite proves the product passes it. It does not prove the suite would fail
if the product broke - a test can assert nothing and still be green. So each entry
in a catalogue (mutants/<product>.yml) is one rule broken on purpose, and names the
suite that must catch it. This runs a copy of the product with that one change, runs
that suite, and reports every mutant that survived.

    python scripts/mutate.py --product ../barber-booking-api            # the whole catalogue
    python scripts/mutate.py --product ../barber-booking-api --only lock
    python scripts/mutate.py --product ../barber-booking-api --check    # anchors only, seconds

Safety:

- it never edits the product's checkout. Running servers read the page from disk on
  every request, so editing it in place would break the page for anyone using it for
  the whole run. It exports the last commit (`git archive HEAD`) into a temporary
  directory and breaks that copy - so it tests what is committed, and says which commit;
- the broken copy runs on its own port (the `barber-mutant` environment, 8102) with a
  throwaway database - never on a copy anyone uses;
- nothing it runs is recorded in the run history or the dashboard (QA_NO_RECORD).

And because a report is only as good as its baseline: the unmodified product is run
first, and if it does not pass every suite the catalogue uses, nothing else is run.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
ENV_NAME = "barber-mutant"
PORT = 8102

SUITES = {
    "api": [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "tests/barber"],
    "ui": [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "--ui", "tests/barber_ui"],
    # Safari's engine. Some defects exist only there - a select drawn by the
    # browser, 23px tall whatever the CSS says - and survive every Chromium run.
    "ui-webkit": [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-x",
        "-p",
        "no:cacheprovider",
        "--ui",
        "tests/barber_ui/test_booking_page_mobile.py",
        "--browser",
        "webkit",
    ],
    "load": [
        sys.executable,
        "scripts/perf_run.py",
        "perf/barber/booking_race.js",
        "--profile",
        "load",
        "-e",
        "VUS=20",
        "-e",
        "RAMP=3s",
        "-e",
        "HOLD=12s",
    ],
}


@dataclass
class Change:
    find: str
    replace: str


@dataclass
class Mutant:
    name: str
    file: str
    catches: list[str]
    changes: list[Change]


@dataclass
class Outcome:
    mutant: Mutant
    caught_by: str | None = None
    detail: str = ""
    error: str = ""
    suites_run: list[str] = field(default_factory=list)


def load_catalogue(path: Path) -> list[Mutant]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutants = []
    for entry in raw["mutants"]:
        unknown = set(entry["catches"]) - set(SUITES)
        if unknown:
            raise ValueError(f"{entry['name']}: unknown suite(s) {sorted(unknown)}; known: {sorted(SUITES)}")
        mutants.append(
            Mutant(
                entry["name"],
                entry["file"],
                list(entry["catches"]),
                [Change(c["find"], c["replace"]) for c in entry["changes"]],
            )
        )
    names = [m.name for m in mutants]
    if len(set(names)) != len(names):
        raise ValueError("two mutants share a name; every name must say what it breaks")
    return mutants


def stale_anchors(product: Path, mutants: list[Mutant]) -> list[str]:
    """Every change must find its text exactly once, or it would break nothing - or
    the wrong thing - and look like a caught or a survived mutant for no reason."""
    problems = []
    for mutant in mutants:
        path = product / mutant.file
        if not path.is_file():
            problems.append(f"{mutant.name}: no such file {mutant.file}")
            continue
        text = path.read_text(encoding="utf-8")
        for change in mutant.changes:
            count = text.count(change.find)
            if count != 1:
                first = change.find.strip().splitlines()[0][:70]
                problems.append(f"{mutant.name}: found {count} times in {mutant.file}: {first!r}")
    return problems


def apply(product: Path, mutant: Mutant) -> str:
    """Apply the mutant; return the file's original text for restoring it."""
    path = product / mutant.file
    original = path.read_text(encoding="utf-8")
    mutated = original
    for change in mutant.changes:
        mutated = mutated.replace(change.find, change.replace, 1)
    path.write_text(mutated, encoding="utf-8")
    return original


def tree_is_clean(product: Path) -> bool:
    status = subprocess.run(
        ["git", "-C", str(product), "status", "--porcelain"], capture_output=True, text=True
    )
    return status.returncode == 0 and status.stdout.strip() == ""


def export_head(product: Path) -> tuple[Path, str]:
    """The product's last commit, exported to a temporary directory. The mutants
    break this copy; the checkout - and every server reading from it - is untouched."""
    commit = subprocess.run(
        ["git", "-C", str(product), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    workspace = Path(tempfile.mkdtemp(prefix="mutation-workspace-"))
    archive = subprocess.run(
        ["git", "-C", str(product), "archive", "HEAD"], capture_output=True, check=True
    ).stdout
    subprocess.run(["tar", "-x", "-C", str(workspace)], input=archive, check=True)
    return workspace, commit


def env_example(product: Path) -> dict[str, str]:
    """The product's committed development values - never anyone's private .env."""
    values = {}
    for line in (product / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def port_in_use(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


class ProductServer:
    """The product, started from the exported copy with the checkout's own virtualenv,
    on the mutant port, on a fresh database."""

    def __init__(self, product: Path, port: int, python: Path) -> None:
        self.product, self.port, self.python, self.proc, self.workdir = product, port, python, None, None

    def start(self) -> bool:
        self.workdir = Path(tempfile.mkdtemp(prefix="mutant-db-"))
        env = {
            **os.environ,
            **env_example(self.product),
            "DATABASE_URL": f"sqlite:///{self.workdir / 'm.db'}",
            # Its codes go to the fake SMS provider the suites read them from.
            "SMS_URL": "http://127.0.0.1:8109/messages",
        }
        self.proc = subprocess.Popen(
            [
                str(self.python),
                "-m",
                "uvicorn",
                "app.main:create_app",
                "--factory",
                "--port",
                str(self.port),
                "--workers",
                "2",
            ],
            cwd=self.product,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        for _ in range(60):
            if self.proc.poll() is not None:
                return False
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=2) as resp:
                    if resp.status == 200:
                        return True
            except OSError:
                time.sleep(0.5)
        return False

    def stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
        for _ in range(30):
            if not port_in_use(self.port):
                break
            time.sleep(0.2)
        if self.workdir is not None:
            shutil.rmtree(self.workdir, ignore_errors=True)


def verdict(name: str, returncode: int) -> str:
    """passed, failed - or error. For a pytest suite only 1 means a test failed; 2
    interrupted, 3 internal error, 4 usage, 5 nothing collected mean the tests are
    broken, and counting that as a catch would hide a survivor."""
    if returncode == 0:
        return "passed"
    if name == "load" or returncode == 1:
        return "failed"
    return "error"


def run_suite(name: str) -> tuple[str, str]:
    env = {**os.environ, "ENV": ENV_NAME, "QA_NO_RECORD": "1", "PYTHONPATH": str(ROOT)}
    result = subprocess.run(SUITES[name], cwd=ROOT, env=env, capture_output=True, text=True)
    lines = [line for line in result.stdout.splitlines() if line.startswith(("FAILED", "ERROR"))]
    summary = (
        lines[0].split(" - ")[0] if lines else (result.stdout.strip().splitlines() or ["(no output)"])[-1]
    )
    return verdict(name, result.returncode), summary


def run_mutant(product: Path, mutant: Mutant, python: Path) -> Outcome:
    outcome = Outcome(mutant)
    original = apply(product, mutant)
    server = ProductServer(product, PORT, python)
    try:
        if not server.start():
            outcome.caught_by, outcome.detail = "startup", "the broken product did not start"
            return outcome
        for suite in mutant.catches:
            outcome.suites_run.append(suite)
            status, summary = run_suite(suite)
            if status == "error":
                outcome.error = f"{suite}: {summary}"
                return outcome
            if status == "failed":
                outcome.caught_by, outcome.detail = suite, summary
                return outcome
        return outcome
    finally:
        server.stop()
        (product / mutant.file).write_text(original, encoding="utf-8")


def baseline(product: Path, suites: list[str], python: Path) -> list[str]:
    """The suites the clean product fails. Must be empty for a report to mean anything."""
    server = ProductServer(product, PORT, python)
    try:
        if not server.start():
            return ["startup"]
        return [suite for suite in suites if run_suite(suite)[0] != "passed"]
    finally:
        server.stop()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--product", required=True, type=Path, help="the product's checkout, e.g. ../barber-booking-api"
    )
    parser.add_argument("--catalogue", type=Path, default=ROOT / "mutants" / "barber-booking.yml")
    parser.add_argument("--only", help="run only mutants whose name contains this")
    parser.add_argument(
        "--check", action="store_true", help="check the anchors still match the product, run nothing"
    )
    args = parser.parse_args()

    product = args.product.resolve()
    mutants = load_catalogue(args.catalogue)
    if args.only:
        mutants = [m for m in mutants if args.only in m.name]

    stale = stale_anchors(product, mutants)
    if stale:
        print("the catalogue no longer matches the product - update these before trusting any report:")
        print("\n".join(f"  {line}" for line in stale))
        return 2
    if args.check:
        print(f"{len(mutants)} mutant(s): every anchor matches {product.name} exactly once")
        return 0

    if port_in_use(PORT):
        print(f"refusing: something already listens on port {PORT}, the mutant port.")
        return 2
    python = product / ".venv" / "bin" / "python"
    if not python.exists():
        print(f"refusing: no virtualenv at {python}. Run `make install` in {product.name}.")
        return 2

    workspace, commit = export_head(product)
    if not tree_is_clean(product):
        print(
            f"note: {product.name} has uncommitted changes; this tests the last commit, {commit}, without them."
        )
    try:
        needed = sorted({suite for m in mutants for suite in m.catches})
        print(
            f"baseline: {product.name} at {commit}, unmodified, against {', '.join(needed)} ...", flush=True
        )
        failing = baseline(workspace, needed, python)
        if failing:
            print(
                f"refusing: the unmodified product already fails {', '.join(failing)}. A mutation report would mean nothing."
            )
            return 2

        outcomes = []
        for index, mutant in enumerate(mutants, 1):
            outcome = run_mutant(workspace, mutant, python)
            outcomes.append(outcome)
            mark = "CAUGHT  " if outcome.caught_by else "ERROR   " if outcome.error else "SURVIVED"
            detail = (
                f"by {outcome.caught_by}: {outcome.detail}"
                if outcome.caught_by
                else outcome.error or f"ran {', '.join(outcome.suites_run)}"
            )
            print(f"[{index:>2}/{len(mutants)}] {mark} {mutant.name}\n           {detail}", flush=True)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    survivors = [o for o in outcomes if not o.caught_by and not o.error]
    errors = [o for o in outcomes if o.error]
    REPORTS.mkdir(exist_ok=True)
    report = REPORTS / f"mutation-{product.name}.json"
    report.write_text(
        json.dumps(
            {
                "product": product.name,
                "commit": commit,
                "caught": sum(1 for o in outcomes if o.caught_by),
                "total": len(outcomes),
                "mutants": [
                    {
                        "name": o.mutant.name,
                        "file": o.mutant.file,
                        "catches": o.mutant.catches,
                        "caught_by": o.caught_by,
                        "detail": o.detail,
                        "error": o.error,
                    }
                    for o in outcomes
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"\n{product.name} at {commit}: {sum(1 for o in outcomes if o.caught_by)} of {len(outcomes)} mutants caught. Report: {report.relative_to(ROOT)}"
    )
    for o in survivors:
        print(f"  SURVIVED {o.mutant.name} - {', '.join(o.mutant.catches)} did not notice")
    for o in errors:
        print(f"  ERROR    {o.mutant.name} - {o.error}")
    return 1 if survivors or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
