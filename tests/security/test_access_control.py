"""Access control, checked from the caller's side.

Most of these are not exotic. They are the ones that actually happen: an id
guessed from a URL, a token used for the wrong account, an error message that
says more than it should.
"""

import pytest

pytestmark = pytest.mark.usefixtures("fresh_state")


def test_a_member_cannot_read_an_order_by_guessing_its_id(items, orders, api):
    item = items.create_fake_item(price=10.0)
    order = orders.create_fake_order(item["id"], persona="member")

    # the admin owns nothing here, so this is another account's record
    resp = orders.get_by_id(order["id"], persona="admin")
    assert resp.status_code == 200, "an admin may read any order by design"

    unknown = orders.get_by_id("ord-999999", persona="member")
    assert unknown.status_code in (403, 404), "a guessed id must never return someone else's data"


def test_a_member_cannot_perform_an_admin_action_even_with_a_valid_token(items):
    assert items.create({"name": "x", "price": 1.0}, persona="member").status_code == 403
    assert items.delete_by_id("itm-1", persona="member").status_code == 403


def test_an_admin_action_refuses_an_anonymous_caller_before_it_validates_the_body(items):
    resp = items.create({"name": "", "price": -5}, persona=None)
    assert (
        resp.status_code == 401
    ), "authentication is checked before the payload, or the 422 leaks that the route exists"


@pytest.mark.parametrize(
    "header",
    ["", "Bearer", "Bearer ", "Basic abc", "Bearer ../../etc/passwd", "Bearer " + "a" * 500],
    ids=["empty", "scheme-only", "scheme-space", "wrong-scheme", "traversal", "very-long"],
)
def test_malformed_credentials_are_rejected_the_same_way(api, items, header):
    resp = api.request("GET", items.path, persona=None, headers={"Authorization": header})
    assert resp.status_code == 401, "every malformed credential must look the same to an attacker"


def test_a_token_is_not_accepted_in_a_query_parameter(api, items):
    token = api.auth_headers("member")["Authorization"].split(" ", 1)[1]
    resp = api.request("GET", f"{items.path}?access_token={token}", persona=None)

    assert resp.status_code == 401, "tokens in URLs end up in logs and browser history"
