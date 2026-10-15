"""How the page feels: its own letters, a list drawn in grey while it is slow to arrive, and
motion - all of it extra. A person who asked their device for less motion gets none of it, and
nothing ever waits for an animation.

The other page tests run without motion (obj.barber.booking_page.a_device); these ask for it."""

from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect

from obj.barber.booking_page import BookingPage, a_device
from utils.local_time import at_local, local_day

PHONE = {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True, "locale": "he-IL"}


@pytest.fixture
def moving(browser, env_config):
    """A phone whose owner has not asked for less motion."""
    context = a_device(browser, **PHONE, reduced_motion="no-preference")
    yield BookingPage(context.new_page(), env_config["url"])
    context.close()


def hold(page, pattern):
    """Keep a request from being answered until the test lets it go. Not a delay: a handler that
    sleeps also stops the test from looking, and the look then races the answer."""
    held = []

    def keep(route):
        held.append(route)

    page.route(pattern, keep)

    def let_go():
        waiting, held[:] = list(held), []
        for route in waiting:
            route.continue_()
        page.unroute(pattern, keep)

    return let_go


def animation_of(locator) -> str:
    return locator.evaluate("e => getComputedStyle(e).animationName")


def test_the_letters_are_rubik_and_come_from_the_shop_itself(shop, account, env_config):
    asked = []
    shop.page.on("request", lambda r: asked.append(r.url))

    shop.sign_in_as(account)

    shop.page.wait_for_function("() => [...document.fonts].some((f) => f.status === 'loaded')")
    assert shop.page.evaluate("getComputedStyle(document.body).fontFamily").startswith(("Rubik", '"Rubik"'))
    assert shop.by("book").evaluate("e => getComputedStyle(e).fontFamily").startswith(("Rubik", '"Rubik"'))
    assert shop.by("service-button").evaluate("e => getComputedStyle(e).fontFamily").startswith(("Rubik", '"Rubik"'))
    fonts = [url for url in asked if "/fonts/" in url]
    assert fonts, "the page asked for no font file"
    home = urlparse(env_config["url"]).netloc
    assert {urlparse(url).netloc for url in asked} == {home}, "the page asks no other site for anything"


def test_times_that_are_slow_to_arrive_are_drawn_in_grey_and_gone_when_they_land(
    shop, account, ui_barber, ui_haircut, shop_tz
):
    signed_in = shop.sign_in_as(account)
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 5))
    expect(signed_in.by("slot").first).to_be_visible()
    let_go = hold(shop.page, "**/barbers/*/availability*")

    signed_in.day(local_day(shop_tz, 6)).click(no_wait_after=True)

    grey = shop.page.locator(".skeleton")
    expect(grey).to_be_visible()
    expect(grey).to_have_attribute("aria-hidden", "true")
    expect(signed_in.by("slots")).to_be_hidden()
    assert grey.locator(".bone").count() >= 5
    expect(signed_in.by("app")).to_have_attribute("aria-busy", "true")
    # The page says it is settled only once the grey is gone and the real list is back.
    let_go()
    signed_in.settled()
    assert grey.count() == 0
    assert signed_in.by("slots").is_visible() and signed_in.by("slot").count() > 0


@pytest.mark.parametrize(
    ("asks", "list_id"),
    [("**/bookings?*", "bookings"), ("**/courses", "courses"), ("**/products", "products")],
)
def test_each_list_has_its_grey_shape_while_it_is_slow(
    browser, env_config, account, bookings, barbers, courses, products, ui_haircut, shop_tz, asks, list_id
):
    """On a wide screen every list is in view - a screen of its own, whatever --device the run is on.
    The page is opened again with one of them held back."""
    courses.create_fake_course()
    products.create_fake_product()
    barber = barbers.create_fake_barber()
    start = at_local(shop_tz, local_day(shop_tz, 6), "11:00")
    bookings.create_booking(barber["id"], ui_haircut["id"], start, persona=account["persona"])
    wide = a_device(browser, viewport={"width": 1100, "height": 760}, locale="he-IL")
    shop = BookingPage(wide.new_page(), env_config["url"])
    signed_in = shop.sign_in_as(account)
    let_go = hold(shop.page, asks)

    shop.page.reload()

    grey = shop.page.locator(f'[data-testid="{list_id}"] + .skeleton')
    expect(grey).to_be_visible()
    expect(signed_in.by(list_id)).to_be_hidden()
    assert shop.page.locator(".skeleton").count() == 1, "only the list that is late"
    let_go()
    signed_in.settled()
    assert shop.page.locator(".skeleton").count() == 0 and signed_in.by(list_id).is_visible()
    wide.close()


def test_a_slow_list_on_another_tab_draws_nothing(browser, env_config, account):
    """On a phone the courses are a tab of their own: their shape is not drawn behind the one in view."""
    context = a_device(browser, **PHONE)
    phone = BookingPage(context.new_page(), env_config["url"]).sign_in_as(account)
    let_go = hold(phone.page, "**/courses")

    phone.page.reload()
    expect(phone.by("app")).to_have_attribute("aria-busy", "true")
    phone.page.wait_for_timeout(500)

    assert phone.page.locator('[data-testid="courses"] + .skeleton').count() == 0
    let_go()
    phone.settled()
    assert phone.page.locator(".skeleton").count() == 0
    context.close()


def test_with_motion_the_times_come_in_and_a_booking_is_marked_with_confetti(
    moving, account, ui_barber, ui_haircut, shop_tz
):
    phone = moving.sign_in_as(account)
    phone.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 5))

    assert animation_of(phone.by("slot").first) == "rise"
    phone.pick("12:00").book(keep_answer=True)

    ring = phone.by("booking-done").locator(".ring")
    assert animation_of(ring) == "ring-in"
    assert animation_of(ring.locator(".tick")) == "drawn"
    expect(ring.locator(".bit")).to_have_count(26)
    assert phone.text(ring.locator(".tick")) == "✓", "the tick is still a tick underneath"
    expect(ring.locator(".bit")).to_have_count(0, timeout=4000)


def test_a_request_that_waits_for_the_barber_is_not_celebrated(moving, account, barbers, services, shop_tz):
    barber = barbers.create_fake_barber()
    asks_first = services.create_fake_service(requires_approval=True)
    phone = moving.sign_in_as(account)
    phone.choose(barber["id"], asks_first["id"], local_day(shop_tz, 5)).pick("12:00").book(keep_answer=True)

    # Counted at once, not waited for: confetti that was thrown clears itself away within two seconds,
    # and a check that waits would find none by then.
    assert phone.by("booking-done").locator(".bit").count() == 0
    expect(phone.by("booking-done")).to_have_attribute("data-waiting", "")


def test_a_person_who_asked_for_less_motion_gets_none(shop, account, ui_barber, ui_haircut, shop_tz):
    signed_in = shop.sign_in_as(account)
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 5))

    assert animation_of(signed_in.by("slot").first) == "none"
    signed_in.pick("13:00").book(keep_answer=True)

    ring = signed_in.by("booking-done").locator(".ring")
    assert ring.locator(".bit").count() == 0, "counted at once: thrown confetti clears itself away"
    assert animation_of(ring) == "none" and animation_of(ring.locator(".tick")) == "none"
    assert signed_in.text(ring.locator(".tick")) == "✓"
