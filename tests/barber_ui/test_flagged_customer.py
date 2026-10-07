"""A flagged customer is told nothing: their booking looks like any request."""

from playwright.sync_api import expect

from tests.barber.test_flagged_customers import cancel_three
from utils.local_time import local_day


def test_a_flagged_customers_booking_at_any_hour_is_a_request_like_any_other(
    barbers, shop, account, bookings, ui_haircut, shop_tz
):
    own = barbers.create_fake_barber()
    cancel_three(bookings, own, ui_haircut, account["persona"], shop_tz)
    signed_in = shop.sign_in_as(account)

    signed_in.choose(own["id"], ui_haircut["id"], local_day(shop_tz, 9)).pick("10:00").book(keep_answer=True)

    assert signed_in.last_answer["title"] == "הבקשה נשלחה"
    signed_in.go_to_my_bookings()
    expect(signed_in.row_at("10:00")).to_have_attribute("data-approval", "pending")
