"""A booking that goes through is answered by a card in the booking panel, where
the form was; one that could not be made is answered by a modal popup, red - and
"the time is taken" said as exactly that."""

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect

from utils.local_time import at_local, local_day


def test_a_booking_is_confirmed_by_a_card_that_says_what_was_booked(signed_in, ui_barber, ui_haircut, shop_tz):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 8)).pick("16:00").book(
        keep_answer=True
    )

    expect(signed_in.by("booking-done")).to_be_visible()
    expect(signed_in.by("popup")).to_be_hidden()
    expect(signed_in.by("book-panel")).to_be_hidden()
    assert signed_in.last_answer["title"] == "התור נקבע"
    assert "16:00" in signed_in.last_answer["text"] and "80.00 ₪" in signed_in.last_answer["text"]
    expect(signed_in.by("booking-done-title")).to_be_focused()


def test_the_card_leads_to_the_new_booking_in_the_list(signed_in, ui_barber, ui_haircut, shop_tz):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 8)).pick("17:00").book(
        keep_answer=True
    )

    signed_in.go_to_my_bookings()

    expect(signed_in.row_at("17:00")).to_be_focused()


def test_the_card_leads_back_to_the_form_for_another_booking(signed_in, ui_barber, ui_haircut, shop_tz):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 8)).pick("18:00").book(
        keep_answer=True
    )

    signed_in.book_another()

    expect(signed_in.by("book-panel")).to_be_visible()
    expect(signed_in.by("slot").first).to_be_visible()
    expect(signed_in.chosen_barber()).to_be_focused()


@pytest.fixture
def refused_booking(shop, account, bookings, barbers, ui_haircut, shop_tz):
    first, second = barbers.create_fake_barber(), barbers.create_fake_barber()
    shop.sign_in_as(account)
    day = local_day(shop_tz, 9)
    shop.choose(second["id"], ui_haircut["id"], day).pick("12:00")
    bookings.create_booking(
        first["id"], ui_haircut["id"], at_local(shop_tz, day, "12:00"), persona=account["persona"]
    )
    return shop


def test_a_refusal_that_is_not_a_taken_time_says_it_could_not_book(refused_booking):
    refused_booking.book()

    assert refused_booking.last_answer["kind"] == "error"
    assert refused_booking.last_answer["title"] == "לא הצלחנו לקבוע את התור"
    assert "כבר יש לך תור" in refused_booking.last_answer["text"]
    expect(refused_booking.by("booking-done")).to_be_hidden()


def test_while_a_refusal_is_open_nothing_behind_it_can_be_pressed(refused_booking):
    refused_booking.book(keep_answer=True)

    assert refused_booking.by("popup").evaluate(
        "d => d.matches(':modal')"
    ), "a popup the page stays usable behind is not modal"
    with pytest.raises(PlaywrightTimeout):
        refused_booking.by("slot").first.click(timeout=1500)


@pytest.mark.parametrize("how", ["its button", "Escape"])
def test_a_refusal_closes_with_its_button_and_with_escape(refused_booking, how):
    refused_booking.book(keep_answer=True)

    if how == "its button":
        refused_booking.close_popup()
    else:
        refused_booking.page.keyboard.press("Escape")

    expect(refused_booking.by("popup")).to_be_hidden()


def test_a_third_booking_ahead_is_refused_saying_how_many_may_be_held(
    shop, account, bookings, barbers, ui_haircut, shop_tz
):
    barber = barbers.create_fake_barber()
    day = local_day(shop_tz, 10)
    for hhmm in ("10:00", "11:00"):
        bookings.create_booking(
            barber["id"], ui_haircut["id"], at_local(shop_tz, day, hhmm), persona=account["persona"]
        )
    shop.sign_in_as(account)

    shop.choose(barber["id"], ui_haircut["id"], day).pick("13:00").book()

    assert shop.last_answer["kind"] == "error"
    assert "עד 2 תורים" in shop.last_answer["text"] and "לבטל" in shop.last_answer["text"], shop.last_answer[
        "text"
    ]
