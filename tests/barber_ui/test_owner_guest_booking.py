"""The owner books, from the screen, someone who phoned or walked in - by name,
into the diary the site books into."""

import secrets

from playwright.sync_api import expect

from utils.local_time import at_local, local_day, parse_instant


def test_the_owner_books_a_caller_by_name_and_the_diary_shows_who_is_coming(
    owner_screen, barbers, bookings, ui_haircut, shop_tz
):
    # The barber exists before the owner signs in: the screen reads the
    # barbers once, at sign-in.
    barber = barbers.create_fake_barber()
    day = local_day(shop_tz, 5)
    screen = owner_screen().select_barber(barber["id"])

    screen.choose(barber["id"], ui_haircut["id"], day).pick("11:00").book_for("משה כהן")

    assert screen.last_popup["title"] == "✓ התור נקבע"
    assert "משה כהן" in screen.last_popup["text"]
    expect(screen.row_at("11:00")).to_contain_text("משה כהן")
    expect(screen.row_at("11:00")).to_contain_text("בלי חשבון")
    expect(screen.by("guest-name")).to_have_value("")
    assert "11:00" not in screen.times()
    [stored] = bookings.listing(persona="owner", barber_id=barber["id"])["content"]
    assert stored["guest_name"] == "משה כהן" and stored["customer_id"] is None
    assert parse_instant(stored["start"]) == at_local(shop_tz, day, "11:00")


def test_without_a_name_nothing_is_booked_and_the_field_says_so(
    owner_screen, barbers, bookings, ui_haircut, shop_tz
):
    barber = barbers.create_fake_barber()
    screen = owner_screen().select_barber(barber["id"])
    screen.choose(barber["id"], ui_haircut["id"], local_day(shop_tz, 5)).pick("12:00")

    screen.by("book").click()
    screen.settled()

    expect(screen.message()).to_contain_text("צריך לכתוב את שם הלקוח")
    expect(screen.by("guest-name")).to_be_focused()
    expect(screen.by("popup")).to_be_hidden()
    assert bookings.listing(persona="owner", barber_id=barber["id"])["total"] == 0


def test_a_name_that_looks_like_html_is_shown_as_text(owner_screen, barbers, ui_haircut, shop_tz):
    barber = barbers.create_fake_barber()
    screen = owner_screen().select_barber(barber["id"])
    name = '<img src=x onerror="document.title=1">'

    screen.choose(
        barber["id"],
        ui_haircut["id"],
        local_day(shop_tz, 6),
    ).pick("10:00").book_for(name)

    expect(screen.row_at("10:00")).to_contain_text(name)
    assert screen.page.locator('[data-testid="bookings"] img').count() == 0


def test_a_customer_never_gets_the_name_field(signed_in):
    expect(signed_in.by("book-panel")).to_be_visible()
    expect(signed_in.by("guest-field")).to_be_hidden()


def test_a_withdrawn_service_is_not_offered_for_booking_and_does_not_spoil_the_screen(owner_screen, services):
    # Named to sort first, where the screen's default choice would land on it.
    withdrawn = services.create_fake_service(name=f"!withdrawn {secrets.token_hex(4)}")
    services.deactivate(withdrawn["id"])

    screen = owner_screen()

    assert withdrawn["id"] not in screen.by("service").locator("option").evaluate_all(
        "os => os.map(o => o.value)"
    )
    expect(screen.message()).not_to_have_attribute("data-kind", "error")
