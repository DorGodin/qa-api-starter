"""Answers that arrive late. Changing a barber, a service or a day asks the server
again, and nothing makes the answers come back in the order they were asked
for. An answer to an earlier choice that lands after the answer to the current
one must be dropped - otherwise the screen shows the times, the hours or the
bookings of a choice that is no longer on it.

Found by a flaky test: in CI the times for today, past 15:00 in the afternoon,
landed after the times for the day chosen, and 15:00 was missing. A race that
shows up once in a while is still a race, so each test here holds the earlier
answer back on purpose and releases it after the current one - the order is
forced, and the test fails every time the page lets a late answer through.
"""

from __future__ import annotations

from playwright.sync_api import expect

from obj.barber.barbers import WEEK
from utils.local_time import at_local, local_day, parse_instant


class Held:
    """Requests matching `matches` are held back, unanswered, until release() -
    at most `limit` of them; the rest go through."""

    def __init__(self, page, matches, limit: int | None = None) -> None:
        self.page, self.matches, self.limit, self.routes = page, matches, limit, []
        page.route(matches, self.hold)

    def hold(self, route) -> None:
        if self.limit is not None and len(self.routes) >= self.limit:
            route.continue_()
            return
        self.routes.append(route)

    def release(self) -> None:
        assert self.routes, "nothing was held back, so this run did not create the race it is about"
        for route in self.routes:
            route.continue_()
        self.page.unroute(self.matches)


def test_the_times_for_an_earlier_choice_never_replace_the_times_for_the_day_chosen(
    signed_in, ui_barber, ui_haircut, shop_tz
):
    signed_in.barber_pill(ui_barber["id"]).click()
    signed_in.by("service").select_option(value=ui_haircut["id"])
    signed_in.settled()
    earlier, later = signed_in.chosen_day(), local_day(shop_tz, 7)
    signed_in.show_month_of(later)

    held = Held(signed_in.page, lambda url: "/availability" in url and f"date={earlier.isoformat()}" in url)
    signed_in.barber_pill(ui_barber["id"]).click()
    with signed_in.page.expect_response(lambda r: "/availability" in r.url and later.isoformat() in r.url):
        signed_in.day(later).click()
    held.release()
    signed_in.settled()

    days = {
        parse_instant(slot.get_attribute("data-start")).astimezone(shop_tz).date()
        for slot in signed_in.by("slot").all()
    }
    assert days == {later}, "every time on the screen belongs to the day in the date field"


def test_the_hours_of_the_barber_before_never_replace_the_hours_of_the_barber_chosen(owner_screen, barbers):
    sundays_only = barbers.create_fake_barber()
    barbers.set_hours(
        sundays_only["id"], {"hours": {day: ["10:00", "12:00"] if day == "sun" else None for day in WEEK}}
    )
    all_week = barbers.create_fake_barber()
    screen = owner_screen().select_barber(sundays_only["id"])

    held = Held(screen.page, lambda url: f"/barbers/{sundays_only['id']}/hours" in url)
    screen.barber_pill(sundays_only["id"]).click()
    with screen.page.expect_response(lambda r: f"/barbers/{all_week['id']}/hours" in r.url):
        screen.barber_pill(all_week["id"]).click()
    held.release()
    screen.settled()

    expect(screen.hours_row("mon").get_by_test_id("hours-works")).to_be_checked()
    expect(screen.hours_row("sun").get_by_test_id("hours-open")).to_have_value("00:00")

    screen.save_hours()
    assert (
        barbers.hours(all_week["id"]) == barbers.build_hours()["hours"]
    ), "saving wrote another barber's hours onto the barber whose name is on the screen"


def test_the_bookings_of_the_barber_before_never_replace_the_bookings_of_the_barber_chosen(
    owner_screen, barbers, bookings, new_customer, ui_haircut, shop_tz
):
    before, chosen = barbers.create_fake_barber(), barbers.create_fake_barber()
    customer, day = new_customer(), local_day(shop_tz, 5)
    bookings.create_booking(before["id"], ui_haircut["id"], at_local(shop_tz, day, "10:00"), persona=customer)
    bookings.create_booking(chosen["id"], ui_haircut["id"], at_local(shop_tz, day, "13:00"), persona=customer)
    screen = owner_screen().select_barber(before["id"])

    held = Held(screen.page, lambda url: "/bookings?" in url and f"barber_id={before['id']}" in url)
    screen.barber_pill(before["id"]).click()
    with screen.page.expect_response(
        lambda r: "/bookings?" in r.url and f"barber_id={chosen['id']}" in r.url
    ):
        screen.barber_pill(chosen["id"]).click()
    held.release()
    screen.settled()

    expect(screen.rows()).to_have_count(1)
    expect(screen.row_at("13:00")).to_be_visible()


def test_an_answer_for_the_person_who_signed_out_never_lands_in_the_page_they_left(
    shop, account, ui_barber, ui_haircut, shop_tz
):
    errors = []
    shop.page.on("pageerror", lambda error: errors.append(error))
    shop.sign_in_as(account)
    shop.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 8)).pick("10:00").book()
    expect(shop.rows()).to_have_count(1)

    shop.show_tab("book")
    held = Held(shop.page, lambda url: "/availability" in url or "/bookings?" in url)
    shop.barber_pill(ui_barber["id"]).click()
    shop.by("logout").click()
    held.release()
    shop.settled()

    expect(shop.by("slot")).to_have_count(0)
    expect(shop.by("booking-row")).to_have_count(0)
    assert errors == [], f"the page threw on an answer for someone no longer signed in: {errors}"


def test_a_popup_closed_before_the_list_is_drawn_still_sends_the_focus_to_the_new_booking(
    signed_in, ui_barber, ui_haircut, shop_tz
):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 9)).pick("14:00")

    held = Held(signed_in.page, lambda url: "/bookings?" in url, limit=1)
    signed_in.by("book").click()
    expect(signed_in.by("popup")).to_be_visible()
    signed_in.page.keyboard.press("Escape")
    expect(signed_in.by("popup")).to_be_hidden()
    held.release()
    signed_in.settled()

    expect(signed_in.row_at("14:00")).to_be_focused()
