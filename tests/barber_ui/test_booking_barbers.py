"""The barbers on the booking page: a pill each, by full name, one chosen - a
radio group a keyboard moves through as it does the times."""

from __future__ import annotations

import re

from playwright.sync_api import expect

from utils.local_time import local_day


def test_every_barber_the_customer_can_book_is_a_pill_by_full_name_and_one_is_chosen(
    signed_in, barbers, account
):
    bookable = barbers.find(persona=account["persona"]).assert_ok(200).as_dict["content"]

    pills = signed_in.by("barbers").get_by_role("radio")

    assert [signed_in.text(p) for p in pills.all()] == [b["display_name"] for b in bookable]
    expect(signed_in.by("barbers").locator('[aria-checked="true"]')).to_have_count(1)
    expect(signed_in.by("barbers").locator('[tabindex="0"]')).to_have_count(1)
    assert signed_in.chosen_barber().get_attribute("data-id") == signed_in.by("barber").input_value()


def test_pressing_a_barber_offers_that_barbers_times(signed_in, barbers, ui_barber, ui_haircut, shop_tz):
    day = local_day(shop_tz, 3)

    signed_in.choose(ui_barber["id"], ui_haircut["id"], day)

    expect(signed_in.barber_pill(ui_barber["id"])).to_have_attribute("aria-checked", "true")
    expected = [s["start_local"][11:16] for s in barbers.slots(ui_barber["id"], day, ui_haircut["id"])]
    assert signed_in.times() == expected


def test_the_arrows_move_to_the_next_barber_and_choose_them(signed_in, ui_barber, ui_haircut, shop_tz):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 3))
    pills = signed_in.by("barbers").get_by_role("radio")
    ids = [p.get_attribute("data-id") for p in pills.all()]
    at = ids.index(ui_barber["id"])
    following = ids[at + 1] if at + 1 < len(ids) else ids[at - 1]
    key = "ArrowLeft" if at + 1 < len(ids) else "ArrowRight"
    signed_in.barber_pill(ui_barber["id"]).focus()

    with signed_in.page.expect_response(lambda r: f"/barbers/{following}/availability" in r.url):
        signed_in.page.keyboard.press(key)
    signed_in.settled()

    expect(signed_in.barber_pill(following)).to_be_focused()
    expect(signed_in.barber_pill(following)).to_have_attribute("aria-checked", "true")
    assert signed_in.by("barber").input_value() == following


def test_a_barber_who_does_not_work_the_day_chosen_moves_the_calendar_to_a_free_day(
    shop, account, barbers, ui_barber, ui_haircut, shop_tz
):
    day = local_day(shop_tz, 3)
    off_that_day = barbers.create_fake_barber()
    barbers.add_time_off(off_that_day["id"], day).assert_ok(201)
    screen = shop.sign_in_as(account).choose(ui_barber["id"], ui_haircut["id"], day)

    screen.choose_barber(off_that_day["id"])

    assert screen.chosen_day() != day, "the day the barber is off stayed chosen"
    expect(screen.day(screen.chosen_day())).to_have_class(re.compile(r"\bfree\b"))
    expect(screen.by("slot").first).to_be_visible()
    expect(screen.by("no-slots")).to_be_hidden()
