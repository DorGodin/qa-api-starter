"""One customer may hold two bookings, so the way around it is more accounts. One
address may make five an hour - every test here signs up from addresses of its own,
so no run uses up 127.0.0.1."""

from __future__ import annotations


def sign_up(customers, address: str, username: str | None = None):
    payload = customers.build_signup_payload(username=username)
    return customers.create(payload, headers={"X-Forwarded-For": address})


def test_five_accounts_from_one_address_and_the_sixth_is_refused(customers, fresh_address):
    address = fresh_address()
    for _ in range(5):
        sign_up(customers, address).assert_ok(201)

    refused = sign_up(customers, address)

    assert refused.status_code == 429
    assert refused.as_dict["code"] == "too_many_signups"
    assert 0 < int(refused.headers["Retry-After"]) <= 60 * 60
    sign_up(customers, fresh_address()).assert_ok(201)


def test_a_username_already_taken_does_not_use_up_the_address(customers, fresh_address):
    address = fresh_address()
    taken = sign_up(customers, address).as_dict["username"]
    for _ in range(5):
        assert sign_up(customers, address, username=taken).status_code == 409

    for _ in range(4):
        sign_up(customers, address).assert_ok(201)
