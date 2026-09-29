from __future__ import annotations

from pathlib import Path

import pytest

from config.loader import load_env_config
from obj import ApiClient, Items, Orders

GATED = {
    "tests/unit": "--unit",
    "tests/edge-cases": "--edge-cases",
}
PASSWORDS = {"admin": "admin-secret", "member": "member-secret"}


def pytest_addoption(parser):
    parser.addoption("--unit", action="store_true", default=False, help="collect tests/unit")
    parser.addoption("--edge-cases", action="store_true", default=False, help="collect tests/edge-cases")


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


@pytest.fixture(scope="module", autouse=True)
def _clean_state(request):
    """Reset once per module so an ordered flow keeps its state, and modules
    never leak into each other."""
    if "api" not in getattr(request, "fixturenames", []):
        return
    request.getfixturevalue("api").request("POST", "/_test/reset", persona="admin").assert_ok(204)


@pytest.fixture(scope="module")
def ctx():
    """Shared state for ordered tests inside one module."""
    return {}
