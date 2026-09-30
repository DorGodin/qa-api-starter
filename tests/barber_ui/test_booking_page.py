"""A customer books and cancels through the page, and every result is checked
twice: on the screen, and through the API behind it."""

from playwright.sync_api import expect

from utils.local_time import at_local, local_day, parse_instant


def test_signing_in_replaces_the_form_with_the_booking_screen(shop, account):
    shop.sign_in(account["username"], account["password"])

    expect(shop.by("login-form")).to_be_hidden()
    expect(shop.by("app")).to_be_visible()
    expect(shop.by("display-name")).to_contain_text(account["display_name"])


def test_the_book_button_appears_only_after_a_time_is_chosen(signed_in, ui_barber, ui_haircut, shop_tz):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 3))

    expect(signed_in.by("confirm")).to_be_hidden()
    signed_in.pick("10:00")
    expect(signed_in.by("confirm")).to_contain_text("10:00")


def test_a_customer_books_a_time_and_sees_it(signed_in, bookings, account, ui_barber, ui_haircut, shop_tz):
    day = local_day(shop_tz, 3)
    signed_in.choose(ui_barber["id"], ui_haircut["id"], day).pick("11:00").book()

    expect(signed_in.message()).to_contain_text("Booked:")
    expect(signed_in.row_at("11:00")).to_contain_text("₪80.00")
    assert "11:00" not in signed_in.times(), "a booked time is still offered"

    stored = bookings.listing(persona=account["persona"])["content"]
    assert len(stored) == 1
    assert parse_instant(stored[0]["start"]) == at_local(shop_tz, day, "11:00")


def test_cancelling_from_the_list_gives_the_time_back(
    signed_in, bookings, account, ui_barber, ui_haircut, shop_tz
):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 4)).pick("12:00").book()

    signed_in.cancel("12:00")

    expect(signed_in.message()).to_contain_text("Cancelled")
    expect(signed_in.row_at("12:00")).to_contain_text("cancelled")
    assert "12:00" in signed_in.times()
    assert bookings.listing(persona=account["persona"], status="confirmed")["total"] == 0


def test_a_late_cancellation_explains_why_and_keeps_the_booking(
    shop, bookings, account, barbers, ui_haircut, shop_tz
):
    # The barber exists before the customer signs in: the page reads the list
    # of barbers once, at sign-in, as a customer's page would.
    soon = barbers.create_fake_barber()
    signed_in = shop.sign_in(account["username"], account["password"])
    today = local_day(shop_tz, 0)
    signed_in.choose(soon["id"], ui_haircut["id"], today)
    if not signed_in.times():
        signed_in.choose(soon["id"], ui_haircut["id"], local_day(shop_tz, 1))
    # The second time, not the first: the first can be seconds away, and if a
    # quarter hour ticks over between listing it and booking it, the booking is
    # refused as in the past. The second is 15 minutes out - still well inside
    # the 24 hour cutoff.
    soonest = signed_in.times()[1]
    signed_in.pick(soonest).book()

    signed_in.cancel(soonest)

    expect(signed_in.message()).to_contain_text("24 hours")
    (
        expect(signed_in.message()).to_contain_text("call the shop"),
        "say what to do next, not only what went wrong",
    )
    expect(signed_in.message()).to_have_attribute("data-kind", "error")
    assert bookings.listing(persona=account["persona"], status="confirmed")["total"] == 1


def test_a_double_click_on_book_books_once(signed_in, bookings, account, ui_barber, ui_haircut, shop_tz):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 5)).pick("13:00")
    sent = []
    signed_in.page.on(
        "request", lambda r: sent.append(r) if r.method == "POST" and r.url.endswith("/bookings") else None
    )

    signed_in.by("book").dblclick()
    signed_in.settled()

    # Counted on the wire. With one Idempotency-Key per chosen time, a second
    # request would be answered as a success, so the screen alone cannot show
    # whether the page sent it twice.
    assert len(sent) == 1, f"the page sent {len(sent)} booking requests for one double click"

    assert bookings.listing(persona=account["persona"])["total"] == 1
    expect(signed_in.rows()).to_have_count(1)
    # The server would refuse a second booking anyway. What the page must also
    # not do is send it: the refusal would replace "Booked" with "Someone just
    # booked 13:00" - told to the very customer who just booked it.
    expect(signed_in.message()).to_contain_text("Booked:")
    expect(signed_in.message()).to_have_attribute("data-kind", "ok")


def test_signing_up_through_the_page_signs_you_straight_in(shop, customers):
    payload = customers.build_signup_payload()

    shop.sign_up(payload["display_name"], payload["username"], payload["password"])

    expect(shop.by("app")).to_be_visible()
    expect(shop.by("display-name")).to_contain_text(payload["display_name"])
