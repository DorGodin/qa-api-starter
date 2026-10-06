"""A customer books and cancels through the page, and every result is checked
twice: on the screen, and through the API behind it."""

from playwright.sync_api import expect

from obj.barber.booking_page import greeting
from utils.local_time import at_local, local_day, parse_instant


def test_signing_in_replaces_the_form_with_the_booking_screen(shop, account):
    shop.sign_in_as(account)

    expect(shop.by("login-form")).to_be_hidden()
    expect(shop.by("app")).to_be_visible()
    expect(shop.by("display-name")).to_have_text(greeting(account["display_name"]))


def test_a_computer_shows_booking_and_the_bookings_side_by_side_without_tabs(signed_in):
    if signed_in.page.viewport_size["width"] <= 760:
        expect(signed_in.by("tabbar")).to_be_visible()
        return

    expect(signed_in.by("tabbar")).to_be_hidden()
    expect(signed_in.by("left-panel")).to_be_visible()
    expect(signed_in.by("right-panel")).to_be_visible()


def test_the_staff_see_their_name_and_role_not_a_greeting(shop, credentials):
    shop.sign_in(*credentials("owner"))

    expect(shop.by("display-name")).to_contain_text("· בעלים")
    expect(shop.by("display-name")).not_to_contain_text("שלום")


def test_the_book_button_appears_only_after_a_time_is_chosen(signed_in, ui_barber, ui_haircut, shop_tz):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 3))

    expect(signed_in.by("confirm")).to_be_hidden()
    signed_in.pick("10:00")
    expect(signed_in.by("confirm")).to_contain_text("10:00")


def test_a_customer_books_a_time_and_sees_it(signed_in, bookings, account, ui_barber, ui_haircut, shop_tz):
    day = local_day(shop_tz, 3)
    signed_in.choose(ui_barber["id"], ui_haircut["id"], day).pick("11:00").book()

    assert signed_in.last_answer["title"] == "התור נקבע"
    expect(signed_in.message()).to_have_text("")
    assert "80.00 ₪" in signed_in.text(signed_in.row_at("11:00"))
    assert "11:00" not in signed_in.times(), "a booked time is still offered"

    stored = bookings.listing(persona=account["persona"])["content"]
    assert len(stored) == 1
    assert parse_instant(stored[0]["start"]) == at_local(shop_tz, day, "11:00")


def test_cancelling_from_the_list_gives_the_time_back(
    signed_in, bookings, account, ui_barber, ui_haircut, shop_tz
):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 4)).pick("12:00").book()

    signed_in.cancel("12:00")

    expect(signed_in.message()).to_contain_text("בוטל")
    expect(signed_in.message()).to_have_attribute("data-kind", "cancelled")
    expect(signed_in.message()).to_have_css("color", "rgb(168, 50, 58)")
    expect(signed_in.row_at("12:00")).to_contain_text("בוטל")
    assert "12:00" in signed_in.times()
    assert bookings.listing(persona=account["persona"], status="confirmed")["total"] == 0


def test_a_booking_the_customer_cancelled_is_gone_once_they_leave_the_app(
    signed_in, ui_barber, ui_haircut, shop_tz
):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 4)).pick("12:00").book()
    signed_in.cancel("12:00")
    expect(signed_in.row_at("12:00")).to_have_attribute("data-status", "cancelled")

    signed_in.reload()

    expect(signed_in.row_at("12:00")).to_have_count(0)


def test_a_booking_the_shop_cancelled_stays_for_twelve_hours_even_after_the_customer_comes_back(
    shop, account, bookings, ui_barber, ui_haircut, shop_tz
):
    day = local_day(shop_tz, 4)
    booking = bookings.create_booking(
        ui_barber["id"], ui_haircut["id"], at_local(shop_tz, day, "12:00"), persona=account["persona"]
    )
    bookings.cancel(booking["id"], persona="owner").assert_ok(200)
    shop.page.clock.install()

    shop.sign_in_as(account)
    expect(shop.row_at("12:00")).to_have_attribute("data-status", "cancelled")
    shop.reload()
    expect(shop.row_at("12:00")).to_have_attribute("data-status", "cancelled")

    shop.page.clock.fast_forward("11:58:00")
    expect(shop.row_at("12:00")).to_have_attribute("data-status", "cancelled")
    shop.page.clock.fast_forward("00:03:00")

    expect(shop.row_at("12:00")).to_have_count(0)


def test_a_booking_the_customer_cancelled_is_gone_after_twelve_hours(
    shop, account, bookings, ui_barber, ui_haircut, shop_tz
):
    day = local_day(shop_tz, 4)
    bookings.create_booking(
        ui_barber["id"], ui_haircut["id"], at_local(shop_tz, day, "12:00"), persona=account["persona"]
    )
    shop.page.clock.install()
    shop.sign_in_as(account)
    shop.cancel("12:00")
    expect(shop.row_at("12:00")).to_have_attribute("data-status", "cancelled")

    shop.page.clock.fast_forward("11:59:00")
    expect(shop.row_at("12:00")).to_have_attribute("data-status", "cancelled")
    shop.page.clock.fast_forward("00:02:00")

    expect(shop.row_at("12:00")).to_have_count(0)


def test_a_double_click_on_book_books_once(signed_in, bookings, account, ui_barber, ui_haircut, shop_tz):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 5)).pick("13:00")
    sent = []
    signed_in.page.on(
        "request", lambda r: sent.append(r) if r.method == "POST" and r.url.endswith("/bookings") else None
    )

    signed_in.by("book").dblclick()
    signed_in.settled()
    expect(signed_in.by("booking-done")).to_be_visible()

    # Counted on the wire. With one Idempotency-Key per chosen time, a second
    # request would be answered as a success, so the screen alone cannot show
    # whether the page sent it twice.
    assert len(sent) == 1, f"the page sent {len(sent)} booking requests for one double click"

    assert bookings.listing(persona=account["persona"])["total"] == 1
    expect(signed_in.rows()).to_have_count(1)
    # The server would refuse a second booking anyway. What the page must also
    # not do is send it: the refusal would replace "Booked" with "Someone just
    # booked 13:00" - told to the very customer who just booked it.
    expect(signed_in.by("popup")).to_be_hidden()
    expect(signed_in.by("booking-done-title")).to_have_text("התור נקבע")
    expect(signed_in.message()).to_have_text("")


def test_an_account_made_through_the_api_signs_in_on_the_page_with_its_password(shop, customers):
    account = customers.create_account()

    shop.sign_in(account["username"], account["password"])

    expect(shop.by("app")).to_be_visible()
    expect(shop.by("display-name")).to_have_text(greeting(account["display_name"]))


def test_a_remembered_sign_in_the_server_no_longer_accepts_is_dropped_on_refresh(shop):
    shop.open()
    shop.page.evaluate("() => sessionStorage.setItem('barber.session', 'expired-or-forged')")

    shop.reload()

    expect(shop.by("code-request-form")).to_be_visible()
    expect(shop.by("app")).to_be_hidden()
    assert (
        shop.page.evaluate("() => sessionStorage.getItem('barber.session')") is None
    ), "a dead sign-in is not kept"
