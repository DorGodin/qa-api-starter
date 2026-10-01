"""Signing out ends the sign-in on the server, not only in the browser.

A signed token is valid until it expires - twelve hours - whatever the browser
does with it. Before this, a token copied before the sign-out (from a shared
computer, a log, a stolen sessionStorage) kept working all that time.
"""

from __future__ import annotations


def signed_in(api, account: dict) -> dict:
    resp = api.request(
        "POST",
        "/auth/token",
        persona=None,
        json={"username": account["username"], "password": account["password"]},
    )
    resp.assert_ok(200)
    return {"Authorization": f"Bearer {resp.as_dict['access_token']}"}


def an_account(customers) -> dict:
    payload = customers.build_signup_payload()
    customers.create(payload, persona=None).assert_ok(201)
    return payload


def test_a_token_stops_working_the_moment_its_sign_in_ends(api, customers):
    session = signed_in(api, an_account(customers))
    assert api.request("GET", "/me", persona=None, headers=session).status_code == 200

    api.request("POST", "/auth/logout", persona=None, headers=session).assert_ok(204)

    assert api.request("GET", "/me", persona=None, headers=session).status_code == 401
    assert api.request("GET", "/bookings", persona=None, headers=session).status_code == 401


def test_signing_out_on_one_phone_leaves_the_person_signed_in_on_another(api, customers):
    account = an_account(customers)
    phone, laptop = signed_in(api, account), signed_in(api, account)

    api.request("POST", "/auth/logout", persona=None, headers=phone).assert_ok(204)

    assert api.request("GET", "/me", persona=None, headers=laptop).status_code == 200


def test_a_sign_out_needs_a_sign_in_to_end(api):
    assert api.request("POST", "/auth/logout", persona=None).status_code == 401
