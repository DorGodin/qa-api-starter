"""A booking just made becomes the customer's regular time in a tap: how often, and the next time it
would be; the list says it stands, and stopping it keeps the booking."""

from playwright.sync_api import expect

from utils.local_time import local_day


def test_a_booking_just_made_becomes_a_standing_one_and_stops_from_the_list(
    barbers, shop, account, ui_haircut, shop_tz
):
    barber = barbers.create_fake_barber()
    signed_in = shop.sign_in_as(account)
    signed_in.choose(barber["id"], ui_haircut["id"], local_day(shop_tz, 3)).pick("10:00").book(
        keep_answer=True
    )

    expect(signed_in.by("standing-offer")).to_be_hidden()
    signed_in.by("standing-open").click()
    expect(signed_in.by("standing-offer")).to_be_visible()
    expect(signed_in.by("standing-make")).to_contain_text("כן, להפוך לקבוע")
    expect(signed_in.by("standing-next")).to_contain_text("10:00")
    three_weeks = signed_in.text(signed_in.by("standing-next"))
    every = signed_in.by("standing-every")
    expect(every.get_by_role("radio", name="3 שבועות")).to_have_attribute("aria-checked", "true")
    every.get_by_role("radio", name="שבועיים").click()
    expect(every.get_by_role("radio", name="שבועיים")).to_have_attribute("aria-checked", "true")
    assert signed_in.text(signed_in.by("standing-next")) != three_weeks, "the next date follows the choice"
    # The three choices share one row.
    tops = {round(b.bounding_box()["y"]) for b in every.get_by_role("radio").all()}
    assert len(tops) == 1, tops
    signed_in.by("standing-make").click()
    signed_in.settled()

    expect(signed_in.by("standing-made")).to_contain_text("תור קבוע כל שבועיים")
    expect(signed_in.by("standing-offer")).to_be_hidden()
    signed_in.go_to_my_bookings()
    row = signed_in.row_at("10:00")
    expect(row.get_by_test_id("booking-standing")).to_have_text("קבוע כל שבועיים · הבא ייקבע אחרי הביקור")

    row.get_by_test_id("stop-standing").click()
    signed_in.settled()
    expect(signed_in.message()).to_contain_text("התור הקבוע הופסק")
    expect(signed_in.row_at("10:00").get_by_test_id("booking-standing")).to_have_count(0)
    expect(signed_in.row_at("10:00")).to_have_attribute("data-status", "confirmed")


def test_no_thanks_folds_the_offer_back_and_makes_nothing(
    barbers, shop, account, bookings, ui_haircut, shop_tz
):
    barber = barbers.create_fake_barber()
    signed_in = shop.sign_in_as(account)
    signed_in.choose(barber["id"], ui_haircut["id"], local_day(shop_tz, 3)).pick("11:00").book(
        keep_answer=True
    )
    signed_in.by("standing-open").click()

    signed_in.by("standing-cancel").click()

    expect(signed_in.by("standing-offer")).to_be_hidden()
    expect(signed_in.by("standing-open")).to_be_focused()
    mine = bookings.listing(persona=account["persona"])["content"]
    assert all(b["standing"] is None for b in mine)
