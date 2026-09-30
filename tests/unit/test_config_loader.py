import json
from pathlib import Path

import pytest

import config.loader as loader
from config.loader import is_local_host, load_env_config, password_env_var, password_for


def block(url="http://127.0.0.1:8000", **extra):
    return {
        "url": url,
        "product": "demo",
        "personas": {"admin": "admin-user", "member": "member-user"},
        "admin_persona": "admin",
        "auth": {"type": "password_token", "path": "/auth/token"},
        "health_path": "/health",
        "test_hooks": True,
        **extra,
    }


@pytest.fixture
def configs(tmp_path: Path, monkeypatch):
    committed, local = tmp_path / "config.json", tmp_path / "config.local.json"
    monkeypatch.setattr(loader, "_CONFIG_PATH", committed)
    monkeypatch.setattr(loader, "_LOCAL_OVERRIDE", local)
    for persona in ("admin", "member"):
        monkeypatch.delenv(password_env_var(persona), raising=False)

    def write(committed_blocks: dict, local_blocks: dict | None = None):
        committed.write_text(json.dumps(committed_blocks))
        if local_blocks is not None:
            local.write_text(json.dumps(local_blocks))

    return write


def test_the_committed_config_is_valid_for_every_environment():
    for env in json.loads(Path("config/config.json").read_text()):
        load_env_config(env)


def test_unknown_env_names_the_known_ones(configs):
    configs({"local": block()})

    with pytest.raises(KeyError, match="local"):
        load_env_config("does-not-exist")


@pytest.mark.parametrize(
    "key", ["url", "product", "personas", "admin_persona", "auth", "health_path", "test_hooks"]
)
def test_every_required_key_is_named_when_it_is_missing(configs, key):
    incomplete = block()
    del incomplete[key]
    configs({"qa": incomplete})

    with pytest.raises(KeyError, match=key):
        load_env_config("qa")


def test_test_hooks_as_the_string_false_is_refused_because_it_is_truthy(configs):
    configs({"qa": block(test_hooks="false")})

    with pytest.raises(TypeError, match="true or false"):
        load_env_config("qa")


def test_a_password_for_a_remote_host_is_refused_in_the_committed_file(configs):
    configs({"qa": block(url="https://qa.product.com", passwords={"admin": "real"})})

    with pytest.raises(ValueError, match="config.local.json"):
        load_env_config("qa")


def test_a_password_for_a_remote_host_is_fine_in_the_local_override(configs):
    configs({"qa": block(url="https://qa.product.com")}, {"qa": {"passwords": {"admin": "from-local"}}})

    assert password_for("admin", "qa") == "from-local"


def test_passwords_never_travel_inside_the_config_dict(configs):
    configs({"local": block(passwords={"admin": "demo-pass"})})

    assert "passwords" not in load_env_config("local")
    assert "demo-pass" not in json.dumps(load_env_config("local"))


def test_the_environment_variable_wins_over_every_file(configs, monkeypatch):
    configs({"local": block(passwords={"admin": "committed"})}, {"local": {"passwords": {"admin": "local"}}})
    monkeypatch.setenv("QA_ADMIN_PASSWORD", "from-ci-secret")

    assert password_for("admin", "local") == "from-ci-secret"


def test_the_local_override_wins_over_the_committed_file(configs):
    configs({"local": block(passwords={"admin": "committed"})}, {"local": {"passwords": {"admin": "local"}}})

    assert password_for("admin", "local") == "local"


def test_a_missing_password_says_where_to_put_one_without_printing_any(configs):
    configs({"qa": block(url="https://qa.product.com")})

    with pytest.raises(KeyError) as err:
        password_for("admin", "qa")

    assert "QA_ADMIN_PASSWORD" in str(err.value)
    assert "config.local.json" in str(err.value)


def test_a_persona_name_becomes_a_valid_variable_name():
    assert password_env_var("shop-owner") == "QA_SHOP_OWNER_PASSWORD"


@pytest.mark.parametrize(
    "url, local",
    [
        ("http://127.0.0.1:8000", True),
        ("http://localhost:3000", True),
        ("http://[::1]:8000", True),
        ("http://api:8000", True),
        ("https://qa.product.com", False),
        ("https://staging.example.invalid", False),
        ("http://10.0.0.5:8000", False),
    ],
)
def test_only_this_machine_and_container_names_count_as_local(url, local):
    assert is_local_host(url) is local


def test_the_admin_persona_must_be_one_of_the_declared_personas(configs):
    configs({"qa": block(admin_persona="root")})

    with pytest.raises(ValueError, match="admin_persona 'root' is not one of its personas"):
        load_env_config("qa")
