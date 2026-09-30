import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import perf_run  # noqa: E402

from tests.unit.test_perf_history import TOKEN, k6_export  # noqa: E402


class FakeK6:
    """Stands in for the k6 binary: writes the export where it was told to, as
    k6 does, and returns the exit code k6 would."""

    def __init__(self, export: dict | None, exit_code: int):
        self.export = export
        self.exit_code = exit_code
        self.command: list[str] | None = None

    def __call__(self, command, cwd=None):
        self.command = command
        target = next(arg.split("=", 1)[1] for arg in command if arg.startswith("--summary-export="))
        if self.export is not None:
            Path(target).write_text(json.dumps(self.export))
        return type("Completed", (), {"returncode": self.exit_code})()


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.setattr(perf_run, "REPORTS", tmp_path)
    monkeypatch.setenv("ENV", "local")
    monkeypatch.delenv("BASE_URL", raising=False)

    def start(fake, *args):
        monkeypatch.setattr(perf_run.subprocess, "run", fake)
        monkeypatch.setattr(sys, "argv", ["perf_run.py", "perf/write_path.js", *args])
        return perf_run.main()

    return start


def ledger(tmp_path: Path) -> list[dict]:
    path = tmp_path / "perf.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_a_breached_run_is_recorded_and_still_fails_the_pipeline(harness, tmp_path):
    fake = FakeK6(k6_export(wrong_totals=5, crossed=("count==0",)), exit_code=99)

    code = harness(fake)

    assert code == 99
    assert ledger(tmp_path)[-1]["verdict"] == "THRESHOLDS BREACHED"


def test_the_token_never_reaches_the_ledger_and_the_export_is_deleted(harness, tmp_path):
    fake = FakeK6(k6_export(), exit_code=0)

    harness(fake)

    export = next(arg.split("=", 1)[1] for arg in fake.command if arg.startswith("--summary-export="))
    assert not Path(export).exists(), "the raw export holds setup_data and must not survive the run"
    assert TOKEN not in (tmp_path / "perf.jsonl").read_text()


def test_the_export_is_deleted_even_when_k6_writes_nothing(harness, tmp_path):
    fake = FakeK6(None, exit_code=255)

    code = harness(fake)

    export = next(arg.split("=", 1)[1] for arg in fake.command if arg.startswith("--summary-export="))
    assert code == 255
    assert not Path(export).exists()
    assert ledger(tmp_path) == [], "a run with no summary must not invent a row"


def test_the_profile_flag_is_consumed_and_the_rest_reaches_k6(harness):
    fake = FakeK6(k6_export(), exit_code=0)

    harness(fake, "--profile", "spike", "-e", "VUS=7")

    assert "PROFILE=spike" in fake.command
    assert "VUS=7" in fake.command
    assert "--profile" not in fake.command, "k6 has no --profile flag and would exit 255"


def test_prod_is_refused_before_k6_is_ever_started(harness, monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    fake = FakeK6(k6_export(), exit_code=0)

    with pytest.raises(AssertionError, match="must never run against prod"):
        harness(fake)
    assert fake.command is None


def test_a_base_url_that_names_prod_is_refused(harness, monkeypatch):
    monkeypatch.setenv("BASE_URL", "https://api.prod.example.com")
    fake = FakeK6(k6_export(), exit_code=0)

    with pytest.raises(SystemExit, match="names prod"):
        harness(fake)
    assert fake.command is None
