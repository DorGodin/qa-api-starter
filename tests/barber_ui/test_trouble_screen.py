"""The trouble screen: no connection, no answer, or the server failing while a person books. It says which and
offers the shop's WhatsApp; when the connection comes back the very same booking is sent again - made once,
however many times it is sent."""

import re

from playwright.sync_api import expect

from utils.local_time import at_local, local_day


def ready_to_book(shop, account, barbers, ui_haircut, shop_tz):
    barber = barbers.create_fake_barber()
    screen = (
        shop.sign_in_as(account).choose(barber["id"], ui_haircut["id"], local_day(shop_tz, 6)).pick("10:00")
    )
    return screen, barber


def mine(bookings, account):
    return [b for b in bookings.listing(account["persona"])["content"] if b["status"] == "confirmed"]


def test_with_no_connection_the_screen_says_so_and_the_booking_goes_through_once_it_is_back(
    shop, account, barbers, bookings, ui_haircut, shop_tz
):
    screen, _ = ready_to_book(shop, account, barbers, ui_haircut, shop_tz)
    shop.page.context.set_offline(True)

    screen.by("book").click()

    trouble = screen.by("trouble")
    expect(trouble).to_be_visible()
    expect(trouble).to_have_attribute("data-kind", "offline")
    expect(screen.by("trouble-title")).to_have_text("אין חיבור כרגע")
    expect(screen.by("trouble-close")).to_be_focused()
    expect(screen.by("trouble-reach")).to_have_text("וואטסאפ למספרה")
    expect(screen.by("trouble-reach")).to_have_attribute("href", re.compile(r"^https://wa\.me/"))
    shop.page.context.set_offline(False)
    shop.page.evaluate("window.dispatchEvent(new Event('online'))")

    expect(screen.by("booking-done")).to_be_visible()
    expect(trouble).to_be_hidden()
    assert len(mine(bookings, account)) == 1


def test_when_the_server_fails_booking_again_makes_it_once(
    shop, account, barbers, bookings, ui_haircut, shop_tz
):
    screen, _ = ready_to_book(shop, account, barbers, ui_haircut, shop_tz)
    failures = {"left": 1}

    def fail_once(route):
        if route.request.method == "POST" and failures["left"]:
            failures["left"] -= 1
            route.fulfill(status=503, body="")
        else:
            route.continue_()

    shop.page.route("**/bookings", fail_once)
    screen.by("book").click()

    expect(screen.by("trouble")).to_have_attribute("data-kind", "server")
    expect(screen.by("trouble-title")).to_have_text("משהו השתבש אצלנו")
    screen.by("trouble-close").click()
    screen.close_popup()
    screen.pick("10:00").by("book").click()

    expect(screen.by("booking-done")).to_be_visible()
    assert len(mine(bookings, account)) == 1


def test_a_booking_whose_answer_was_lost_is_made_once_and_its_time_is_taken(
    shop, account, barbers, bookings, ui_haircut, shop_tz
):
    screen, _ = ready_to_book(shop, account, barbers, ui_haircut, shop_tz)
    lost = {"left": 1}

    def lose_the_answer(route):
        if route.request.method == "POST" and lost["left"]:
            lost["left"] -= 1
            route.fetch()
            route.abort()
        else:
            route.continue_()

    shop.page.route("**/bookings", lose_the_answer)
    screen.by("book").click()
    expect(screen.by("trouble")).to_have_attribute("data-kind", "offline")
    screen.by("trouble-close").click()
    screen.close_popup()

    assert len(mine(bookings, account)) == 1, "the booking reached the shop though its answer did not"
    expect(screen.by("slot").filter(has_text="10:00")).to_have_count(0)


def test_an_answer_that_never_comes_is_given_up_after_a_while(shop, account, barbers, ui_haircut, shop_tz):
    screen, _ = ready_to_book(shop, account, barbers, ui_haircut, shop_tz)
    shop.page.clock.install()
    shop.page.route(
        "**/bookings", lambda route: None if route.request.method == "POST" else route.continue_()
    )

    screen.by("book").click()
    shop.page.clock.run_for(16_000)

    expect(screen.by("trouble")).to_have_attribute("data-kind", "offline")


def test_closing_the_screen_leaves_the_booking_unmade_and_says_why(
    shop, account, barbers, bookings, ui_haircut, shop_tz
):
    screen, _ = ready_to_book(shop, account, barbers, ui_haircut, shop_tz)
    shop.page.context.set_offline(True)
    screen.by("book").click()
    expect(screen.by("trouble")).to_be_visible()

    screen.by("trouble-close").click()

    expect(screen.by("trouble")).to_be_hidden()
    expect(screen.by("popup")).to_contain_text("אין חיבור לאינטרנט")
    shop.page.context.set_offline(False)
    assert mine(bookings, account) == []


def test_offline_a_customer_still_sees_the_booking_they_have(
    shop, account, barbers, bookings, ui_haircut, shop_tz
):
    barber = barbers.create_fake_barber()
    made = bookings.create_booking(
        barber["id"],
        ui_haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 5), "12:00"),
        persona=account["persona"],
    )
    screen = shop.sign_in_as(account)
    shop.page.context.set_offline(True)

    screen.show_tab("book")
    screen.barber_pill(barber["id"]).click()

    expect(screen.by("trouble-booking")).to_be_visible()
    assert made["start_local"][11:16] in screen.text(screen.by("trouble-when"))
    shop.page.context.set_offline(False)

