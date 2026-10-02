"""The owner takes a barber who left out of the shop, from the screen - and the
customer who had a booking with them still sees who it is with."""

from playwright.sync_api import expect

from utils.local_time import at_local, local_day


def test_the_owner_takes_a_barber_out_and_their_diary_stays(
    owner_screen, barbers, bookings, account, ui_haircut, shop_tz
):
    leaving = barbers.create_fake_barber()
    bookings.create_booking(
        leaving["id"],
        ui_haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 5), "11:00"),
        persona=account["persona"],
    )
    screen = owner_screen().select_barber(leaving["id"])
    expect(screen.by("barber-active-toggle")).to_have_text("הוצאת הספר מהפעילות")

    screen.toggle_barber_active()

    expect(screen.message()).to_contain_text("הוצא מהפעילות")
    expect(screen.message()).to_have_attribute("data-kind", "ok")
    expect(screen.by("barber").locator("option:checked")).to_contain_text("(לא פעיל)")
    expect(screen.by("barber-left")).to_be_visible()
    expect(screen.by("slot")).to_have_count(0)
    expect(screen.row_at("11:00")).to_be_visible()
    expect(screen.by("barber-active-toggle")).to_have_text("החזרת הספר לפעילות")
    [seen] = [
        b for b in barbers.find(persona="owner").assert_ok(200).as_dict["content"] if b["id"] == leaving["id"]
    ]
    assert seen["active"] is False


def test_a_barber_brought_back_is_offered_again(owner_screen, barbers, shop_tz):
    leaving = barbers.create_fake_barber()
    barbers.set_active(leaving["id"], False).assert_ok(200)
    screen = owner_screen().select_barber(leaving["id"])
    expect(screen.by("barber-left")).to_be_visible()

    screen.toggle_barber_active()

    expect(screen.message()).to_contain_text("חזר לפעילות")
    expect(screen.by("barber-left")).to_be_hidden()
    expect(screen.by("slot").first).to_be_visible()


def test_a_customer_is_not_offered_the_barber_but_still_sees_who_their_booking_is_with(
    shop, barbers, bookings, account, ui_haircut, shop_tz
):
    leaving = barbers.create_fake_barber()
    bookings.create_booking(
        leaving["id"],
        ui_haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 5), "12:00"),
        persona=account["persona"],
    )
    barbers.set_active(leaving["id"], False).assert_ok(200)

    signed_in = shop.sign_in(account["username"], account["password"])

    offered = signed_in.by("barber").locator("option").evaluate_all("os => os.map(o => o.value)")
    assert leaving["id"] not in offered
    expect(signed_in.row_at("12:00")).to_contain_text(leaving["display_name"])
