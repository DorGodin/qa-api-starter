"""Every booking answers in a modal popup: green when it is booked, red when it
could not be - and "the time is taken" said as exactly that."""

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect

from utils.local_time import at_local, local_day


def test_a_booking_is_confirmed_in_a_popup_that_says_what_was_booked(
    signed_in, ui_barber, ui_haircut, shop_tz
):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 8)).pick("16:00").book(
        keep_popup=True
    )

    popup = signed_in.by("popup")
    expect(popup).to_be_visible()
    expect(popup).to_have_attribute("data-kind", "ok")
    assert "התור נקבע" in signed_in.last_popup["title"]
    assert "16:00" in signed_in.last_popup["text"] and "80.00 ₪" in signed_in.last_popup["text"]
    expect(signed_in.by("popup-close")).to_be_focused()


def test_the_popup_closes_with_its_button_and_with_escape(signed_in, ui_barber, ui_haircut, shop_tz):
    day = local_day(shop_tz, 8)
    signed_in.choose(ui_barber["id"], ui_haircut["id"], day).pick("17:00").book(keep_popup=True)
    signed_in.close_popup()

    signed_in.pick("18:00").book(keep_popup=True)
    signed_in.page.keyboard.press("Escape")

    expect(signed_in.by("popup")).to_be_hidden()


def test_while_the_popup_is_open_nothing_behind_it_can_be_pressed(signed_in, ui_barber, ui_haircut, shop_tz):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 9)).pick("11:00").book(
        keep_popup=True
    )

    assert signed_in.by("popup").evaluate(
        "d => d.matches(':modal')"
    ), "a popup the page stays usable behind is not modal"
    with pytest.raises(PlaywrightTimeout):
        signed_in.by("slot").first.click(timeout=1500)


def test_a_refusal_that_is_not_a_taken_time_says_it_could_not_book(
    shop, account, bookings, barbers, ui_haircut, shop_tz
):
    first, second = barbers.create_fake_barber(), barbers.create_fake_barber()
    shop.sign_in(account["username"], account["password"])
    day = local_day(shop_tz, 9)
    shop.choose(second["id"], ui_haircut["id"], day).pick("12:00")
    # While the customer looks, they book 12:00 somewhere else - in another tab.
    bookings.create_booking(
        first["id"], ui_haircut["id"], at_local(shop_tz, day, "12:00"), persona=account["persona"]
    )

    shop.book()

    assert shop.last_popup["kind"] == "error"
    assert shop.last_popup["title"] == "לא הצלחנו לקבוע את התור"
    assert "כבר יש לך תור" in shop.last_popup["text"]
