"""The barbershop from an attacker's side: tokens that were tampered with, someone else's booking, fields a
caller is not allowed to set, another site's page calling the API, paths that climb out of the media folder,
and files that pretend to be pictures. Each one is refused the way an ordinary mistake is - and never a 5xx."""

from __future__ import annotations

import base64
import json

import pytest

from obj.barber.courses import PNG_1X1, Courses
from utils.assertions import assert_refused
from utils.local_time import at_local, local_day

FOREIGN_SITE = "https://evil.example"


def b64(part: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(part).encode()).rstrip(b"=").decode()


def with_token(api, token: str, path: str = "/me"):
    persona = f"forged-{abs(hash(token))}"
    api.register_persona_headers(persona, {"Authorization": f"Bearer {token}"})
    return api.request("GET", path, persona=persona)


@pytest.fixture
def signed_in(customers, sms_inbox) -> dict:
    return customers.sign_in_by_code(sms_inbox)


@pytest.fixture
def someones_booking(barbers, bookings, haircut, new_customer, shop_tz) -> dict:
    owner_of_it = new_customer()
    barber = barbers.create_fake_barber()
    start = at_local(shop_tz, local_day(shop_tz, 6), "11:00")
    return {
        "booking": bookings.create_booking(barber["id"], haircut["id"], start, persona=owner_of_it),
        "barber": barber,
    }


def test_a_token_changed_in_any_part_is_refused_like_no_token_at_all(api, signed_in):
    header, payload, signature = signed_in["token"].split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    flipped = signature[:-2] + ("AA" if signature[-2:] != "AA" else "BB")
    forged = {
        "the signature changed": f"{header}.{payload}.{flipped}",
        "the claims changed, the signature kept": f"{header}.{b64({**claims, 'sub': 'usr_owner'})}.{signature}",
        "no signature, alg none": f"{b64({'alg': 'none', 'typ': 'JWT'})}.{payload}.",
        "not a token": "not-a-token",
    }
    unsigned = api.request("GET", "/me", persona=None)

    for what, token in forged.items():
        answer = with_token(api, token)
        assert answer.status_code == 401, what
        assert answer.as_dict == unsigned.as_dict, f"{what}: answered unlike a missing token"
    assert with_token(api, signed_in["token"]).status_code == 200, "the real token stopped working"


def test_a_token_ends_with_the_account_it_belongs_to(api, signed_in):
    with_token(api, signed_in["token"])
    persona = f"forged-{abs(hash(signed_in['token']))}"

    api.request("DELETE", "/me", persona=persona).assert_ok(204)

    assert with_token(api, signed_in["token"]).status_code == 401


def test_another_customer_cannot_see_or_touch_someone_elses_booking(
    api, bookings, someones_booking, new_customer, shop_tz
):
    booking_id = someones_booking["booking"]["id"]
    stranger = new_customer()
    later = at_local(shop_tz, local_day(shop_tz, 6), "13:00")

    attempts = {
        "read it": api.request("GET", f"/bookings/{booking_id}", persona=stranger),
        "cancel it": bookings.cancel(booking_id, persona=stranger),
        "move it": bookings.move(booking_id, later, persona=stranger),
        "make it standing": api.request(
            "POST", f"/bookings/{booking_id}/standing", persona=stranger, json={"every_weeks": 2}
        ),
    }

    for what, answer in attempts.items():
        assert answer.status_code == 404, f"a stranger could {what}: {answer.status_code}"
    assert booking_id not in str(bookings.listing(persona=stranger)), "it is in the stranger's list"


def test_a_customer_cannot_reach_the_shops_own_pages(api, someones_booking, new_customer):
    customer = new_customer()
    barber_id = someones_booking["barber"]["id"]

    for method, path, body in [
        ("POST", "/bookings/guest", {}),
        ("PUT", f"/barbers/{barber_id}/hours", {"hours": {}}),
        ("POST", f"/barbers/{barber_id}/time-off", {}),
        ("GET", "/customers/usr_any/card", None),
        ("PUT", "/customers/usr_any/note", {"note": "x"}),
        ("PUT", "/approval-rules", {}),
    ]:
        answer = api.request(method, path, persona=customer, json=body)
        assert answer.status_code == 403, f"{method} {path} answered a customer {answer.status_code}"


