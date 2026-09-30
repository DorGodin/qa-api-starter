"""The collection hook must gate folders without overriding pytest itself."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def collect(*args: str, env: str = "local") -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "ENV": env, "PYTHONPATH": "."},
    )
    last = [line for line in result.stdout.splitlines() if "collected" in line or "no tests" in line]
    if not last:
        raise AssertionError(result.stdout[-2000:] + result.stderr[-2000:])
    if "no tests" in last[-1]:
        return 0
    # pytest prints "12 tests collected", or "11/12 tests collected (1 deselected)"
    count = last[-1].split()[0]
    return int(count.split("/")[0])


def test_a_gated_folder_is_not_collected_without_its_flag():
    assert collect("tests/unit") == 0


def test_a_gated_folder_is_collected_with_its_flag():
    assert collect("--unit", "tests/unit") > 0


def test_the_hook_does_not_override_pytests_own_ignore():
    """Answering False to pytest_ignore_collect silently disables --ignore."""
    everything = collect("--unit", "tests/unit")
    without_one = collect("--unit", "tests/unit", "--ignore=tests/unit/test_trends.py")

    assert without_one < everything, "--ignore was swallowed by the gating hook"


def test_deselect_is_honoured_too():
    everything = collect("--unit", "tests/unit/test_trends.py")
    fewer = collect(
        "--unit",
        "tests/unit/test_trends.py",
        "--deselect=tests/unit/test_trends.py::test_no_history_is_not_a_finding",
    )

    assert fewer == everything - 1


def test_another_products_suites_are_not_collected():
    assert collect("tests/barber", env="local") == 0
    assert collect("tests/suites", env="barber") == 0


def test_a_products_own_suites_are_collected():
    assert collect("tests/barber", env="barber") > 0
    assert collect("tests/suites", env="local") > 0


def test_the_other_products_gated_folders_stay_out_even_with_their_flag():
    assert collect("--edge-cases", "tests/edge-cases", env="barber") == 0


def test_the_frameworks_own_tests_run_whatever_the_product():
    assert collect("--unit", "tests/unit", env="barber") == collect("--unit", "tests/unit", env="local") > 0


def test_a_broken_env_does_not_break_collection_of_the_unit_tests():
    assert collect("--unit", "tests/unit", env="no-such-env") > 0
