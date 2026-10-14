"""The customer card on the staff's screen, and the cancellations told three at a time."""

from playwright.sync_api import expect

from utils.local_time import at_local, local_day


def test_the_owner_opens_a_customers_card_from_the_diary_and_keeps_a_note(
    barbers, ui_haircut, bookings, account, owner_screen, shop_tz
):
    barber = barbers.create_fake_barber()
    made = bookings.create_booking(
        barber["id"],
        ui_haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 6), "11:00"),
        persona=account["persona"],
    )
    owner = owner_screen().select_barber(barber["id"])

    owner.row_at("11:00").get_by_test_id("open-card").click()
    owner.settled()

    dialog = owner.by("customer-card")
    expect(dialog).to_be_visible()
    expect(owner.by("card-name")).to_have_text(account["display_name"])
    expect(owner.by("card-phone")).to_have_text(account["phone"])
    owner.by("card-note").fill("מספר 2 בצדדים")
    owner.by("card-save").click()
    owner.settled()
    owner.by("card-close").click()
    expect(dialog).to_be_hidden()
    owner.row_at("11:00").get_by_test_id("open-card").click()
    owner.settled()
    expect(owner.by("card-note")).to_have_value("מספר 2 בצדדים")
    assert made["customer_id"]


def test_a_booking_still_ahead_offers_no_not_come_to_and_a_walk_in_has_no_card(
    barbers, ui_haircut, bookings, account, owner_screen, shop_tz
):
    barber = barbers.create_fake_barber()
    bookings.create_booking(
        barber["id"],
        ui_haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 6), "12:00"),
        persona=account["persona"],
    )
    bookings.book_guest(
        barber["id"],
        ui_haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 6), "13:00"),
        "יואב",
        persona="owner",
    ).assert_ok(201)

    owner = owner_screen().select_barber(barber["id"])

    expect(owner.row_at("12:00").get_by_test_id("no-show")).to_have_count(0)
    expect(owner.row_at("13:00").get_by_test_id("open-card")).to_have_count(0)


def test_many_cancellations_are_told_three_and_how_many_more(
    barbers, ui_haircut, bookings, new_customer, owner_screen, shop_tz
):
    barber = barbers.create_fake_barber()
    for hour in ("09:00", "10:00", "11:00", "12:00", "13:00"):
        me = new_customer()
        made = bookings.create_booking(
            barber["id"], ui_haircut["id"], at_local(shop_tz, local_day(shop_tz, 6), hour), persona=me
        )
        bookings.cancel(made["id"], persona=me).assert_ok(200)

    owner = owner_screen().select_barber(barber["id"])

    expect(owner.by("cancel-note")).to_have_count(3)
    expect(owner.by("cancel-more")).to_have_text("ועוד 2 ביטולים")


def test_a_closed_card_and_signing_out_leave_no_note_in_the_page(
    barbers, ui_haircut, bookings, account, owner_screen, shop_tz
):
    barber = barbers.create_fake_barber()
    made = bookings.create_booking(
        barber["id"],
        ui_haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 6), "14:00"),
        persona=account["persona"],
    )
    owner = owner_screen()
    owner.select_barber(barber["id"])
    owner.row_at("14:00").get_by_test_id("open-card").click()
    owner.settled()
    owner.by("card-note").fill("סוד של הצוות")
    owner.by("card-save").click()
    owner.settled()

    owner.page.keyboard.press("Escape")
    expect(owner.by("customer-card")).to_be_hidden()
    expect(owner.by("card-note")).to_have_value("")
    owner.by("logout").click()

    assert "סוד של הצוות" not in owner.page.evaluate(
        "document.body.innerHTML + document.getElementById('card-note').value"
    )
    assert made["customer_id"]


def test_the_buttons_under_a_booking_stand_in_the_middle_of_its_row(
    barbers, ui_haircut, bookings, account, owner_screen, shop_tz
):
    barber = barbers.create_fake_barber()
    bookings.create_booking(
        barber["id"],
        ui_haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 6), "15:00"),
        persona=account["persona"],
    )
    owner = owner_screen().select_barber(barber["id"])
    row = owner.row_at("15:00")

    edges = row.evaluate(
        """(row) => {
            const r = row.getBoundingClientRect(), style = getComputedStyle(row);
            const boxes = [...row.querySelectorAll(":scope > button")].map((b) => b.getBoundingClientRect());
            return [r.left + parseFloat(style.paddingLeft), r.right - parseFloat(style.paddingRight), Math.min(...boxes.map((b) => b.left)), Math.max(...boxes.map((b) => b.right))];
        }"""
    )

    inner_left, inner_right, left, right = edges
    assert abs((left - inner_left) - (inner_right - right)) <= 2, edges
