"""The shop's courses: the owner keeps them, a customer reads them, a card's button opens
WhatsApp with the course named, and a picture is accepted by what it is."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from obj.barber.courses import GIF_HEAD, JPEG_HEAD, PNG_1X1, WEBP_HEAD
from utils.assertions import assert_refused


def test_the_owner_adds_a_course_and_a_customer_reads_it(courses, new_customer):
    made = courses.create_fake_course(
        title="קורס ברברינג", subtitle="8 מפגשים", starts_on="2026-11-02", price_minor=320000
    )

    seen = next(c for c in courses.listing(new_customer()) if c["id"] == made["id"])

    assert (seen["title"], seen["subtitle"], seen["starts_on"], seen["price_minor"], seen["currency"]) == (
        "קורס ברברינג",
        "8 מפגשים",
        "2026-11-02",
        320000,
        "ILS",
    )
    assert seen["image_url"] is None and seen["active"] is True


def test_a_course_may_have_no_date_and_no_price(courses):
    made = courses.create_fake_course(subtitle="", starts_on=None, price_minor=None)

    assert (made["subtitle"], made["starts_on"], made["price_minor"]) == ("", None, None)


def test_only_the_owner_adds_changes_or_pictures_a_course(courses, new_customer):
    me, course = new_customer(), courses.create_fake_course()

    assert_refused(courses.create(courses.build_course_payload(), persona=me), 403, "forbidden")
    assert_refused(courses.update_by_id(course["id"], {"title": "x"}, persona=me), 403, "forbidden")
    assert_refused(courses.set_image(course["id"], PNG_1X1, persona=me), 403, "forbidden")
    assert_refused(courses.remove_image(course["id"], persona=me), 403, "forbidden")
    assert_refused(courses.find(persona=None), 401, "unauthorized")


def test_courses_come_by_date_and_those_without_a_date_last(courses, new_customer):
    undated = courses.create_fake_course(title="א קורס", starts_on=None)
    later = courses.create_fake_course(title="ב קורס", starts_on="2027-06-01")
    sooner = courses.create_fake_course(title="ג קורס", starts_on="2027-05-01")

    order = [
        c["id"]
        for c in courses.listing(new_customer())
        if c["id"] in {undated["id"], later["id"], sooner["id"]}
    ]

    assert order == [sooner["id"], later["id"], undated["id"]]


def test_a_withdrawn_course_is_hidden_from_customers_and_kept_for_the_owner(courses, new_customer):
    course = courses.create_fake_course()
    courses.withdraw(course["id"])

    assert course["id"] not in [c["id"] for c in courses.listing(new_customer())]
    kept = next(c for c in courses.listing("owner") if c["id"] == course["id"])
    assert kept["active"] is False


def test_a_course_is_changed_and_its_date_and_price_cleared(courses):
    course = courses.create_fake_course()

    changed = (
        courses.update_by_id(
            course["id"], {"title": "חדש", "starts_on": None, "price_minor": None}, persona="owner"
        )
        .assert_ok(200)
        .as_dict
    )

    assert (changed["title"], changed["starts_on"], changed["price_minor"]) == ("חדש", None, None)


@pytest.mark.parametrize(
    "payload",
    [
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 81},
        {"title": "x", "subtitle": "y" * 121},
        {"title": "x", "price_minor": -1},
        {"title": "x", "starts_on": "soon"},
    ],
    ids=["empty", "blank", "long title", "long line", "negative price", "bad date"],
)
def test_a_course_that_makes_no_sense_is_refused(courses, payload):
    assert courses.create(payload, persona="owner").status_code == 422


def test_the_button_opens_whatsapp_with_the_course_named_when_the_shop_has_a_number(courses, new_customer):
    made = courses.create_fake_course(title="קורס ברברינג")

    seen = next(c for c in courses.listing(new_customer()) if c["id"] == made["id"])

    if seen["whatsapp_url"] is None:
        pytest.skip("this copy of the shop has no SHOP_WHATSAPP set")
    link = urlparse(seen["whatsapp_url"])
    assert (link.scheme, link.netloc) == ("https", "wa.me")
    assert "קורס ברברינג" in parse_qs(link.query)["text"][0]


@pytest.mark.parametrize(
    ("raw", "ending", "kind"),
    [(JPEG_HEAD, ".jpg", "image/jpeg"), (PNG_1X1, ".png", "image/png"), (WEBP_HEAD, ".webp", "image/webp")],
)
def test_a_picture_is_accepted_by_its_bytes_and_served(courses, api, raw, ending, kind):
    course = courses.create_fake_course()

    saved = courses.set_image(course["id"], raw).assert_ok(200).as_dict

    assert saved["image_url"].startswith("/media/course-") and saved["image_url"].endswith(ending)
    served = api.request("GET", saved["image_url"], persona=None)
    assert (served.status_code, served.headers["content-type"], served.raw.content) == (200, kind, raw)


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (GIF_HEAD, "invalid_image"),
        (b"<script>alert(1)</script>", "invalid_image"),
        (JPEG_HEAD + b"\x00" * 3_000_000, "image_too_large"),
    ],
    ids=["a gif", "a script", "too large"],
)
def test_a_picture_that_is_not_one_is_refused_and_the_course_keeps_none(courses, raw, code):
    course = courses.create_fake_course()

    assert_refused(courses.set_image(course["id"], raw), 422, code)
    assert next(c for c in courses.listing("owner") if c["id"] == course["id"])["image_url"] is None


def test_a_new_picture_replaces_the_old_one(courses, api):
    course = courses.create_fake_course()
    first = courses.set_image(course["id"], JPEG_HEAD).assert_ok(200).as_dict["image_url"]

    second = courses.set_image(course["id"], PNG_1X1).assert_ok(200).as_dict["image_url"]

    assert first != second
    assert api.request("GET", first, persona=None).status_code == 404
    assert api.request("GET", second, persona=None).status_code == 200


def test_removing_a_picture_takes_it_off_the_course_and_off_the_server(courses, api):
    course = courses.create_fake_course()
    url = courses.set_image(course["id"], PNG_1X1).assert_ok(200).as_dict["image_url"]

    removed = courses.remove_image(course["id"]).assert_ok(200).as_dict

    assert removed["image_url"] is None
    assert api.request("GET", url, persona=None).status_code == 404


@pytest.mark.parametrize("name", ["../barber.db", "..%2Fbarber.db", "course-nope.jpg", "anything.png"])
def test_the_media_route_serves_no_other_file(api, name):
    assert api.request("GET", f"/media/{name}", persona=None).status_code == 404
