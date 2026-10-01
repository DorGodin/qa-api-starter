"""The barbershop's booking page, as a customer uses it.

Every action goes through what a person can see and press - labels, buttons,
the words on the screen - and waits for the page to answer, never for a fixed
number of milliseconds. A test built on this reads like the steps a person
would take.
"""

from __future__ import annotations

from datetime import date

from playwright.sync_api import Locator, Page, expect

from obj.barber.customers import new_device_address

# The page is Hebrew. Its field labels, as a person reads them.
USERNAME, PASSWORD, YOUR_NAME = "שם משתמש", "סיסמה", "השם שלך"
BARBER, SERVICE, DATE = "ספר", "שירות", "תאריך"

# Unicode direction controls the page puts around names (isolates) and that
# Intl puts inside prices (marks), plus the no-break space: invisible, and in
# the way of a plain comparison. `plain()` removes them.
BIDI_CONTROLS = dict.fromkeys(
    map(ord, "\u2066\u2067\u2068\u2069\u200e\u200f\u202a\u202b\u202c\u202d\u202e"), None
)


def plain(text: str) -> str:
    return text.translate(BIDI_CONTROLS).replace("\u00a0", " ")


def a_device(browser, **context_args):
    """A browser context that is a different person's device: an address of its
    own, as the barbershop counts sign-ups and failed sign-ins by address."""
    return browser.new_context(**context_args, extra_http_headers={"X-Forwarded-For": new_device_address()})


class BookingPage:
    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

    def by(self, testid: str) -> Locator:
        return self.page.get_by_test_id(testid)

    def open(self) -> BookingPage:
        self.page.goto(self.base_url + "/")
        expect(self.by("login-form")).to_be_visible()
        return self

    def reload(self) -> BookingPage:
        """Refresh the page, as a person pulling it down on a phone does, and wait
        until it has settled - signed in again, or showing the sign-in form."""
        self.page.reload()
        self.settled()
        return self

    def sign_in(self, username: str, password: str, navigate: bool = True) -> BookingPage:
        """navigate=False signs in on the page as it is, the way the next person
        on a shared device does: a navigation would wipe what the last one left."""
        if navigate:
            self.open()
        self.page.get_by_label(USERNAME, exact=True).first.fill(username)
        self.page.get_by_label(PASSWORD, exact=True).first.fill(password)
        self.by("login").click()
        expect(
            self.page.locator('[data-testid="app"]:visible, [data-testid="login-error"]:visible').first
        ).to_be_visible()
        if self.by("login-error").is_visible():
            # Say why, not only that the screen never came: a refused sign-in
            # otherwise reads as a page that is slow to load.
            raise AssertionError(
                f"signing in as {username} was refused: {plain(self.by('login-error').inner_text())}"
            )
        self.settled()
        return self

    def sign_up(self, name: str, username: str, password: str, navigate: bool = True) -> BookingPage:
        if navigate:
            self.open()
        self.page.get_by_label(YOUR_NAME, exact=True).fill(name)
        self.by("signup-username").fill(username)
        self.by("signup-password").fill(password)
        self.by("signup").click()
        return self

    def choose(self, barber_id: str, service_id: str, day: date) -> BookingPage:
        """Pick barber, service and day, and wait until the times for exactly that
        choice are on screen."""
        with self.page.expect_response(lambda r: "/availability" in r.url and day.isoformat() in r.url):
            self.by("barber").select_option(value=barber_id)
            self.by("service").select_option(value=service_id)
            self.by("date").fill(day.isoformat())
            self.by("date").dispatch_event("change")
        self.settled()
        return self

    def choose_by_name(self, barber: str, service: str, day: date) -> BookingPage:
        """The same choice, made the way a customer makes it: by the names on the
        screen, not by ids taken from somewhere else."""
        barber_id = self.by("barber").locator("option", has_text=barber).get_attribute("value")
        service_id = self.by("service").locator("option", has_text=service).get_attribute("value")
        return self.choose(barber_id, service_id, day)

    def times(self) -> list[str]:
        return self.by("slot").all_inner_texts()

    def pick(self, hhmm: str) -> BookingPage:
        self.by("slot").filter(has_text=hhmm).first.click()
        expect(self.by("confirm")).to_be_visible()
        return self

    def book(self, keep_popup: bool = False) -> BookingPage:
        """Book, and read the popup that answers. The popup is modal - nothing
        behind it can be pressed - so unless asked to keep it, it is closed and
        what it said is kept in `last_popup`."""
        self.by("book").click()
        self.settled()
        popup = self.by("popup")
        expect(popup).to_be_visible()
        self.last_popup = {
            "title": plain(self.by("popup-title").inner_text()),
            "text": plain(self.by("popup-text").inner_text()),
            "kind": popup.get_attribute("data-kind"),
        }
        if not keep_popup:
            self.close_popup()
        return self

    def close_popup(self) -> BookingPage:
        self.by("popup-close").click()
        expect(self.by("popup")).to_be_hidden()
        return self

    def settled(self) -> None:
        """Wait until what is on screen is current: the page holds aria-busy
        until its last refresh has landed.

        Not wait_for_load_state("networkidle"): once a page has loaded, that
        returns at once - it waits for a load state, not for the network to go
        quiet again - so a test would read the list before it refreshed. It
        passed once by luck and failed the next run."""
        expect(self.by("app")).to_have_attribute("aria-busy", "false")

    def message(self) -> Locator:
        return self.by("message")

    def text(self, locator: Locator) -> str:
        """What the element says, without the invisible direction controls."""
        return plain(locator.inner_text())

    def rows(self) -> Locator:
        return self.by("booking-row")

    def row_at(self, hhmm: str) -> Locator:
        return self.rows().filter(has=self.page.get_by_test_id("booking-when").filter(has_text=hhmm))

    def cancel(self, hhmm: str) -> BookingPage:
        self.row_at(hhmm).get_by_test_id("cancel").click()
        self.settled()
        return self


