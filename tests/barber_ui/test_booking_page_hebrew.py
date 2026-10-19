"""A Hebrew page is not an English page with the words swapped. It reads right
to left, it carries Latin names and numbers inside Hebrew sentences, and it must
never let the server's English through to the customer."""

import re

from playwright.sync_api import expect

from utils.local_time import at_local, local_day

LATIN = re.compile(r"[A-Za-z]")
# How he-IL writes a short weekday: "יום א׳" to "יום ו׳" - and Saturday is
# "שבת" alone, with no "יום". A test that expected "יום" failed every Saturday.
HEBREW_WEEKDAY = re.compile(r"^(יום [א-ו]׳|שבת)")
HEBREW = re.compile(r"[\u0590-\u05FF]")
FSI, PDI = "\u2068", "\u2069"
# Up to this width the page stacks its two columns (its @media max-width: 760px).
PHONE_WIDTH = 760


def test_the_page_is_hebrew_and_its_layout_is_mirrored(signed_in):
    html = signed_in.page.locator("html")
    expect(html).to_have_attribute("lang", "he")
    expect(html).to_have_attribute("dir", "rtl")

    if signed_in.page.viewport_size["width"] > PHONE_WIDTH:
        booking = signed_in.by("left-panel").bounding_box()
        bookings = signed_in.by("right-panel").bounding_box()
        assert booking["x"] > bookings["x"], "booking comes first, and in Hebrew first is on the right"
    else:
        # On a phone they are two tabs at the foot of the screen, and in Hebrew
        # the first, booking, is on the right.
        book, mine = signed_in.by("tab-book").bounding_box(), signed_in.by("tab-mine").bounding_box()
        assert book["x"] > mine["x"], "the booking tab comes first, on the right"


def test_times_keep_their_own_order_inside_the_right_to_left_page(signed_in, ui_barber, ui_haircut, shop_tz):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 3))
    first, second = signed_in.by("slot").nth(0), signed_in.by("slot").nth(1)

    assert (
        first.evaluate("e => getComputedStyle(e).direction") == "ltr"
    ), "a time is read left to right, always"
    assert re.fullmatch(r"\d\d:\d\d", first.inner_text())
    assert first.bounding_box()["x"] > second.bounding_box()["x"], "the grid itself flows right to left"


def test_a_latin_name_inside_a_hebrew_sentence_is_isolated(shop, account, barbers, ui_haircut, shop_tz):
    latin = barbers.create_fake_barber()
    shop.sign_in_as(account)
    shop.choose(latin["id"], ui_haircut["id"], local_day(shop_tz, 3)).pick("10:00")

    confirm = shop.by("confirm-text").inner_text()

    # Without isolation, the bidi algorithm lets a Latin name pull the dot or
    # dash beside it to the wrong side of the sentence.
    assert f"{FSI}{latin['display_name']}{PDI}" in confirm, confirm
    assert "אצל" in confirm


def test_prices_are_written_the_israeli_way(signed_in, ui_barber, ui_haircut, shop_tz):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 6)).pick("14:00").book()

    row = signed_in.text(signed_in.row_at("14:00"))

    assert re.search(r"80\.00\s*₪", row), f"the amount, then the sign: {row}"
    assert "₪80" not in row


def test_dates_are_written_in_hebrew(signed_in, ui_barber, ui_haircut, shop_tz):
    signed_in.choose(ui_barber["id"], ui_haircut["id"], local_day(shop_tz, 7)).pick("15:00").book()

    when = signed_in.text(signed_in.row_at("15:00").get_by_test_id("booking-when"))

    assert HEBREW_WEEKDAY.match(when), when
    assert not LATIN.search(when), f"a Latin month or weekday slipped in: {when}"


def test_no_english_from_the_server_ever_reaches_the_customer(
    shop, account, customers, bookings, barbers, credentials, ui_haircut, shop_tz, fresh_address
):
    said = {}
    shop.page.set_extra_http_headers({"X-Forwarded-For": fresh_address()})

    contested = barbers.create_fake_barber()
    shop.sign_in_as(account)
    day = local_day(shop_tz, 4)
    shop.choose(contested["id"], ui_haircut["id"], day).pick("11:00")
    rival = customers.sign_up_as_persona()
    bookings.create_booking(contested["id"], ui_haircut["id"], at_local(shop_tz, day, "11:00"), persona=rival)
    shop.book()
    said["slot taken"] = shop.last_answer["text"]

    for situation, text in said.items():
        assert HEBREW.search(text), f"{situation}: nothing was said in Hebrew: {text!r}"
        assert not LATIN.search(text), f"{situation}: English reached the customer: {text!r}"


def test_the_service_choice_drops_the_agorot_of_a_whole_price_and_keeps_real_ones(signed_in, services):
    whole = services.create_fake_service(price_minor=14000)
    odd = services.create_fake_service(price_minor=9250)
    signed_in.reload()

    def words(service):
        return signed_in.text(signed_in.service_list().locator(f'[data-value="{service["id"]}"]'))

    assert re.search(r"· 140\s*₪$", words(whole)), words(whole)
    assert re.search(r"· 92\.50\s*₪$", words(odd)), words(odd)


def test_the_service_list_opens_below_its_field_with_each_service_on_one_line(signed_in, services):
    """An iPhone opens its own list upward when the field is low, and folds a long line in two: the page's
    own list opens under the field, and every service is its name, its minutes and its price."""
    long = services.create_fake_service(duration_minutes=45)
    signed_in.reload()

    listed = signed_in.service_list()
    assert listed.bounding_box()["y"] >= signed_in.by("service-button").bounding_box()["y"]
    item = listed.locator(f'[data-value="{long["id"]}"]')
    expect(item).to_contain_text(long["name"])
    expect(item.locator("small")).to_have_text(re.compile(r"^45 דק׳ · "))
    assert item.locator("small").evaluate(
        "e => e.getBoundingClientRect().height < 2 * parseFloat(getComputedStyle(e).fontSize)"
    ), "the minutes and price fold"


def test_the_chosen_service_says_how_long_it_takes_beside_its_name(signed_in, services):
    short = services.create_fake_service(duration_minutes=15)
    long = services.create_fake_service(duration_minutes=45)
    signed_in.reload()

    signed_in.choose_service(short["id"])
    expect(signed_in.by("service-meta")).to_have_text(re.compile(r"^15 דק׳ · "))
    signed_in.choose_service(long["id"])
    expect(signed_in.by("service-meta")).to_have_text(re.compile(r"^45 דק׳ · "))
    expect(signed_in.by("service-name")).to_contain_text(long["name"])


def test_the_service_list_is_used_from_the_keyboard(signed_in, services):
    services.create_fake_service()
    signed_in.reload()
    button, listed = signed_in.by("service-button"), signed_in.by("service-list")

    button.focus()
    signed_in.page.keyboard.press("ArrowDown")
    expect(listed).to_be_visible()
    expect(button).to_have_attribute("aria-expanded", "true")
    expect(listed.locator('[aria-selected="true"]')).to_be_focused()

    signed_in.page.keyboard.press("Escape")
    expect(listed).to_be_hidden()
    expect(button).to_be_focused()

    signed_in.page.keyboard.press("Enter")
    signed_in.page.keyboard.press("End")
    last = listed.locator("li").last
    expect(last).to_be_focused()
    chosen = last.get_attribute("data-value")
    signed_in.page.keyboard.press("Enter")
    expect(listed).to_be_hidden()
    expect(button).to_be_focused()
    expect(signed_in.by("service")).to_have_value(chosen)
