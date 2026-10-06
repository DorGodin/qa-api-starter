"""A customer's booking from 14:00 up to 16:00 is a request until the barber answers:
the card, the list, and being told - in the page, not by text message."""

import pytest
from playwright.sync_api import expect

from obj.barber.booking_page import plain
from utils.local_time import at_local, local_day


@pytest.fixture
def own_barber(barbers):
    return barbers.create_fake_barber()


def waiting_booking(bookings, barber, haircut, account, shop_tz, days, hhmm="15:00"):
    return bookings.create_booking(
        barber["id"],
        haircut["id"],
        at_local(shop_tz, local_day(shop_tz, days), hhmm),
        persona=account["persona"],
    )


def test_a_booking_in_the_afternoon_hours_is_answered_by_a_request(
    own_barber, signed_in, ui_haircut, shop_tz
):
    signed_in.choose(own_barber["id"], ui_haircut["id"], local_day(shop_tz, 6)).pick("15:00").book(
        keep_answer=True
    )

    assert signed_in.last_answer["title"] == "הבקשה נשלחה"
    assert signed_in.last_answer["note"] == f"{own_barber['display_name']} יאשר או ידחה את התור."
    expect(signed_in.by("booking-done-note")).to_be_visible()


def test_the_list_says_the_booking_waits_for_the_barber(own_barber, signed_in, ui_haircut, shop_tz):
    signed_in.choose(own_barber["id"], ui_haircut["id"], local_day(shop_tz, 6)).pick("15:00").book()

    row = signed_in.row_at("15:00")

    expect(row).to_have_attribute("data-approval", "pending")
    assert "ממתין לאישור של " + own_barber["display_name"] in signed_in.text(
        row.get_by_test_id("booking-detail")
    )
    expect(row.get_by_test_id("cancel")).to_be_visible()


@pytest.mark.parametrize("hhmm", ["13:45", "16:00"])
def test_a_booking_outside_the_hours_is_booked_at_once(own_barber, signed_in, ui_haircut, shop_tz, hhmm):
    signed_in.choose(own_barber["id"], ui_haircut["id"], local_day(shop_tz, 6)).pick(hhmm).book(
        keep_answer=True
    )

    assert signed_in.last_answer["title"] == "התור נקבע"
    assert signed_in.last_answer["note"] is None
    expect(signed_in.by("booking-done-note")).to_be_hidden()
    signed_in.go_to_my_bookings()
    expect(signed_in.row_at(hhmm)).to_have_attribute("data-approval", "")


def test_the_customer_is_told_in_the_page_when_the_barber_says_yes(
    shop, account, bookings, barbers, own_barber, ui_haircut, shop_tz
):
    made = waiting_booking(bookings, own_barber, ui_haircut, account, shop_tz, 7)
    shop.sign_in_as(account)
    expect(shop.row_at("15:00")).to_have_attribute("data-approval", "pending")

    bookings.approve(made["id"], persona="owner").assert_ok(200)
    shop.reload()

    expect(shop.by("popup")).to_be_visible()
    assert "אישר את התור" in plain(shop.by("popup-title").inner_text())
    assert "15:00" in plain(shop.by("popup-text").inner_text())
    shop.close_popup()
    assert "מאושר" in shop.text(shop.row_at("15:00").get_by_test_id("booking-detail"))
    expect(shop.row_at("15:00")).to_have_attribute("data-approval", "approved")


def test_the_customer_is_told_once(shop, account, bookings, own_barber, ui_haircut, shop_tz):
    made = waiting_booking(bookings, own_barber, ui_haircut, account, shop_tz, 7)
    shop.sign_in_as(account)
    bookings.approve(made["id"], persona="owner").assert_ok(200)
    shop.reload()
    shop.close_popup()

    shop.reload()

    expect(shop.by("popup")).to_be_hidden()


def test_the_customer_who_is_told_no_can_choose_another_time(
    shop, account, bookings, own_barber, ui_haircut, shop_tz
):
    made = waiting_booking(bookings, own_barber, ui_haircut, account, shop_tz, 7)
    shop.sign_in_as(account)
    bookings.decline(made["id"], persona="owner").assert_ok(200)

    shop.reload()

    expect(shop.by("popup")).to_be_visible()
    assert plain(shop.by("popup-title").inner_text()) == "התור לא אושר"
    expect(shop.by("popup")).to_have_attribute("data-kind", "news")
    expect(shop.by("popup-action")).to_have_text("בחירת שעה אחרת")
    shop.by("popup-action").click()
    expect(shop.by("popup")).to_be_hidden()
    expect(shop.by("slot").first).to_be_visible()
    assert "לא אושר" in shop.text(shop.row_at("15:00").get_by_test_id("booking-detail"))


def test_the_barber_answers_from_the_diary_and_the_customer_is_not_asked(
    shop, account, bookings, own_barber, ui_haircut, shop_tz
):
    waiting_booking(bookings, own_barber, ui_haircut, account, shop_tz, 8)
    shop.sign_in(own_barber["username"], own_barber["password"])
    row = shop.row_at("15:00")
    expect(row.get_by_test_id("approve")).to_be_visible()
    expect(row.get_by_test_id("decline")).to_be_visible()
    expect(row.get_by_test_id("cancel")).to_have_count(0)

    shop.answer("15:00", "approve")

    expect(shop.row_at("15:00").get_by_test_id("approve")).to_have_count(0)
    expect(shop.row_at("15:00")).to_have_attribute("data-approval", "approved")
    assert "אושר" in shop.text(shop.message())


def test_a_barber_who_says_no_frees_the_time(
    shop, account, bookings, barbers, own_barber, ui_haircut, shop_tz, new_customer
):
    waiting_booking(bookings, own_barber, ui_haircut, account, shop_tz, 8)
    shop.sign_in(own_barber["username"], own_barber["password"])

    shop.answer("15:00", "decline")

    expect(shop.row_at("15:00")).to_have_attribute("data-approval", "declined")
    assert "נדחה" in shop.text(shop.row_at("15:00").get_by_test_id("booking-detail"))
    free = [
        s["start"]
        for s in barbers.slots(
            own_barber["id"], local_day(shop_tz, 8), ui_haircut["id"], persona=account["persona"]
        )
    ]
    assert at_local(shop_tz, local_day(shop_tz, 8), "15:00").strftime("%Y-%m-%dT%H:%M:%SZ") in free


def test_the_owner_answers_for_the_barber(owner_screen, account, bookings, own_barber, ui_haircut, shop_tz):
    waiting_booking(bookings, own_barber, ui_haircut, account, shop_tz, 9)
    owner = owner_screen()

    owner.select_barber(own_barber["id"])
    owner.answer("15:00", "approve")

    expect(owner.row_at("15:00")).to_have_attribute("data-approval", "approved")


def test_the_page_looks_again_while_a_booking_waits_and_tells_when_it_is_answered(
    shop, account, bookings, own_barber, ui_haircut, shop_tz
):
    made = waiting_booking(bookings, own_barber, ui_haircut, account, shop_tz, 7)
    shop.page.clock.install()
    shop.sign_in_as(account)
    expect(shop.row_at("15:00")).to_have_attribute("data-approval", "pending")

    bookings.approve(made["id"], persona="owner").assert_ok(200)
    shop.page.clock.fast_forward("00:00:50")

    expect(shop.by("popup")).to_be_visible()
    assert "אישר את התור" in plain(shop.by("popup-title").inner_text())
