"""The shop's shelf: the owner keeps the products, a customer reads them, and one with a booking
ahead asks for a product to be kept for it. Nothing is paid and nothing is counted.

A booking that is over cannot be made from outside, so "nothing is kept for a booking that is over"
is the product's own test; here the closed booking is a cancelled one."""

from __future__ import annotations

import pytest

from obj.barber.courses import GIF_HEAD, PNG_1X1
from utils.assertions import assert_refused
from utils.local_time import at_local, local_day


@pytest.fixture
def me(new_customer):
    return new_customer()


@pytest.fixture
def ahead(bookings, barbers, haircut, me, shop_tz):
    barber = barbers.create_fake_barber()
    start = at_local(shop_tz, local_day(shop_tz, 5), "11:00")
    return bookings.create_booking(barber["id"], haircut["id"], start, persona=me)


def test_the_owner_adds_a_product_and_a_customer_reads_it(products, me):
    made = products.create_fake_product(name="ווקס מט QA", line="100 מ״ל", price_minor=6500)

    seen = products.one(made["id"], persona=me)

    assert (seen["name"], seen["line"], seen["price_minor"], seen["currency"]) == (
        "ווקס מט QA",
        "100 מ״ל",
        6500,
        "ILS",
    )
    assert (seen["active"], seen["in_stock"], seen["image_url"]) == (True, True, None)


@pytest.mark.parametrize(
    "fields",
    [{"name": " "}, {"name": "x" * 81}, {"line": "x" * 121}, {"price_minor": -1}, {"price_minor": None}],
)
def test_a_product_needs_a_name_and_a_price_that_is_not_negative(products, fields):
    payload = {**products.build_product_payload(), **fields}

    assert products.create(payload, persona="owner").status_code == 422


def test_only_the_owner_keeps_the_shelf(products, me):
    product = products.create_fake_product()

    assert_refused(products.create(products.build_product_payload(), persona=me), 403, "forbidden")
    assert_refused(products.update_by_id(product["id"], {"in_stock": False}, persona=me), 403, "forbidden")
    assert_refused(products.set_image(product["id"], PNG_1X1, persona=me), 403, "forbidden")
    assert_refused(products.remove_image(product["id"], persona=me), 403, "forbidden")
    assert_refused(products.find(persona=None), 401, "unauthorized")


def test_a_withdrawn_product_is_the_owners_alone_and_one_that_ran_out_is_still_shown(products, me):
    gone, out = products.create_fake_product(), products.create_fake_product()
    products.withdraw(gone["id"])
    products.run_out(out["id"])

    seen = {p["id"]: p for p in products.listing(me)}

    assert gone["id"] not in seen and seen[out["id"]]["in_stock"] is False
    assert products.one(gone["id"], persona="owner")["active"] is False


def test_a_change_leaves_what_was_not_sent(products):
    product = products.create_fake_product(line="30 מ״ל", price_minor=8000)

    changed = (
        products.update_by_id(product["id"], {"price_minor": 9000}, persona="owner").assert_ok(200).as_dict
    )

    assert (changed["name"], changed["line"], changed["price_minor"]) == (product["name"], "30 מ״ל", 9000)
    assert_refused(products.update_by_id("prd_nope", {"price_minor": 1}, persona="owner"), 404, "not_found")


def test_a_picture_is_served_to_anyone_and_gone_once_removed(products, api):
    product = products.create_fake_product()

    url = products.set_image(product["id"], PNG_1X1).assert_ok(200).as_dict["image_url"]

    assert url.startswith("/media/product-")
    assert api.request("GET", url, persona=None).raw.content == PNG_1X1
    assert_refused(products.set_image(product["id"], GIF_HEAD), 422, "invalid_image")
    assert products.remove_image(product["id"]).assert_ok(200).as_dict["image_url"] is None
    assert api.request("GET", url, persona=None).status_code == 404


def test_a_product_is_kept_for_a_booking_ahead_and_the_diary_names_it(products, bookings, me, ahead):
    product = products.create_fake_product()

    kept = products.keep(ahead["id"], product["id"], persona=me).assert_ok(200).as_dict

    assert kept["products"] == [{"id": product["id"], "name": product["name"], "quantity": 1}]
    diary = bookings.listing("owner", barber_id=ahead["barber_id"])["content"]
    assert next(b for b in diary if b["id"] == ahead["id"])["products"] == kept["products"]


