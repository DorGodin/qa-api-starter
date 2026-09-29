import pytest


def test_token_is_issued_for_valid_credentials(api, env_config):
    resp = api.request(
        "POST", "/auth/token", persona=None,
        json={"username": env_config["admin_user"], "password": "admin-secret"},
    ).assert_ok(200)

    body = resp.as_dict
    assert body["token_type"] == "bearer"
    assert body["role"] == "admin"
    assert body["access_token"]


@pytest.mark.parametrize(
    "username, password",
    [("admin", "wrong"), ("nobody", "admin-secret"), ("", "")],
    ids=["wrong-password", "unknown-user", "empty"],
)
def test_bad_credentials_are_rejected(api, username, password):
    resp = api.request("POST", "/auth/token", persona=None, json={"username": username, "password": password})
    assert resp.status_code == 401


def test_a_garbage_token_is_rejected(api, items):
    resp = api.request("GET", items.path, persona=None, headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_a_malformed_authorization_header_is_rejected(api, items):
    resp = api.request("GET", items.path, persona=None, headers={"Authorization": "not-even-a-scheme"})
    assert resp.status_code == 401


def test_member_cannot_reach_admin_only_endpoints(items):
    assert items.create({"name": "x", "price": 1.0}, persona="member").status_code == 403


def test_admin_and_member_get_different_tokens(api):
    assert api._tokens["admin"] != api._tokens["member"]


def test_switching_persona_switches_identity(api, orders):
    assert orders.budget(persona="member") == pytest.approx(500.0)
    assert orders.budget(persona="admin") == pytest.approx(0.0)
