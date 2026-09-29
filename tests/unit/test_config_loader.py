import pytest

from config.loader import load_env_config


def test_known_env_returns_required_keys():
    block = load_env_config("local")
    assert block["env"] == "local"
    for key in ("url", "admin_user", "member_user"):
        assert key in block


def test_unknown_env_names_the_known_ones():
    with pytest.raises(KeyError) as err:
        load_env_config("does-not-exist")
    assert "local" in str(err.value)
