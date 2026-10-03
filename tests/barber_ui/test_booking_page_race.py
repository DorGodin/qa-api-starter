"""Two customers looking at the same free time.

Both screens show 10:00 as free. One presses Book first. The other, still
looking at a screen that says 10:00 is free, presses Book a moment later - and
must be told plainly that it has just gone, not shown an error code or, worse,
a booking.

The true same-instant race is proven at the API level (tests/barber/
test_concurrency.py). This is what that race looks like to the person who lost.
"""

from playwright.sync_api import expect

from obj.barber.booking_page import BookingPage
from utils.local_time import local_day


def test_a_time_taken_while_you_were_looking_is_explained(
    new_context, env_config, customers, bookings, barbers, ui_haircut, shop_tz, sms_inbox
):
    contested = barbers.create_fake_barber(opening="09:00", closing="13:00")
    day = local_day(shop_tz, 3)
    screens = []
    for _ in range(2):
        account = customers.sign_in_by_code(sms_inbox)
        screen = BookingPage(new_context().new_page(), env_config["url"]).sign_in_as(account)
        screen.choose(contested["id"], ui_haircut["id"], day).pick("10:00")
        screens.append(screen)
    first, second = screens

    first.book()
    second.book()

    expect(first.message()).to_contain_text("נקבע:")
    expect(second.message()).to_contain_text("מישהו בדיוק קבע את 10:00")
    assert first.last_popup["kind"] == "ok" and "התור נקבע" in first.last_popup["title"]
    assert second.last_popup == {**second.last_popup, "kind": "error", "title": "השעה כבר תפוסה"}
    assert "10:00" in second.last_popup["text"]
    expect(second.message()).to_have_attribute("data-kind", "error")
    assert "10:00" not in second.times(), "the losing screen still offers the time it just lost"
    owner_view = bookings.listing(persona="owner", barber_id=contested["id"], status="confirmed")
    assert owner_view["total"] == 1
