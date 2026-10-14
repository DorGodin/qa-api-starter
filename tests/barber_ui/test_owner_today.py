"""The staff's day, above the diary: four cards - how many today, how many wait for a yes, what to have
ready, who is next - and today by its hours. And who is coming: the customer's name, to the staff."""

from datetime import datetime, timedelta

import pytest
from playwright.sync_api import expect

from obj.barber.booking_page import BookingPage
from utils.helpers import now_utc, to_iso
from utils.local_time import at_local, local_day


def later_today(hours: float, shop_tz, minutes: int = 30) -> str:
    """A quarter hour on the shop's clock, today, the given hours from now, for a booking of that many
    minutes that ends today too - or a skip in the last hours of the day, when there is no later today."""
    t = now_utc() + timedelta(hours=hours)
    t = t.replace(second=0, microsecond=0) + timedelta(minutes=15 - t.minute % 15)
    if (t + timedelta(minutes=minutes) - timedelta(seconds=1)).astimezone(shop_tz).date() != local_day(
        shop_tz, 0
    ):
        pytest.skip("too late in the shop's day to book later today")
    return to_iso(t)


@pytest.fixture
def day(barbers, services, bookings, products, account, shop_tz):
    """A barber of the test's own with a day: a walk-in, a customer with two of a product kept, and a
    request that waits for the barber's yes."""
    barber = barbers.create_fake_barber()
    cut = services.create_fake_service(duration_minutes=30)
    asks = services.create_fake_service(duration_minutes=30, requires_approval=True)
    walk_in = (
        bookings.book_guest(barber["id"], cut["id"], later_today(1, shop_tz), "יואב", persona="owner")
        .assert_ok(201)
        .as_dict
    )
    kept = bookings.create_booking(
        barber["id"], cut["id"], later_today(2, shop_tz), persona=account["persona"]
    )
    product = products.create_fake_product(name="ווקס QA")
    products.keep(kept["id"], product["id"], persona=account["persona"], quantity=2).assert_ok(200)
    waiting = bookings.create_booking(
        barber["id"], asks["id"], later_today(3, shop_tz), persona=account["persona"]
    )
    gone = bookings.book_guest(barber["id"], cut["id"], later_today(4, shop_tz), "בוטל", persona="owner")
    bookings.cancel(gone.assert_ok(201).as_dict["id"], persona="owner").assert_ok(200)
    return {"barber": barber, "walk_in": walk_in, "kept": kept, "waiting": waiting, "product": product}


def test_the_owner_sees_the_day_in_four_cards(day, owner_screen, account):
    owner = owner_screen().select_barber(day["barber"]["id"])

    def card(name):
        box = owner.by(f"today-{name}")
        return owner.text(box.locator("strong")), owner.text(box.locator("small"))

    assert card("count")[0] == "3"
    # The customer's booking may itself fall in the hours that wait for the barber, by the hour the
    # test runs at: what waits is read from what the shop said, not assumed.
    waiting = [b for b in (day["walk_in"], day["kept"], day["waiting"]) if b["approval"] == "pending"]
    number, times = card("waiting")
    assert number == str(len(waiting)) and all(b["start_local"][11:16] in times for b in waiting)
    number, names = card("products")
    assert number == "2" and "ווקס QA ×2" in names
    time, who = card("next")
    assert time == day["walk_in"]["start_local"][11:16] and "יואב" in who
    expect(owner.by("today-title")).to_contain_text("היום")


def test_the_day_by_its_hours_has_a_block_for_each_booking_with_who_is_coming(day, owner_screen, account):
    owner = owner_screen().select_barber(day["barber"]["id"])

    blocks = owner.by("timeline-booking")

    expect(blocks).to_have_count(3)
    expect(owner.by("timeline")).to_have_attribute("aria-hidden", "true")
    kept = blocks.filter(has_text=day["kept"]["start_local"][11:16])
    assert account["display_name"] in owner.text(kept) and "2 מוצרים" in owner.text(kept)
    waiting = owner.page.locator(f'[data-testid="timeline-booking"][data-id="{day["waiting"]["id"]}"]')
    expect(waiting).to_have_class("slot-block pending")
    tops = [b.bounding_box()["y"] for b in blocks.all()]
    assert tops == sorted(tops), "earlier is higher"


def test_a_block_takes_the_eye_to_its_booking_in_the_list(day, owner_screen):
    owner = owner_screen().select_barber(day["barber"]["id"])
    row = owner.page.locator(f'[data-testid="booking-row"][data-id="{day["waiting"]["id"]}"]')

    owner.page.locator(f'[data-testid="timeline-booking"][data-id="{day["waiting"]["id"]}"]').click()

    expect(row).to_be_in_viewport()
    expect(row.get_by_test_id("approve")).to_be_visible()


