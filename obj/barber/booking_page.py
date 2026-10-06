"""The barbershop's booking page, as a customer uses it.

Every action goes through what a person can see and press - labels, buttons,
the words on the screen - and waits for the page to answer, never for a fixed
number of milliseconds. A test built on this reads like the steps a person
would take.
"""

from __future__ import annotations

import re
from datetime import date

from playwright.sync_api import Locator, Page, expect

from obj.barber.customers import new_device_address

# The page is Hebrew. Its field labels, as a person reads them.
USERNAME, PASSWORD = "שם משתמש", "סיסמה"
BARBER, SERVICE, DATE = "ספר", "שירות", "תאריך"

# Unicode direction controls the page puts around names (isolates) and that
# Intl puts inside prices (marks), plus the no-break space: invisible, and in
# the way of a plain comparison. `plain()` removes them.
BIDI_CONTROLS = dict.fromkeys(
    map(ord, "\u2066\u2067\u2068\u2069\u200e\u200f\u202a\u202b\u202c\u202d\u202e"), None
)


def plain(text: str) -> str:
    return text.translate(BIDI_CONTROLS).replace("\u00a0", " ")


def greeting(display_name: str) -> re.Pattern:
    """How the page greets a customer: by first name, with the name isolated."""
    first = display_name.split()[0]
    return re.compile(rf"^שלום [\u2066-\u2069]*{re.escape(first)}[\u2066-\u2069]*$")


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
        """The signed-out screen, as anyone arriving sees it: the code sign-in."""
        self.page.goto(self.base_url + "/")
        expect(self.by("code-request-form")).to_be_visible()
        return self

    def unfold_password_sign_in(self) -> BookingPage:
        """The page signs in by SMS code now; the username and password form is
        folded away under it until every account has a phone. Until these suites
        sign in by code too, they unfold it."""
        fold = self.by("password-sign-in")
        if fold.count() and fold.get_attribute("open") is None:
            fold.locator("summary").click()
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
        self.unfold_password_sign_in()
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

    def sign_in_as(self, account: dict) -> BookingPage:
        """Open the page already signed in as an account made through the API:
        the page's own remembered sign-in, as when a customer comes back. The
        code sign-in itself is driven by sign_in_by_code, in its own tests."""
        self.page.goto(self.base_url + "/")
        self.page.evaluate("token => sessionStorage.setItem('barber.session', token)", account["token"])
        return self.reload()

    def sign_in_by_code(self, name: str, phone: str, inbox, navigate: bool = True) -> BookingPage:
        """Sign in as a person does: name and phone, then the code from the SMS.
        A code asked for too soon after the last one is refused with how long
        to wait - the product's rule, honoured here rather than loosened for tests."""
        if navigate:
            self.page.goto(self.base_url + "/")
        seen = inbox.last_id(phone)
        self.by("full-name").fill(name)
        self.by("phone").fill(phone)
        for _ in range(2):
            self.by("send-code").click()
            expect(
                self.page.locator(
                    '[data-testid="code-form"]:visible, [data-testid="code-request-error"]:visible'
                ).first
            ).to_be_visible()
            if self.by("code-form").is_visible():
                break
            wait = re.search(r"בעוד (\d+) שניות", self.text(self.by("code-request-error")))
            if wait is None:
                raise AssertionError(f"no code was sent: {self.text(self.by('code-request-error'))}")
            self.page.wait_for_timeout((int(wait.group(1)) + 1) * 1000)
        self.by("code").fill(inbox.code_for(phone, after=seen))
        expect(
            self.page.locator('[data-testid="app"]:visible, [data-testid="code-error"]:visible').first
        ).to_be_visible()
        if self.by("code-error").is_visible():
            raise AssertionError(f"the code was refused: {self.text(self.by('code-error'))}")
        self.settled()
        return self

    def session_token(self) -> str:
        """The sign-in this page holds - for checking through the API what it did."""
        return self.page.evaluate("() => sessionStorage.getItem('barber.session')")

    def show_tab(self, tab: str) -> None:
        """On a customer's phone, booking and the bookings are two tabs at the
        foot of the screen - `book` and `mine` - and a person taps the one they
        need. Elsewhere both are on the screen, and this does nothing."""
        button = self.by(f"tab-{tab}")
        # Behind an open popup nothing can be pressed - a person closes it first.
        if self.by("popup").is_visible():
            return
        # The card that answered a booking stands where the form was: to book
        # again a person presses its `קביעת תור נוסף`.
        if tab == "book" and self.by("booking-done").is_visible():
            self.book_another()
            return
        # The page may still be moving the focus to the tab it chose itself -
        # to the new booking, say, once a popup closed with its button or with
        # Escape. A person waits for the screen to settle.
        if self.by("app").is_visible():
            self.page.wait_for_function("() => document.activeElement?.dataset.testid !== 'popup-close'")
            self.settled()
        if button.is_visible() and button.get_attribute("aria-current") != "page":
            button.click()

    def choose(self, barber_id: str, service_id: str, day: date) -> BookingPage:
        """Pick barber, service and day, and wait until the times for exactly that
        choice are on screen."""
        self.show_tab("book")
        self.barber_pill(barber_id).click()
        self.by("service").select_option(value=service_id)
        self.settled()
        return self.choose_day(day)

    def barber_pill(self, barber_id: str) -> Locator:
        return self.by("barbers").locator(f'[data-id="{barber_id}"]')

    def chosen_barber(self) -> Locator:
        return self.by("barbers").locator('[aria-checked="true"]')

    def choose_barber(self, barber_id: str) -> BookingPage:
        self.barber_pill(barber_id).click()
        self.settled()
        return self

    def day(self, day: date) -> Locator:
        """That day in the calendar - once its month is the one shown."""
        return self.by("days").locator(f'td[data-date="{day.isoformat()}"]')

    def show_month_of(self, day: date) -> BookingPage:
        """Turn the calendar to the month of that day, a month at a time, as a
        person does."""
        for _ in range(4):
            shown = self.by("days").locator("td[data-date]").first.get_attribute("data-date")[:7]
            wanted = day.isoformat()[:7]
            if shown == wanted:
                return self
            self.by("next-month" if wanted > shown else "prev-month").click()
            self.settled()
        raise AssertionError(f"the calendar never reached {day:%Y-%m}")

    def choose_day(self, day: date) -> BookingPage:
        """Press that day in the calendar and wait for its times. A day with no
        time to offer cannot be pressed: the times shown stay those of the day
        already chosen, refreshed."""
        self.show_month_of(day)
        cell = self.day(day)
        if cell.get_attribute("aria-disabled") == "true":
            return self
        with self.page.expect_response(lambda r: "/availability" in r.url and day.isoformat() in r.url):
            cell.click()
        self.settled()
        return self

    def chosen_day(self) -> date:
        return date.fromisoformat(self.by("date").input_value())

    def choose_by_name(self, barber: str, service: str, day: date) -> BookingPage:
        """The same choice, made the way a customer makes it: by the names on the
        screen, not by ids taken from somewhere else."""
        self.show_tab("book")
        barber_id = self.by("barbers").get_by_role("radio", name=barber, exact=True).get_attribute("data-id")
        service_id = self.by("service").locator("option", has_text=service).get_attribute("value")
        return self.choose(barber_id, service_id, day)

    def times(self) -> list[str]:
        self.show_tab("book")
        return self.by("slot").all_inner_texts()

    def pick(self, hhmm: str) -> BookingPage:
        self.show_tab("book")
        self.by("slot").filter(has_text=hhmm).first.click()
        expect(self.by("confirm")).to_be_visible()
        return self

    def book(self, keep_answer: bool = False) -> BookingPage:
        """Book, and read what answers: a card in the panel when a customer's
        booking or move went through, a modal popup for a refusal and for the
        owner's booking for a caller. Unless asked to keep it, the answer is
        left - the popup closed, the card's `התורים שלי` pressed - and what it
        said is kept in `last_answer`."""
        self.by("book").click()
        self.settled()
        answer = self.page.locator(
            '[data-testid="booking-done"]:visible, [data-testid="popup"]:visible'
        ).first
        expect(answer).to_be_visible()
        if self.by("popup").is_visible():
            self.last_answer = {
                "title": plain(self.by("popup-title").inner_text()),
                "text": plain(self.by("popup-text").inner_text()),
                "kind": self.by("popup").get_attribute("data-kind"),
            }
            if not keep_answer:
                self.close_popup()
        else:
            self.last_answer = {
                "title": plain(self.by("booking-done-title").inner_text()),
                "text": plain(self.by("booking-done-when").inner_text())
                + " · "
                + plain(self.by("booking-done-what").inner_text()),
                "kind": "ok",
            }
            if not keep_answer:
                self.go_to_my_bookings()
        return self

    def go_to_my_bookings(self) -> BookingPage:
        self.by("booking-done-mine").click()
        self.settled()
        return self

    def book_another(self) -> BookingPage:
        self.by("booking-done-more").click()
        expect(self.by("booking-done")).to_be_hidden()
        return self

    def close_popup(self) -> BookingPage:
        self.by("popup-close").click()
        expect(self.by("popup")).to_be_hidden()
        # The browser fires the dialog's close event a task later, and the page
        # answers it - the focus to the new booking, and its tab. Until then a
        # test faster than any person could press something the page then undoes.
        self.page.wait_for_function("() => document.activeElement?.dataset.testid !== 'popup-close'")
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
        self.show_tab("mine")
        return self.by("booking-row")

    def row_at(self, hhmm: str) -> Locator:
        return self.rows().filter(has=self.page.get_by_test_id("booking-when").filter(has_text=hhmm))

    def book_for(self, name: str, keep_answer: bool = False) -> BookingPage:
        """The owner's booking: the guest's name, then the same book button."""
        self.by("guest-name").fill(name)
        return self.book(keep_answer=keep_answer)

    def start_moving(self, hhmm: str) -> BookingPage:
        """Press "שינוי מועד" on the booking at that time: the panel then offers the
        times it can move to, with its barber and service fixed."""
        self.row_at(hhmm).get_by_test_id("move").click()
        self.settled()
        expect(self.by("moving")).to_be_visible()
        return self

    def stop_moving(self) -> BookingPage:
        self.by("stop-moving").click()
        self.settled()
        expect(self.by("moving")).to_be_hidden()
        return self

    def course_card(self, title: str) -> Locator:
        self.show_tab("courses")
        return self.by("course").filter(has=self.page.get_by_test_id("course-title").filter(has_text=title))

    def answer(self, hhmm: str, verb: str) -> BookingPage:
        self.row_at(hhmm).get_by_test_id(verb).click()
        self.settled()
        return self

    def cancel(self, hhmm: str) -> BookingPage:
        self.row_at(hhmm).get_by_test_id("cancel").click()
        self.settled()
        return self


