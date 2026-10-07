"""A booking too close to cancel or move: the buttons are not offered, the row says why, and
the way to ask the shop is a WhatsApp link. The server's refusal stays tested in tests/barber."""

import json
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import expect

from obj.barber import CANCEL_CUTOFF_HOURS
from utils.helpers import now_utc, to_iso

SHOP_WHATSAPP = "https://wa.me/972500000000"


def hours_from_now(hours: float) -> str:
    t = now_utc() + timedelta(hours=hours)
    return to_iso(t.replace(second=0, microsecond=0) + timedelta(minutes=15 - t.minute % 15))


def shop_with_whatsapp(page):
    def patch(route):
        response = route.fetch()
        body = response.json()
        body["links"] = {**body.get("links", {}), "whatsapp": SHOP_WHATSAPP}
        route.fulfill(response=response, body=json.dumps(body))

    page.route("**/shop", patch)


@pytest.fixture
def quarter_service(services):
    return services.create_fake_service(duration_minutes=15)


@pytest.fixture
def own_barber(barbers):
    return barbers.create_fake_barber()


def booked(bookings, barber, haircut, account, hours):
    made = bookings.create_booking(
        barber["id"], haircut["id"], hours_from_now(hours), persona=account["persona"]
    )
    return made["start_local"][11:16]


def test_a_booking_closer_than_the_cutoff_offers_neither_button_and_says_why(
    own_barber, shop, bookings, account, quarter_service
):
    hhmm = booked(bookings, own_barber, quarter_service, account, CANCEL_CUTOFF_HOURS - 6)
    signed_in = shop.sign_in_as(account)

    row = signed_in.row_at(hhmm)

    expect(row.get_by_test_id("cancel")).to_have_count(0)
    expect(row.get_by_test_id("move")).to_have_count(0)
    note = signed_in.text(row.get_by_test_id("late-note"))
    assert f"אי אפשר לבטל או לשנות תור פחות מ־{CANCEL_CUTOFF_HOURS} שעות לפני." in note, note


def test_a_booking_far_enough_ahead_has_both_buttons_and_no_note(
    own_barber, shop, bookings, account, quarter_service, shop_tz
):
    hhmm = booked(bookings, own_barber, quarter_service, account, CANCEL_CUTOFF_HOURS + 48)
    signed_in = shop.sign_in_as(account)

    row = signed_in.row_at(hhmm)

    expect(row.get_by_test_id("cancel")).to_be_visible()
    expect(row.get_by_test_id("move")).to_be_visible()
    expect(row.get_by_test_id("late-note")).to_have_count(0)


def test_the_note_links_to_the_shops_whatsapp_naming_the_booking(
    own_barber, shop, bookings, account, quarter_service
):
    hhmm = booked(bookings, own_barber, quarter_service, account, 3)
    shop_with_whatsapp(shop.page)
    signed_in = shop.sign_in_as(account)

    link = signed_in.row_at(hhmm).get_by_test_id("late-whatsapp")

    expect(link).to_have_attribute("target", "_blank")
    assert "noopener" in link.get_attribute("rel")
    href = urlparse(link.get_attribute("href"))
    assert f"{href.scheme}://{href.netloc}{href.path}" == SHOP_WHATSAPP
    assert hhmm in parse_qs(href.query)["text"][0]


def test_without_a_whatsapp_number_the_note_still_says_why_and_has_no_link(
    own_barber, shop, bookings, account, quarter_service
):
    hhmm = booked(bookings, own_barber, quarter_service, account, 3)
    shop.page.route(
        "**/shop",
        lambda route: route.fulfill(
            response=route.fetch(),
            body=json.dumps({**route.fetch().json(), "links": {}}),
        ),
    )
    signed_in = shop.sign_in_as(account)

    row = signed_in.row_at(hhmm)

    expect(row.get_by_test_id("late-note")).to_be_visible()
    expect(row.get_by_test_id("late-whatsapp")).to_have_count(0)


def test_the_owner_may_still_cancel_a_booking_that_is_close(
    own_barber, owner_screen, bookings, account, quarter_service
):
    hhmm = booked(bookings, own_barber, quarter_service, account, 3)
    owner = owner_screen().select_barber(own_barber["id"])

    row = owner.row_at(hhmm)

    expect(row.get_by_test_id("cancel")).to_be_visible()
    expect(row.get_by_test_id("late-note")).to_have_count(0)