def test_the_list_says_who_is_coming_to_the_staff(day, owner_screen, account):
    owner = owner_screen().select_barber(day["barber"]["id"])

    detail = owner.text(
        owner.page.locator(f'[data-testid="booking-row"][data-id="{day["kept"]["id"]}"]').get_by_test_id(
            "booking-detail"
        )
    )

    assert account["display_name"] in detail


def test_a_barber_sees_their_own_day(day, browser, env_config, barbers):
    screen = BookingPage(browser.new_page(), env_config["url"]).sign_in(
        day["barber"]["username"], day["barber"]["password"]
    )

    assert screen.text(screen.by("today-count").locator("strong")) == "3"
    expect(screen.by("timeline-booking")).to_have_count(3)


def test_a_customer_has_no_day_of_cards(day, signed_in):
    expect(signed_in.by("today")).to_be_hidden()


def test_a_day_with_nothing_says_so(barbers, owner_screen):
    barber = barbers.create_fake_barber()

    owner = owner_screen().select_barber(barber["id"])

    assert owner.text(owner.by("today-count").locator("strong")) == "0"
    expect(owner.by("timeline-empty")).to_be_visible()
    expect(owner.by("today-waiting")).to_be_disabled()
    assert owner.text(owner.by("today-next").locator("small")) == "אין עוד היום"


def test_the_next_booking_is_the_first_still_to_come(day, owner_screen, page):
    """What is over cannot be booked from outside, but the cards read the time from the browser:
    its clock is moved past the first booking of the day."""
    first = day["walk_in"]["start_local"]
    page.clock.set_fixed_time(datetime.fromisoformat(first) + timedelta(minutes=20))

    owner = owner_screen().select_barber(day["barber"]["id"])

    assert owner.text(owner.by("today-next").locator("strong")) == day["kept"]["start_local"][11:16]
    assert owner.text(owner.by("today-count").locator("strong")) == "3", "the one that is over still counts"


def test_a_customers_cancellation_leaves_the_diary_and_is_told_until_it_is_seen(
    barbers, ui_haircut, bookings, account, owner_screen, shop_tz
):
    barber = barbers.create_fake_barber()
    made = bookings.create_booking(
        barber["id"],
        ui_haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 6), "11:00"),
        persona=account["persona"],
    )
    bookings.cancel(made["id"], persona=account["persona"]).assert_ok(200)
    owner = owner_screen().select_barber(barber["id"])

    expect(owner.row_at("11:00")).to_have_count(0)
    note = owner.text(owner.by("cancel-note"))
    assert account["display_name"] in note and "11:00" in note and "ביטל/ה" in note
    owner.by("cancel-seen").click()
    expect(owner.by("cancel-notes")).to_be_hidden()
    owner.reload()
    owner.select_barber(barber["id"])
    expect(owner.by("cancel-notes")).to_be_hidden()


def test_a_cancellation_the_shop_made_itself_is_not_told(
    barbers, ui_haircut, bookings, account, owner_screen, shop_tz
):
    barber = barbers.create_fake_barber()
    made = bookings.create_booking(
        barber["id"],
        ui_haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 6), "12:00"),
        persona=account["persona"],
    )
    bookings.cancel(made["id"], persona="owner").assert_ok(200)

    owner = owner_screen().select_barber(barber["id"])

    expect(owner.row_at("12:00")).to_have_count(0)
    expect(owner.by("cancel-notes")).to_be_hidden()


def test_the_diary_tells_a_cancellation_that_comes_while_it_is_open(
    barbers, ui_haircut, bookings, account, owner_screen, page, shop_tz
):
    barber = barbers.create_fake_barber()
    made = bookings.create_booking(
        barber["id"],
        ui_haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 6), "13:00"),
        persona=account["persona"],
    )
    page.clock.install()
    owner = owner_screen().select_barber(barber["id"])
    expect(owner.row_at("13:00")).to_have_count(1)

    bookings.cancel(made["id"], persona=account["persona"]).assert_ok(200)
    page.clock.run_for(61_000)

    expect(owner.row_at("13:00")).to_have_count(0)
    expect(owner.by("cancel-note")).to_have_count(1)


def test_the_days_span_ends_when_its_last_booking_ends(day, owner_screen, services):
    owner = owner_screen().select_barber(day["barber"]["id"])

    span = owner.text(owner.by("today-count").locator("small"))

    last_start = day["waiting"]["start_local"]
    end = datetime.fromisoformat(last_start) + timedelta(minutes=30)
    assert span.endswith(end.strftime("%H:%M")), span


def test_signing_out_leaves_nothing_of_the_day_in_the_page(day, owner_screen, account):
    owner = owner_screen().select_barber(day["barber"]["id"])
    expect(owner.by("timeline-booking")).to_have_count(3)

    owner.by("logout").click()

    expect(owner.by("today")).to_be_hidden()
    expect(owner.page.locator('[data-testid="timeline-booking"]')).to_have_count(0)
    assert account["display_name"] not in owner.page.evaluate("document.body.innerHTML")
    assert "ווקס QA" not in owner.page.evaluate("document.body.innerHTML")
