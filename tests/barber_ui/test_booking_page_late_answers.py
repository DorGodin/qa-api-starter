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
from utils.local_time import at_local, local_day, local_today, parse_instant


class Held:
    """Requests matching `matches` are held back, unanswered, until release()."""

    def __init__(self, page, matches) -> None:
        self.page, self.matches, self.routes = page, matches, []
        page.route(matches, self.hold)

    def hold(self, route) -> None:
        self.routes.append(route)

    def release(self) -> None:
        assert self.routes, "nothing was held back, so this run did not create the race it is about"
        for route in self.routes:
            route.continue_()
        self.page.unroute(self.matches)


def test_the_times_for_an_earlier_choice_never_replace_the_times_for_the_day_chosen(
    signed_in, ui_barber, ui_haircut, shop_tz
):
    today, later = local_today(shop_tz), local_day(shop_tz, 7)
    signed_in.by("barber").select_option(value=ui_barber["id"])
    signed_in.by("service").select_option(value=ui_haircut["id"])
    signed_in.settled()

    held = Held(signed_in.page, lambda url: "/availability" in url and f"date={today.isoformat()}" in url)
    signed_in.by("barber").dispatch_event("change")
    with signed_in.page.expect_response(lambda r: "/availability" in r.url and later.isoformat() in r.url):
        signed_in.by("date").fill(later.isoformat())
        signed_in.by("date").dispatch_event("change")
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
    screen.by("barber").dispatch_event("change")
    with screen.page.expect_response(lambda r: f"/barbers/{all_week['id']}/hours" in r.url):
        screen.by("barber").select_option(value=all_week["id"])
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
    screen.by("barber").dispatch_event("change")
    with screen.page.expect_response(
        lambda r: "/bookings?" in r.url and f"barber_id={chosen['id']}" in r.url
    ):
        screen.by("barber").select_option(value=chosen["id"])
    held.release()
    screen.settled()

    expect(screen.rows()).to_have_count(1)
    expect(screen.row_at("13:00")).to_be_visible()