def test_a_role_sent_with_the_sign_in_is_ignored(api, customers, sms_inbox):
    phone = customers.new_phone()
    seen = sms_inbox.last_id(phone)
    extra = {"role": "owner", "is_owner": True, "is_staff": True, "id": "usr_owner"}

    api.request(
        "POST", "/auth/otp", persona=None, json={"full_name": "דנה כהן", "phone": phone, **extra}
    ).assert_ok(202)
    token = (
        customers.verify_code(phone, sms_inbox.code_for(phone, after=seen))
        .assert_ok(200)
        .as_dict["access_token"]
    )

    assert with_token(api, token).as_dict["role"] == "customer"


def test_a_booking_cannot_name_its_own_price_or_customer(
    api, bookings, barbers, haircut, new_customer, shop_tz
):
    me = new_customer()
    barber = barbers.create_fake_barber()
    payload = bookings.build_booking_payload(
        barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 7), "12:00")
    )

    booked = (
        api.request(
            "POST",
            "/bookings",
            persona=me,
            json={**payload, "price_minor": 1, "status": "confirmed", "customer_id": "usr_owner"},
        )
        .assert_ok(201)
        .as_dict
    )

    assert booked["price_minor"] == haircut["price_minor"]
    assert booked["customer_id"] != "usr_owner"


def test_another_sites_page_is_not_let_in(api):
    plain = api.request("GET", "/shop", persona=None, headers={"Origin": FOREIGN_SITE})
    preflight = api.request(
        "OPTIONS",
        "/bookings",
        persona=None,
        headers={"Origin": FOREIGN_SITE, "Access-Control-Request-Method": "POST"},
    )

    for answer in (plain, preflight):
        allowed = answer.raw.headers.get("Access-Control-Allow-Origin")
        assert allowed not in (FOREIGN_SITE, "*"), f"another site is let in: {allowed}"


def test_the_api_does_not_publish_a_map_of_itself(api):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert api.request("GET", path, persona=None).status_code == 404, f"{path} is served to anyone"


def test_unusual_methods_are_refused_cleanly(api):
    for method in ("TRACE", "PUT", "DELETE"):
        answer = api.request(method, "/shop", persona=None)
        assert answer.status_code == 405, f"{method} /shop answered {answer.status_code}"


@pytest.mark.parametrize(
    "path",
    [
        "/media/../.env",
        "/media/..%2f.env",
        "/media/%2e%2e/%2e%2e/etc/passwd",
        "/static/../app/config.py",
        "/fonts/..%2f..%2f.env",
        "/%2e%2e/.env",
        "/media/barber-x.png%00.html",
    ],
)
def test_a_path_cannot_climb_out_of_the_served_folders(api, path):
    answer = api.request("GET", path, persona=None)

    assert answer.status_code in (400, 404), f"{path} answered {answer.status_code}"
    assert "SECRET_KEY" not in answer.raw.text and "root:" not in answer.raw.text


@pytest.mark.parametrize(
    "disguised",
    [
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b"<html><script>alert(1)</script></html>",
        b"\x89PNG\r\n\x1a\n" + b"<script>alert(1)</script>",
    ],
    ids=["svg with a script", "a page", "a png head on a page"],
)
def test_a_file_that_only_pretends_to_be_a_picture_is_refused(barbers, disguised):
    barber = barbers.create_fake_barber()

    answer = barbers.client.request(
        "PUT", f"{barbers.path}/{barber['id']}/photo", persona="owner", json=Courses.encode(disguised)
    )

    assert_refused(answer, 422, "invalid_image")


def test_a_served_picture_is_a_picture_and_cannot_be_read_as_a_page(api, barbers):
    barber = barbers.create_fake_barber()
    url = (
        barbers.client.request(
            "PUT", f"{barbers.path}/{barber['id']}/photo", persona="owner", json=Courses.encode(PNG_1X1)
        )
        .assert_ok(200)
        .as_dict["photo_url"]
    )

    served = api.request("GET", url, persona=None).raw.headers

    assert served["Content-Type"].startswith("image/")
    assert served.get("X-Content-Type-Options") == "nosniff"
