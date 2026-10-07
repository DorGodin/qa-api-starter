"""After the appointment: stars at a tap, then words if the customer likes. A booking cannot be
made in the past, so the page is told - by the answer to its own list request - that one is over;
what the server decides about that is tested in the product's suite and in tests/barber."""

import json

import pytest
from playwright.sync_api import expect

from utils.local_time import at_local, local_day


@pytest.fixture
def own_barber(barbers):
    return barbers.create_fake_barber()


class Told:
    """The list request answered as if the booking were over, and the review requests recorded."""

    def __init__(self, page, booking_id, review=None, reviewable=True, refuse=None):
        self.booking_id, self.review, self.reviewable, self.refuse, self.sent = (
            booking_id,
            review,
            reviewable,
            refuse,
            [],
        )
        page.route("**/bookings?*", self.list_)
        page.route("**/bookings/*/review", self.review_)

    def list_(self, route):
        response = route.fetch()
        body = response.json()
        for booking in body["content"]:
            if booking["id"] == self.booking_id:
                booking["reviewable"] = self.reviewable and self.review is None
                booking["review"] = self.review
        route.fulfill(response=response, body=json.dumps(body))

    def review_(self, route):
        request = route.request
        self.sent.append((request.method, json.loads(request.post_data)))
        if self.refuse:
            route.fulfill(status=409, content_type="application/json", body=json.dumps(self.refuse))
            return
        if request.method == "POST":
            self.review = {"stars": self.sent[-1][1]["stars"], "text": None}
        else:
            self.review = {**self.review, "text": self.sent[-1][1]["text"] or None}
        route.fulfill(status=200, content_type="application/json", body="{}")


def over(bookings, barber, haircut, account, shop_tz, days=8):
    return bookings.create_booking(
        barber["id"],
        haircut["id"],
        at_local(shop_tz, local_day(shop_tz, days), "10:00"),
        persona=account["persona"],
    )


def open_list(shop, account, booking, **told):
    seen = Told(shop.page, booking["id"], **told)
    shop.sign_in_as(account)
    return shop, seen


def test_a_booking_that_is_over_asks_how_it_was_with_five_stars(
    own_barber, shop, account, bookings, ui_haircut, shop_tz
):
    shop, _ = open_list(shop, account, over(bookings, own_barber, ui_haircut, account, shop_tz))
    shop.show_tab("mine")

    card = shop.by("review-card")

    expect(card).to_have_attribute("data-state", "ask")
    assert own_barber["display_name"] in shop.text(card.locator("h3"))
    expect(card.locator(".stars button")).to_have_count(5)


def test_the_stars_have_names_a_screen_reader_can_say(
    own_barber, shop, account, bookings, ui_haircut, shop_tz
):
    shop, _ = open_list(shop, account, over(bookings, own_barber, ui_haircut, account, shop_tz))
    shop.show_tab("mine")

    names = [shop.by(f"star-{n}").get_attribute("aria-label") for n in range(1, 6)]

    assert names == ["כוכב אחד", "2 כוכבים", "3 כוכבים", "4 כוכבים", "5 כוכבים"]


def test_a_tap_on_a_star_sends_that_many_and_thanks_the_customer(
    own_barber, shop, account, bookings, ui_haircut, shop_tz
):
    shop, seen = open_list(shop, account, over(bookings, own_barber, ui_haircut, account, shop_tz))
    shop.show_tab("mine")

    shop.by("star-4").click()
    shop.settled()

    assert seen.sent == [("POST", {"stars": 4})]
    expect(shop.by("review-card")).to_have_attribute("data-state", "thanks")
    expect(shop.by("review-text")).to_be_visible()
    assert "דירגת 4 כוכבים" in shop.text(shop.by("booking-detail").first)


def test_the_words_are_sent_after_the_stars_and_the_card_goes(
    own_barber, shop, account, bookings, ui_haircut, shop_tz
):
    shop, seen = open_list(shop, account, over(bookings, own_barber, ui_haircut, account, shop_tz))
    shop.show_tab("mine")
    shop.by("star-5").click()
    shop.settled()

    shop.by("review-text").fill("אלוף העולם")
    shop.by("review-send").click()
    shop.settled()

    assert seen.sent[-1] == ("PATCH", {"text": "אלוף העולם"})
    expect(shop.by("review-card")).to_have_count(0)
    assert "תודה" in shop.text(shop.message())


def test_finishing_without_words_closes_the_card_and_sends_nothing_more(
    own_barber, shop, account, bookings, ui_haircut, shop_tz
):
    shop, seen = open_list(shop, account, over(bookings, own_barber, ui_haircut, account, shop_tz))
    shop.show_tab("mine")
    shop.by("star-3").click()
    shop.settled()

    shop.by("review-done").click()
    shop.settled()

    assert seen.sent == [("POST", {"stars": 3})]
    expect(shop.by("review-card")).to_have_count(0)


def test_not_now_hides_the_card_and_it_stays_hidden_after_the_page_is_opened_again(
    own_barber, shop, account, bookings, ui_haircut, shop_tz
):
    shop, seen = open_list(shop, account, over(bookings, own_barber, ui_haircut, account, shop_tz))
    shop.show_tab("mine")

    shop.by("review-later").click()
    shop.settled()
    shop.reload()
    shop.show_tab("mine")

    expect(shop.by("review-card")).to_have_count(0)
    assert seen.sent == []


def test_a_booking_that_is_not_over_has_no_card(own_barber, shop, account, bookings, ui_haircut, shop_tz):
    shop, _ = open_list(
        shop, account, over(bookings, own_barber, ui_haircut, account, shop_tz), reviewable=False
    )
    shop.show_tab("mine")

    expect(shop.by("review-card")).to_have_count(0)


def test_a_booking_already_reviewed_has_no_card_and_says_what_was_given(
    own_barber, shop, account, bookings, ui_haircut, shop_tz
):
    shop, _ = open_list(
        shop,
        account,
        over(bookings, own_barber, ui_haircut, account, shop_tz),
        review={"stars": 5, "text": None},
    )
    shop.show_tab("mine")

    expect(shop.by("review-card")).to_have_count(0)
    assert "דירגת 5 כוכבים" in shop.text(shop.by("booking-detail").first)


def test_a_refusal_from_the_server_is_said_in_hebrew(
    own_barber, shop, account, bookings, ui_haircut, shop_tz
):
    shop, _ = open_list(
        shop,
        account,
        over(bookings, own_barber, ui_haircut, account, shop_tz),
        refuse={"detail": "x", "code": "already_reviewed"},
    )
    shop.show_tab("mine")

    shop.by("star-5").click()
    shop.settled()

    assert "כבר דירגת" in shop.text(shop.message())


def test_the_barber_and_the_owner_see_the_stars_and_the_words_in_the_row(
    own_barber, owner_screen, account, bookings, ui_haircut, shop_tz
):
    booking = over(bookings, own_barber, ui_haircut, account, shop_tz)
    owner = owner_screen()
    Told(owner.page, booking["id"], review={"stars": 4, "text": "מעולה"}, reviewable=False)
    owner.select_barber(own_barber["id"])
    owner.page.reload()
    owner.settled()
    owner.select_barber(own_barber["id"])

    detail = owner.text(owner.row_at("10:00").get_by_test_id("booking-detail"))

    assert "★★★★" in detail and "מעולה" in detail
