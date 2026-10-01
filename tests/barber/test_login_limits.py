"""Guessing passwords. The barbershop refuses a sign-in for a while after 5
wrong passwords for one account from one address, and after 20 from one address
for any accounts - with the right password too, or the guessing would go on.

Every request here comes from an address of the test's own (fresh_address), so
no run ever locks the machine the suites run on.
"""

from __future__ import annotations

WINDOW_SECONDS = 15 * 60


def sign_in(api, username: str, password: str, address: str):
    return api.request(
        "POST",
        "/auth/token",
        persona=None,
        headers={"X-Forwarded-For": address},
        json={"username": username, "password": password},
    )


def an_account(customers) -> dict:
    payload = customers.build_signup_payload()
    customers.create(payload, persona=None).assert_ok(201)
    return payload


def test_five_wrong_passwords_lock_the_account_there_even_against_the_right_one(
    api, customers, fresh_address
):
    account, address = an_account(customers), fresh_address()
    for _ in range(5):
        assert sign_in(api, account["username"], "not-the-password", address).status_code == 401

    refused = sign_in(api, account["username"], account["password"], address)

    assert refused.status_code == 429
    assert refused.as_dict["code"] == "too_many_attempts"
    wait = int(refused.headers["Retry-After"])
    assert 0 < wait <= WINDOW_SECONDS
    assert refused.as_dict["retry_after_seconds"] == wait


def test_an_attacker_cannot_lock_the_real_person_out_from_somewhere_else(api, customers, fresh_address):
    account, attacker, owner_of_it = an_account(customers), fresh_address(), fresh_address()
    for _ in range(6):
        sign_in(api, account["username"], "not-the-password", attacker)

    assert sign_in(api, account["username"], account["password"], owner_of_it).status_code == 200


def test_one_password_tried_across_many_usernames_locks_the_address(api, customers, fresh_address):
    account, sprayer = an_account(customers), fresh_address()
    for i in range(20):
        sign_in(api, f"guess-{i}-{sprayer}", "Summer2026!", sprayer)

    assert sign_in(api, account["username"], account["password"], sprayer).status_code == 429
    assert sign_in(api, account["username"], account["password"], fresh_address()).status_code == 200


def test_the_right_password_before_the_limit_starts_the_count_again(api, customers, fresh_address):
    account, address = an_account(customers), fresh_address()
    for _ in range(4):
        sign_in(api, account["username"], "not-the-password", address)
    assert sign_in(api, account["username"], account["password"], address).status_code == 200
    for _ in range(4):
        sign_in(api, account["username"], "not-the-password", address)

    assert sign_in(api, account["username"], account["password"], address).status_code == 200


def test_a_username_that_does_not_exist_is_refused_exactly_like_one_that_does(api, customers, fresh_address):
    real, address = an_account(customers), fresh_address()
    answers = {}
    for username in (real["username"], f"nobody-{address}"):
        for _ in range(5):
            sign_in(api, username, "not-the-password", address)
        refused = sign_in(api, username, "not-the-password", address)
        answers[username] = (refused.status_code, refused.as_dict["code"])

    assert set(answers.values()) == {
        (429, "too_many_attempts")
    }, "a lock that only real accounts get names them"
