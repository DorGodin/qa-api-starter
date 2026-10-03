"""A customer moves a booking from the page: the same booking at a new time,
checked on the screen and through the API behind it."""

from datetime import timedelta

from playwright.sync_api import expect

from obj.barber import MOVE_CUTOFF_HOURS
from utils.helpers import now_utc, to_iso
from utils.local_time import at_local, local_day, parse_instant


def test_a_customer_moves_a_booking_and_it_is_the_same_booking_at_the_new_time(
    signed_in, bookings, account, ui_barber, ui_haircut, shop_tz
):
    day = local_day(shop_tz, 5)
    signed_in.choose(ui_barber["id"], ui_haircut["id"], day).pick("11:00").book()
    [before] = bookings.listing(persona=account["persona"])["content"]

    signed_in.start_moving("11:00")

    expect(signed_in.by("moving-text")).to_contain_text("11:00")
    expect(signed_in.by("barber")).to_be_disabled()
    expect(signed_in.by("service")).to_be_disabled()
    # The booking's own time is not in its way: a quarter later is offered.
    assert "11:15" in signed_in.times()

    signed_in.pick("15:00")
    expect(signed_in.by("book")).to_have_text("הזזת התור")
    signed_in.book()

    assert signed_in.last_popup["title"] == "✓ התור הוזז"
    expect(signed_in.row_at("15:00")).to_be_visible()
    expect(signed_in.row_at("11:00")).to_have_count(0)
    expect(signed_in.by("moving")).to_be_hidden()
    expect(signed_in.by("book")).to_have_text("קביעת התור")
    expect(signed_in.by("barber")).to_be_enabled()
    [after] = bookings.listing(persona=account["persona"])["content"]
    assert after["id"] == before["id"]
    assert parse_instant(after["start"]) == at_local(shop_tz, day, "15:00")
    assert after["price_minor"] == before["price_minor"]


def test_a_time_taken_while_choosing_is_explained_and_the_booking_stays(
    signed_in, bookings, account, ui_barber, ui_haircut, new_customer, shop_tz
):
    day = local_day(shop_tz, 6)
    signed_in.choose(ui_barber["id"], ui_haircut["id"], day).pick("10:00").book()
    signed_in.start_moving("10:00").pick("14:00")
    bookings.create_booking(
        ui_barber["id"], ui_haircut["id"], at_local(shop_tz, day, "14:00"), persona=new_customer()
    )

    signed_in.book()

    assert signed_in.last_popup["title"] == "השעה כבר תפוסה"
    assert "14:00" in signed_in.last_popup["text"]
    [kept] = bookings.listing(persona=account["persona"])["content"]
    assert parse_instant(kept["start"]) == at_local(shop_tz, day, "10:00")


def test_a_late_move_is_explained_in_hebrew(shop, bookings, account, barbers, ui_haircut, shop_tz):
    soon = barbers.create_fake_barber()
    t = now_utc() + timedelta(hours=2)
    start = t.replace(second=0, microsecond=0) + timedelta(minutes=15 - t.minute % 15)
    booking = bookings.create_booking(soon["id"], ui_haircut["id"], to_iso(start), persona=account["persona"])
    hhmm = booking["start_local"][11:16]
    signed_in = shop.sign_in_as(account)

    signed_in.start_moving(hhmm)
    signed_in.pick(signed_in.times()[-1]).book()

    assert f"{MOVE_CUTOFF_HOURS} שעות" in signed_in.last_popup["text"]
    [kept] = bookings.listing(persona=account["persona"])["content"]
    assert parse_instant(kept["start"]) == start


def test_stopping_a_move_puts_the_panel_back_and_changes_nothing(
    signed_in, bookings, account, ui_barber, ui_haircut, shop_tz
):
    day = local_day(shop_tz, 7)
    signed_in.choose(ui_barber["id"], ui_haircut["id"], day).pick("12:00").book()

    signed_in.start_moving("12:00").stop_moving()

    expect(signed_in.by("left-title")).to_have_text("קביעת תור")
    expect(signed_in.by("book")).to_have_text("קביעת התור")
    expect(signed_in.by("service")).to_be_enabled()
    [kept] = bookings.listing(persona=account["persona"])["content"]
    assert parse_instant(kept["start"]) == at_local(shop_tz, day, "12:00")
