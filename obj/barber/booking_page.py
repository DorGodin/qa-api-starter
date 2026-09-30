"""The barbershop's booking page, as a customer uses it.

Every action goes through what a person can see and press - labels, buttons,
the words on the screen - and waits for the page to answer, never for a fixed
number of milliseconds. A test built on this reads like the steps a person
would take.
"""

from __future__ import annotations

from datetime import date

from playwright.sync_api import Locator, Page, expect

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

    def sign_in(self, username: str, password: str) -> BookingPage:
        self.open()
        self.page.get_by_label(USERNAME, exact=True).first.fill(username)
        self.page.get_by_label(PASSWORD, exact=True).first.fill(password)
        self.by("login").click()
        expect(self.by("app")).to_be_visible()
        self.settled()
        return self

    def sign_up(self, name: str, username: str, password: str) -> BookingPage:
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
