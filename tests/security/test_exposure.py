"""What the product reveals without being asked."""
import pytest

pytestmark = pytest.mark.usefixtures("fresh_state")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


@pytest.mark.parametrize("header, expected", SECURITY_HEADERS.items())
def test_responses_carry_the_baseline_security_headers(api, header, expected):
    resp = api.request("GET", "/health", persona=None)
    assert resp.raw.headers.get(header) == expected


def test_an_authenticated_response_is_not_cacheable(api, orders):
    resp = api.request("GET", "/me/budget", persona="member")
    assert "no-store" in resp.raw.headers.get("Cache-Control", "")


def test_error_bodies_do_not_name_internal_machinery(items, orders):
    bodies = [
        str(items.get_by_id("itm-nope").as_dict),
        str(items.create({"price": "abc"}, persona="admin").as_dict),
        str(orders.create({"lines": []}, persona="member").as_dict),
    ]
    for body in bodies:
        for leak in ("Traceback", "site-packages", "/usr/", "sqlalchemy", "psycopg", "uvicorn"):
            assert leak not in body, f"an error body named {leak!r}"


def test_a_failed_login_does_not_say_which_half_was_wrong(api):
    unknown = api.request("POST", "/auth/token", persona=None, json={"username": "nobody", "password": "x"})
    wrong_password = api.request("POST", "/auth/token", persona=None, json={"username": "member", "password": "x"})

    assert unknown.status_code == wrong_password.status_code == 401
    assert unknown.as_dict == wrong_password.as_dict, (
        "different messages let an attacker enumerate valid usernames"
    )


@pytest.mark.parametrize(
    "payload",
    ["' OR 1=1 --", "<script>alert(1)</script>", "../../etc/passwd", "${jndi:ldap://x}", "\x00null"],
    ids=["sql", "xss", "traversal", "jndi", "null-byte"],
)
def test_hostile_strings_are_stored_as_data_not_executed(items, payload):
    created = items.create_fake_item(name=payload)

    assert created["name"] == payload, "the payload was altered rather than stored verbatim"
    found = items.find(params={"name": payload[:8]}).assert_ok(200)
    assert any(row["id"] == created["id"] for row in found.content)


def test_a_filter_value_cannot_change_how_many_rows_come_back(items):
    for i in range(3):
        items.create_fake_item(name=f"Safe {i}")

    injected = items.find(params={"name": "' OR '1'='1"}).assert_ok(200).as_dict
    assert injected["total"] == 0, "a filter value was interpreted instead of matched"
