"""The month's calendar on the booking page: a free day says how many times it
has - the same number its list then shows - a full day says so, a day the barber
does not work cannot be chosen, and the whole month is reachable by keyboard."""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import timedelta

from playwright.sync_api import expect

from obj.barber import BOOKING_WINDOW_DAYS
from utils.local_time import at_local, local_day


def test_a_free_day_names_the_number_of_times_its_list_then_shows(
    shop, account, barbers, ui_haircut, shop_tz
):
    two_hours = barbers.create_fake_barber(opening="10:00", closing="12:00")
    day = local_day(shop_tz, 3)

    screen = shop.sign_in_as(account).choose(two_hours["id"], ui_haircut["id"], day)

    expect(screen.day(day)).to_have_attribute("aria-selected", "true")
    # Ten to twelve, a 30 minute service, a start every quarter: 10:00 to 11:30.
    assert len(screen.times()) == 7
    expect(screen.day(day)).to_have_accessible_name(re.compile(", 7 שעות פנויות$"))


def test_a_day_off_cannot_be_chosen_and_the_day_chosen_stays(shop, account, barbers, ui_haircut, shop_tz):
    barber = barbers.create_fake_barber()
    day, off = local_day(shop_tz, 3), local_day(shop_tz, 4)
    barbers.add_time_off(barber["id"], off).assert_ok(201)
    screen = shop.sign_in_as(account).choose(barber["id"], ui_haircut["id"], day)
    screen.show_month_of(off)

    # Playwright will not press what is marked unavailable; a finger will.
    screen.day(off).click(force=True)
    screen.settled()

    expect(screen.day(off)).to_have_attribute("aria-disabled", "true")
    expect(screen.day(off)).to_have_accessible_name(re.compile("הספר לא עובד ביום הזה$"))
    expect(screen.day(off)).to_have_attribute("aria-selected", "false")
    assert screen.chosen_day() == day


def test_a_full_day_says_full_and_is_marked_unavailable(
    shop, account, barbers, bookings, ui_haircut, new_customer, shop_tz
):
    half_hour = barbers.create_fake_barber(opening="10:00", closing="10:30")
    full = local_day(shop_tz, 5)
    bookings.create_booking(
        half_hour["id"], ui_haircut["id"], at_local(shop_tz, full, "10:00"), persona=new_customer()
    )

    screen = shop.sign_in_as(account).choose(half_hour["id"], ui_haircut["id"], local_day(shop_tz, 3))
    screen.show_month_of(full)

    expect(screen.day(full)).to_contain_text("מלא")
    expect(screen.day(full)).to_have_attribute("aria-disabled", "true")
    expect(screen.day(full)).to_have_accessible_name(re.compile(", מלא$"))


def test_the_keyboard_moves_through_the_days_and_enter_chooses(signed_in, ui_barber, ui_haircut, shop_tz):
    day = local_day(shop_tz, 3)
    signed_in.choose(ui_barber["id"], ui_haircut["id"], day)
    signed_in.day(day).focus()

    # Right to left: the left arrow is the next day.
    signed_in.page.keyboard.press("ArrowLeft")
    signed_in.settled()
    after = day + timedelta(days=1)
    expect(signed_in.day(after)).to_be_focused()
    with signed_in.page.expect_response(lambda r: "/availability" in r.url and after.isoformat() in r.url):
        signed_in.page.keyboard.press("Enter")
    signed_in.settled()

    assert signed_in.chosen_day() == after
    expect(signed_in.day(after)).to_have_attribute("aria-selected", "true")
    expect(signed_in.by("days").locator('td[tabindex="0"]')).to_have_count(1)


def test_page_down_turns_to_the_next_month_on_the_same_day(signed_in, ui_barber, ui_haircut, shop_tz):
    day = local_day(shop_tz, 3)
    signed_in.choose(ui_barber["id"], ui_haircut["id"], day)
    signed_in.day(day).focus()

    signed_in.page.keyboard.press("PageDown")
    signed_in.settled()

    first_of_next = (day.replace(day=1) + timedelta(days=32)).replace(day=1)
    same_day = first_of_next.replace(day=min(day.day, monthrange(first_of_next.year, first_of_next.month)[1]))
    expect(signed_in.day(same_day)).to_be_focused()


def test_the_month_turns_only_within_the_booking_window(signed_in, ui_barber, ui_haircut, shop_tz):
    today, last = local_day(shop_tz, 0), local_day(shop_tz, BOOKING_WINDOW_DAYS)
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 1))

    signed_in.show_month_of(today)
    expect(signed_in.by("prev-month")).to_be_disabled()
    signed_in.show_month_of(last)
    expect(signed_in.by("next-month")).to_be_disabled()
    expect(signed_in.day(last)).not_to_have_attribute("aria-disabled", "true")
    if last.month == (last + timedelta(days=1)).month:
        expect(signed_in.day(last + timedelta(days=1))).to_have_accessible_name(re.compile("לא ניתן לקבוע$"))


def test_a_day_already_over_cannot_be_chosen(signed_in, ui_barber, ui_haircut, shop_tz):
    yesterday = local_day(shop_tz, -1)
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 1))
    if yesterday.month != local_day(shop_tz, 0).month:
        expect(signed_in.by("prev-month")).to_be_disabled()
        return
    signed_in.show_month_of(yesterday)

    signed_in.day(yesterday).click(force=True)
    signed_in.settled()

    expect(signed_in.day(yesterday)).to_have_attribute("aria-disabled", "true")
    expect(signed_in.day(yesterday)).to_have_accessible_name(re.compile("לא ניתן לקבוע$"))
    assert signed_in.chosen_day() == local_day(shop_tz, 1)


def test_the_screen_opens_on_a_day_with_a_time_to_offer(signed_in):
    if signed_in.by("days").locator("td.free").count() == 0:
        return

    expect(signed_in.day(signed_in.chosen_day())).to_have_class(re.compile(r"\bfree\b"))
