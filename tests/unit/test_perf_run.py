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

    def __call__(self, command, cwd=None, env=None):
        self.command = command
        self.env = env
        target = next(arg.split("=", 1)[1] for arg in command if arg.startswith("--summary-export="))
        if self.export is not None:
            Path(target).write_text(json.dumps(self.export))
        return type("Completed", (), {"returncode": self.exit_code})()


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.setattr(perf_run, "REPORTS", tmp_path)
    monkeypatch.setenv("ENV", "local")
    monkeypatch.delenv("PERF_REMOTE_OK", raising=False)

    def start(fake, *args, script="perf/write_path.js"):
        monkeypatch.setattr(perf_run.subprocess, "run", fake)
        monkeypatch.setattr(sys, "argv", ["perf_run.py", script, *args])
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


def config_for(url: str, product: str = "demo") -> dict:
    return {
        "env": "qa",
        "url": url,
        "product": product,
        "personas": {"admin": "a"},
        "admin_persona": "admin",
        "auth": {"type": "password_token", "path": "/auth/token"},
        "health_path": "/health",
        "test_hooks": False,
    }


def test_a_url_that_names_prod_is_refused(harness, monkeypatch):
    monkeypatch.setattr(perf_run, "load_env_config", lambda: config_for("https://api.prod.example.com"))
    fake = FakeK6(k6_export(), exit_code=0)

    with pytest.raises(SystemExit, match="names prod"):
        harness(fake)
    assert fake.command is None


def test_somebody_elses_server_is_not_load_tested_unless_claimed_on_purpose(harness, monkeypatch):
    monkeypatch.setattr(perf_run, "load_env_config", lambda: config_for("https://restful-booker.example.com"))
    fake = FakeK6(k6_export(), exit_code=0)

    with pytest.raises(SystemExit, match="PERF_REMOTE_OK"):
        harness(fake)
    assert fake.command is None


def test_passwords_reach_k6_through_its_environment_and_never_its_arguments(harness):
    fake = FakeK6(k6_export(), exit_code=0)

    harness(fake)

    assert fake.env["QA_ADMIN_PASSWORD"], "k6 needs the password"
    assert fake.env["QA_ADMIN_USER"] == "admin"
    assert not any(
        fake.env["QA_ADMIN_PASSWORD"] in arg for arg in fake.command
    ), "a password in argv is readable by anyone who can list processes"
    assert fake.env["BASE_URL"] == "http://127.0.0.1:8000" and fake.env["TEST_HOOKS"] == "true"


def test_another_products_environment_is_refused_because_the_scripts_are_the_demos(harness, monkeypatch):
    monkeypatch.setattr(
        perf_run, "load_env_config", lambda: config_for("http://127.0.0.1:8100", product="barber-booking")
    )
    fake = FakeK6(k6_export(), exit_code=0)

    with pytest.raises(SystemExit, match="drives the 'demo' product"):
        harness(fake)
    assert fake.command is None


def test_a_barbershop_script_is_refused_against_the_demo(harness):
    fake = FakeK6(k6_export(), exit_code=0)

    with pytest.raises(SystemExit, match="drives the 'barber-booking' product"):
        harness(fake, script="perf/barber/booking_race.js")
    assert fake.command is None


def test_scripts_belong_to_the_product_of_their_folder():
    assert perf_run.product_of("perf/barber/booking_race.js") == "barber-booking"
    assert perf_run.product_of("perf/write_path.js") == "demo"
    assert perf_run.product_of("perf/barberish.js") == "demo", "a folder prefix is not a folder"