def test_kept_twice_it_is_kept_once_and_several_keep_their_order(products, me, ahead):
    first, second = products.create_fake_product(), products.create_fake_product()
    products.keep(ahead["id"], first["id"], persona=me).assert_ok(200)
    products.keep(ahead["id"], second["id"], persona=me).assert_ok(200)

    again = products.keep(ahead["id"], first["id"], persona=me).assert_ok(200).as_dict

    assert [p["id"] for p in again["products"]] == [first["id"], second["id"]]


def test_a_kept_product_is_released_and_releasing_twice_is_no_error(products, me, ahead):
    product = products.create_fake_product()
    products.keep(ahead["id"], product["id"], persona=me).assert_ok(200)

    first = products.release(ahead["id"], product["id"], persona=me).assert_ok(200).as_dict
    products.release(ahead["id"], product["id"], persona=me).assert_ok(200)

    assert first["products"] == []


@pytest.mark.parametrize("gone", ["withdraw", "run_out"])
def test_a_product_withdrawn_or_out_of_stock_cannot_be_kept(products, bookings, me, ahead, gone):
    product = products.create_fake_product()
    getattr(products, gone)(product["id"])

    assert_refused(products.keep(ahead["id"], product["id"], persona=me), 422, "product_unavailable")
    assert bookings.get_by_id(ahead["id"], persona=me).as_dict["products"] == []


def test_nothing_is_kept_for_a_cancelled_booking(products, bookings, me, ahead):
    product = products.create_fake_product()
    bookings.cancel(ahead["id"], persona=me).assert_ok(200)

    assert_refused(products.keep(ahead["id"], product["id"], persona=me), 409, "booking_closed")


def test_somebody_elses_booking_is_not_found_and_a_barber_keeps_nothing(
    products, barbers, new_customer, ahead
):
    product = products.create_fake_product()
    barber = barbers.create_fake_barber()

    assert_refused(products.keep(ahead["id"], product["id"], persona=new_customer()), 404, "not_found")
    assert_refused(
        products.keep(ahead["id"], product["id"], persona=barbers.sign_in_as_persona(barber)),
        403,
        "forbidden",
    )
    assert_refused(products.keep(ahead["id"], "prd_nope", persona="owner"), 404, "not_found")
    products.keep(ahead["id"], product["id"], persona="owner").assert_ok(200)


def test_the_number_asked_for_is_set_not_added(products, me, ahead):
    product = products.create_fake_product()
    products.keep(ahead["id"], product["id"], persona=me, quantity=2).assert_ok(200)

    raised = products.keep(ahead["id"], product["id"], persona=me, quantity=3).assert_ok(200).as_dict
    lowered = products.keep(ahead["id"], product["id"], persona=me, quantity=1).assert_ok(200).as_dict

    assert [p["quantity"] for p in raised["products"]] == [3]
    assert [p["quantity"] for p in lowered["products"]] == [1]


@pytest.mark.parametrize("quantity", [0, 10, -1, 1.5, "two"])
def test_from_one_to_nine_of_a_product_and_nothing_else(products, bookings, me, ahead, quantity):
    product = products.create_fake_product()

    assert products.keep(ahead["id"], product["id"], persona=me, quantity=quantity).status_code == 422
    assert bookings.get_by_id(ahead["id"], persona=me).as_dict["products"] == []
    nine = products.keep(ahead["id"], product["id"], persona=me, quantity=9).assert_ok(200).as_dict
    assert nine["products"][0]["quantity"] == 9


@pytest.mark.parametrize("gone", ["withdraw", "run_out"])
def test_of_a_product_that_ran_out_fewer_may_be_kept_and_never_more(products, bookings, me, ahead, gone):
    product = products.create_fake_product()
    products.keep(ahead["id"], product["id"], persona=me, quantity=3).assert_ok(200)
    getattr(products, gone)(product["id"])

    fewer = products.keep(ahead["id"], product["id"], persona=me, quantity=2).assert_ok(200).as_dict
    more = products.keep(ahead["id"], product["id"], persona=me, quantity=4)

    assert fewer["products"][0]["quantity"] == 2
    assert_refused(more, 422, "product_unavailable")
    assert bookings.get_by_id(ahead["id"], persona=me).as_dict["products"][0]["quantity"] == 2
