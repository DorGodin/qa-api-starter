"""Many customers pressing "Book" in the same instant.

Asserted as exactly one 201, every other a 409 slot_taken, and no 5xx. "Only one
booking exists" on its own would pass a server that answers everyone who lost
with a 500 - which is what an unlocked check-then-insert does on SQLite. On
Postgres the same bug double books instead. This assertion catches both.
"""

import pytest

from utils.concurrency import at_once
from utils.local_time import at_local, local_day

RACERS = 10


def race(bookings, barber_id, service_id, attempts):
    """attempts: (start, persona) pairs, all fired at the same instant."""
    responses = at_once(
        [lambda s=s, p=p: bookings.book(barber_id, service_id, s, persona=p) for s, p in attempts]
    )
    return sorted(r.status_code for r in responses), responses


def confirmed_at(bookings, barber_id) -> int:
    return bookings.listing(persona="owner", barber_id=barber_id, status="confirmed", limit=100)["total"]


@pytest.mark.parametrize("stagger", [0, 15], ids=["same-start", "overlapping-starts"])
def test_many_customers_racing_for_one_slot_get_exactly_one_booking(
    barbers, bookings, haircut, new_customer, shop_tz, stagger
):
    contested = barbers.create_fake_barber()
    day = local_day(shop_tz, 3)
    starts = [
        at_local(shop_tz, day, "10:00" if i % 2 == 0 or not stagger else "10:15") for i in range(RACERS)
    ]
    attempts = [(start, new_customer()) for start in starts]

    codes, responses = race(bookings, contested["id"], haircut["id"], attempts)

    assert [c for c in codes if c >= 500] == [], f"the losers crashed instead of being refused: {codes}"
    assert codes.count(201) == 1, f"expected exactly one booking: {codes}"
    assert codes.count(409) == RACERS - 1, codes
    assert {r.as_dict.get("code") for r in responses if r.status_code == 409} == {"slot_taken"}
    assert (
        confirmed_at(bookings, contested["id"]) == 1
    ), "the server says one won, but more than one booking was stored"


def test_one_customer_double_submitting_without_a_key_books_once(
    barbers, bookings, haircut, new_customer, shop_tz
):
    contested = barbers.create_fake_barber()
    me = new_customer()
    start = at_local(shop_tz, local_day(shop_tz, 3), "11:00")

    codes, _ = race(bookings, contested["id"], haircut["id"], [(start, me), (start, me)])

    assert codes == [201, 409], codes
    assert bookings.listing(persona=me)["total"] == 1


def test_sign_ins_and_sign_outs_at_once_never_answer_with_a_server_error(api, customers, new_customer):
    """Every sign-in writes - it records or clears a failure - and so does every
    sign-out. Without the write lock two workers deadlocked in SQLite and one
    answered 500: an owner signing in while a customer on the same page signed out."""
    accounts = []
    for _ in range(8):
        payload = customers.build_signup_payload()
        customers.create(payload).assert_ok(201)
        accounts.append(payload)
    sessions = [new_customer() for _ in range(8)]

    def sign_in(account, password):
        return api.request(
            "POST", "/auth/token", persona=None, json={"username": account["username"], "password": password}
        )

    calls = [lambda a=a: sign_in(a, a["password"]) for a in accounts]
    calls += [lambda a=a: sign_in(a, "not-the-password") for a in accounts]
    calls += [lambda p=p: api.request("POST", "/auth/logout", persona=p) for p in sessions]
    codes = sorted(r.status_code for r in at_once(calls))

    assert [c for c in codes if c >= 500] == [], f"a sign-in or sign-out met a locked database: {codes}"


def test_the_owner_saving_while_customers_book_never_answers_with_a_server_error(
    barbers, bookings, services, haircut, new_customer, shop_tz
):
    barber = barbers.create_fake_barber()
    day = local_day(shop_tz, 5)
    people = [new_customer() for _ in range(8)]
    calls = [
        lambda n=n: bookings.book(
            barber["id"], haircut["id"], at_local(shop_tz, day, f"{9 + n}:00"), persona=people[n]
        )
        for n in range(8)
    ]
    calls += [lambda: barbers.set_hours(barber["id"], barbers.build_hours()) for _ in range(8)]
    calls += [lambda: services.create(services.build_service_payload(), persona="owner") for _ in range(8)]

    codes = sorted(r.status_code for r in at_once(calls))

    assert [c for c in codes if c >= 500] == [], f"an owner's save met a locked database: {codes}"
