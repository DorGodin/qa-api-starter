"""Who can do what, and what an outsider learns from trying."""

import pytest

from utils.local_time import local_day


@pytest.mark.parametrize(
    "attempt",
    [
        lambda s: s["services"].create(s["services"].build_service_payload(), persona="customer"),
        lambda s: s["barbers"].create(s["barbers"].build_barber_payload(), persona="customer"),
        lambda s: s["barbers"].set_hours(s["barber"]["id"], s["barbers"].build_hours(), persona="customer"),
        lambda s: s["barbers"].add_time_off(s["barber"]["id"], local_day(s["tz"], 20), persona="customer"),
        lambda s: s["services"].update_by_id(s["haircut"]["id"], {"price_minor": 1}, persona="customer"),
    ],
    ids=["create-service", "create-barber", "set-hours", "add-time-off", "change-a-price"],
)
def test_a_customer_cannot_run_the_shop(services, barbers, barber, haircut, shop_tz, attempt):
    resp = attempt(
        {"services": services, "barbers": barbers, "barber": barber, "haircut": haircut, "tz": shop_tz}
    )

    assert resp.status_code == 403, resp.as_dict


def test_a_barber_cannot_change_the_menu(services):
    assert services.create(services.build_service_payload(), persona="barber").status_code == 403


def test_every_bad_credential_looks_the_same_to_an_outsider(api):
    missing = api.request("GET", "/bookings", persona=None)
    garbage = api.request("GET", "/bookings", persona=None, headers={"Authorization": "Bearer not-a-token"})
    wrong_scheme = api.request(
        "GET", "/bookings", persona=None, headers={"Authorization": "Basic b3duZXI6eA=="}
    )

    assert missing.status_code == garbage.status_code == wrong_scheme.status_code == 401
    assert missing.as_dict == garbage.as_dict == wrong_scheme.as_dict


def test_an_unknown_user_and_a_wrong_password_get_the_same_answer(api, credentials):
    owner, _ = credentials("owner")
    unknown = api.request(
        "POST", "/auth/token", persona=None, json={"username": "nobody-at-all", "password": "x"}
    )
    wrong = api.request("POST", "/auth/token", persona=None, json={"username": owner, "password": "x"})

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.as_dict == wrong.as_dict, "different answers let an attacker find real usernames"


def test_each_customer_lists_only_their_own_bookings(
    barbers, bookings, barber, haircut, new_customer, shop_tz
):
    alice, bob = new_customer(), new_customer()
    slots = barbers.slots(barber["id"], local_day(shop_tz, 10), haircut["id"])
    alices = bookings.create_booking(barber["id"], haircut["id"], slots[0]["start"], persona=alice)
    bobs = bookings.create_booking(barber["id"], haircut["id"], slots[4]["start"], persona=bob)

    assert [b["id"] for b in bookings.listing(persona=alice)["content"]] == [alices["id"]]
    assert [b["id"] for b in bookings.listing(persona=bob)["content"]] == [bobs["id"]]
