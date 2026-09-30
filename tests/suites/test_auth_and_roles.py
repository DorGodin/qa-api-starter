import pytest


def test_token_is_issued_for_valid_credentials(api, credentials):
    username, password = credentials("admin")
    resp = api.request(
        "POST",
        "/auth/token",
        persona=None,
        json={"username": username, "password": password},
    ).assert_ok(200)

    body = resp.as_dict
    assert body["token_type"] == "bearer"
    assert body["role"] == "admin"
    assert body["access_token"]


# ADMIN is resolved inside the test, not at collection: collection must not
# need a password, and a password must never become part of a test id.
ADMIN = object()


@pytest.mark.parametrize(
    "username, password",
    [(ADMIN, "wrong"), ("nobody", ADMIN), ("", "")],
    ids=["wrong-password", "unknown-user", "empty"],
)
def test_bad_credentials_are_rejected(api, credentials, username, password):
    admin_user, admin_password = credentials("admin")
    username = admin_user if username is ADMIN else username
    password = admin_password if password is ADMIN else password
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
    assert api.auth_headers("admin") != api.auth_headers("member")


def test_switching_persona_switches_identity(api, orders):
    assert orders.budget(persona="member") == pytest.approx(500.0)
    assert orders.budget(persona="admin") == pytest.approx(0.0)