class OwnerScreen(BookingPage):
    """The same page, signed in as the owner: hours, days off, barbers, services."""

    def select_barber(self, barber_id: str) -> OwnerScreen:
        self.choose_barber(barber_id)
        return self

    def toggle_barber_active(self) -> OwnerScreen:
        """Take the selected barber out of the shop, or bring them back."""
        self.by("barber-active-toggle").click()
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

    def approval_row(self, day: str) -> Locator:
        return self.page.locator(f'[data-testid="approval-row"][data-day="{day}"]')

    def set_approval_day(self, day: str, start: str | None = None, until: str | None = None) -> OwnerScreen:
        """A day with times asks for the barber's yes in those hours; a day without never does."""
        row = self.approval_row(day)
        asks = row.get_by_test_id("approval-asks")
        if start is None:
            asks.uncheck()
            return self
        asks.check()
        row.get_by_test_id("approval-from").fill(start)
        row.get_by_test_id("approval-until").fill(until)
        return self

    def save_approval(self) -> OwnerScreen:
        self.by("save-approval").click()
        self.settled()
        return self

    def course_editor(self, course_id: str) -> Locator:
        return self.page.locator(f'[data-testid="course-edit"][data-id="{course_id}"]')

    def add_course(self, title: str, subtitle: str = "", starts_on: str = "", price: str = "") -> OwnerScreen:
        self.by("new-course-title").fill(title)
        self.by("new-course-subtitle").fill(subtitle)
        self.by("new-course-date").fill(starts_on)
        self.by("new-course-price").fill(price)
        self.by("add-course").click()
        self.settled()
        return self

    def save_course(self, course_id: str) -> OwnerScreen:
        self.course_editor(course_id).get_by_test_id("save-course").click()
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