class OwnerScreen(BookingPage):
    """The same page, signed in as the owner: hours, days off, barbers, services."""

    def select_barber(self, barber_id: str) -> OwnerScreen:
        self.by("barber").select_option(value=barber_id)
        self.settled()
        return self

    def hours_row(self, day: str) -> Locator:
        return self.page.locator(f'[data-testid="hours-row"][data-day="{day}"]')

    def set_day(self, day: str, opening: str | None = None, closing: str | None = None) -> OwnerScreen:
        """A day with times works those hours; a day without is a day off."""
        row = self.hours_row(day)
        works = row.get_by_test_id("hours-works")
        if opening is None:
            works.uncheck()
            return self
        works.check()
        row.get_by_test_id("hours-open").fill(opening)
        row.get_by_test_id("hours-close").fill(closing)
        return self

    def save_hours(self) -> OwnerScreen:
        self.by("save-hours").click()
        self.settled()
        return self

    def add_day_off(self, day: date) -> OwnerScreen:
        self.by("dayoff-date").fill(day.isoformat())
        self.by("add-dayoff").click()
        self.settled()
        return self

    def days_off(self) -> list[str]:
        return [row.get_attribute("data-day") for row in self.by("dayoff-row").all()]

    def remove_day_off(self, day: date) -> OwnerScreen:
        self.page.locator(f'[data-testid="dayoff-row"][data-day="{day.isoformat()}"]').get_by_test_id(
            "remove-dayoff"
        ).click()
        self.settled()
        return self

    def add_barber(self, name: str, username: str, password: str) -> OwnerScreen:
        self.by("new-barber-name").fill(name)
        self.by("new-barber-username").fill(username)
        self.by("new-barber-password").fill(password)
        self.by("add-barber").click()
        self.settled()
        return self

    def add_service(self, name: str, minutes: int, price: str) -> OwnerScreen:
        self.by("new-service-name").fill(name)
        self.by("new-service-duration").select_option(value=str(minutes))
        self.by("new-service-price").fill(price)
        self.by("add-service").click()
        self.settled()
        return self

    def service_row(self, service_id: str) -> Locator:
        return self.page.locator(f'[data-testid="service-row"][data-id="{service_id}"]')

    def save_service(
        self, service_id: str, price: str | None = None, offered: bool | None = None
    ) -> OwnerScreen:
        row = self.service_row(service_id)
        if price is not None:
            row.get_by_test_id("service-price").fill(price)
        if offered is not None:
            row.get_by_test_id("service-active").set_checked(offered)
        row.get_by_test_id("save-service").click()
        self.settled()
        return self
