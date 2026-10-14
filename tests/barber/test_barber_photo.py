"""A barber's picture: the owner's to give and take away, accepted by what its bytes are, and shown
to everyone who chooses a barber."""

from __future__ import annotations

from obj.barber.courses import GIF_HEAD, PNG_1X1, Courses
from utils.assertions import assert_refused


def photo(barbers, barber_id, raw, persona="owner"):
    return barbers.client.request(
        "PUT", f"{barbers.path}/{barber_id}/photo", persona=persona, json=Courses.encode(raw)
    )


def unphoto(barbers, barber_id, persona="owner"):
    return barbers.client.request("DELETE", f"{barbers.path}/{barber_id}/photo", persona=persona)


def listed(barbers, barber_id, persona):
    return next(b for b in barbers.find(persona=persona).assert_ok(200).content if b["id"] == barber_id)


def test_a_barbers_picture_is_shown_to_customers_and_served_to_anyone(barbers, new_customer, api):
    barber = barbers.create_fake_barber()

    url = photo(barbers, barber["id"], PNG_1X1).assert_ok(200).as_dict["photo_url"]

    assert url.startswith("/media/barber-")
    assert listed(barbers, barber["id"], new_customer())["photo_url"] == url
    assert api.request("GET", url, persona=None).raw.content == PNG_1X1


def test_a_picture_taken_away_is_no_longer_served(barbers, api):
    barber = barbers.create_fake_barber()
    url = photo(barbers, barber["id"], PNG_1X1).assert_ok(200).as_dict["photo_url"]

    cleared = unphoto(barbers, barber["id"]).assert_ok(200).as_dict

    assert cleared["photo_url"] is None
    assert api.request("GET", url, persona=None).status_code == 404


def test_a_new_picture_replaces_the_old_one(barbers, api):
    barber = barbers.create_fake_barber()
    first = photo(barbers, barber["id"], PNG_1X1).assert_ok(200).as_dict["photo_url"]

    second = photo(barbers, barber["id"], PNG_1X1).assert_ok(200).as_dict["photo_url"]

    assert second != first and api.request("GET", first, persona=None).status_code == 404


def test_a_barber_without_a_picture_says_so(barbers, new_customer):
    barber = barbers.create_fake_barber()

    assert listed(barbers, barber["id"], new_customer())["photo_url"] is None


def test_only_a_picture_and_only_the_owner(barbers, new_customer):
    barber = barbers.create_fake_barber()

    assert_refused(photo(barbers, barber["id"], GIF_HEAD), 422, "invalid_image")
    assert_refused(photo(barbers, barber["id"], PNG_1X1, persona=new_customer()), 403, "forbidden")
    assert_refused(unphoto(barbers, barber["id"], persona=new_customer()), 403, "forbidden")
    assert_refused(photo(barbers, "usr_nobody", PNG_1X1), 404, "not_found")
