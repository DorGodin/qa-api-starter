"""More journeys: each thing the shop offers beyond a plain booking, start to finish, through the
page alone - a request the barber answers, a booking for two, the shelf, a move, a course, an
emergency haircut.

As in test_journeys.py nothing is prepared: the owner opens the barber and types the service, the
product or the course on their screen, customers open their accounts on theirs, and the API is used
only at the end, to check that what the screens showed is what was stored."""

from __future__ import annotations

from datetime import timedelta

from playwright.sync_api import expect

from obj.barber.booking_page import BookingPage, OwnerScreen
from obj.barber.courses import PNG_1X1
from tests.barber_ui.test_journeys import WEEKDAYS, add_a_service, new_account, open_a_barber, quarter_hours
from utils.local_time import at_local, local_day, parse_instant


def as_persona(customers, screen: BookingPage, name: str) -> str:
    """The API through the sign-in this screen holds - for the checks at the end."""
    customers.client.register_persona_headers(name, {"Authorization": f"Bearer {screen.session_token()}"})
    return name


def withdraw(owner: OwnerScreen, service_id: str) -> None:
    """A service that waits for the barber's yes is taken off the menu when its journey ends: the
    shop is shared, and left on offer it was the first service other tests met."""
    owner.reload()
    owner.save_service(service_id, offered=False)
    expect(owner.message()).to_have_attribute("data-kind", "ok")


def told(screen: BookingPage) -> dict:
    """Open the page again as a customer coming back does, and read what it tells them."""
    screen.reload()
    expect(screen.by("popup")).to_be_visible()
    said = {"title": screen.text(screen.by("popup-title")), "text": screen.text(screen.by("popup-text"))}
    screen.close_popup()
    return said


def editor_named(owner: OwnerScreen, kind: str, field: str, name: str) -> str:
    """The id of the course or product the owner just typed: its form is found by the name in it."""
    return owner.page.evaluate(
        """([kind, field, name]) => [...document.querySelectorAll(`[data-testid="${kind}-edit"]`)]
            .find((box) => box.querySelector(`[data-testid="${kind}-edit-${field}"]`).value === name).dataset.id""",
        [kind, field, name],
    )


def test_a_request_waits_for_the_barber_and_their_yes_and_no_reach_each_customer(
    person, run_id, credentials, customers, bookings, shop_tz, signed_up, diary_of
):
    day = local_day(shop_tz, 7)
    owner = person(OwnerScreen).sign_in(*credentials("owner"))
    barber = open_a_barber(owner, run_id, WEEKDAYS[day.weekday()], "09:00", "12:00")
    service = f"QA ask first {run_id}"
    service_id = add_a_service(owner, service, 30, "200", needs_barber=True)

    asks = signed_up(person(), new_account(run_id, "asks"))
    asks.choose_by_name(barber["name"], service, day).pick("10:00").book(keep_answer=True)
    expect(asks.by("booking-done")).to_have_attribute("data-waiting", "")
    asks.go_to_my_bookings()
    expect(asks.row_at("10:00")).to_have_attribute("data-approval", "pending")

    also = signed_up(person(), new_account(run_id, "also"))
    also.choose_by_name(barber["name"], service, day)
    assert "10:00" not in also.times(), "a request holds its time while it waits"
    also.pick("11:00").book()
    expect(also.row_at("11:00")).to_have_attribute("data-approval", "pending")

    diary = diary_of(barber)
    diary.answer("10:00", "approve")
    diary.answer("11:00", "decline")
    expect(diary.row_at("10:00")).to_have_attribute("data-approval", "approved")

    yes = told(asks)
    assert "אישר" in yes["title"] and "10:00" in yes["text"], yes
    expect(asks.row_at("10:00")).to_have_attribute("data-approval", "approved")
    told(also)
    expect(also.page.locator('[data-testid="booking-row"][data-status="confirmed"]')).to_have_count(0)

    third = signed_up(person(), new_account(run_id, "third"))
    third.choose_by_name(barber["name"], service, day)
    assert "11:00" in third.times() and "10:00" not in third.times(), "a no frees the time, a yes keeps it"

    stored = {
        parse_instant(b["start"]): b for b in bookings.listing("owner", barber_id=barber["id"])["content"]
    }
    yes_at, no_at = at_local(shop_tz, day, "10:00"), at_local(shop_tz, day, "11:00")
    assert (stored[yes_at]["status"], stored[yes_at]["approval"]) == ("confirmed", "approved")
    assert (stored[no_at]["status"], stored[no_at]["approval"]) == ("cancelled", "declined")
    withdraw(owner, service_id)


def test_a_booking_for_two_is_one_step_counts_once_and_each_is_then_its_own(
    person, run_id, credentials, customers, bookings, shop_tz, signed_up, diary_of, bookings_ahead_limit
):
    day = local_day(shop_tz, 7)
    owner = person(OwnerScreen).sign_in(*credentials("owner"))
    barber = open_a_barber(owner, run_id, WEEKDAYS[day.weekday()], "09:00", "12:00")
    cut, child = f"QA cut {run_id}", f"QA child {run_id}"
    cut_id = add_a_service(owner, cut, 30, "80")
    child_id = add_a_service(owner, child, 15, "60")

    parent = signed_up(person(), new_account(run_id, "parent"))
    parent.choose_by_name(barber["name"], cut, day)
    parent.by("add-person").click()
    parent.settled()
    parent.choose_service(child_id, "service-2")
    parent.by("person-name").fill("יוני")
    parent.settled()
    assert "11:30" not in parent.times(), "the last time has room for one, not for both"
    parent.pick("10:00").book(keep_answer=True)
    assert parent.last_answer["title"] == "שני התורים נקבעו"
    parent.go_to_my_bookings()
    expect(parent.rows()).to_have_count(2)
    assert "עבור יוני" in parent.text(parent.row_at("10:30").get_by_test_id("booking-detail"))

    # Each of the two takes a place toward the bookings a customer may hold: the rest go through - all but the
    # last made elsewhere, the last on this screen - and then the screen says it is full.
    me = as_persona(customers, parent, f"journey-parent-{run_id}")
    weeks = range(1, bookings_ahead_limit - 2)
    others = [at_local(shop_tz, day + timedelta(days=7 * week), "09:00") for week in weeks]
    for start in others:
        bookings.create_booking(barber["id"], cut_id, start, persona=me)
    parent.reload()
    parent.choose_by_name(barber["name"], cut, day)
    if parent.by("remove-person").is_visible():
        parent.by("remove-person").click()
        parent.settled()
    parent.pick("11:00").book()
    assert parent.last_answer["kind"] == "ok"
    parent.show_tab("book")
    expect(parent.by("limit-note")).to_be_visible()

    parent.show_tab("mine")
    parent.cancel("10:30")
    expect(parent.row_at("10:00")).to_have_attribute("data-status", "confirmed")

    diary = diary_of(barber)
    # The parent's own of the two, the one booked on the screen and those made elsewhere; the child's went.
    confirmed = diary.page.locator('[data-testid="booking-row"][data-status="confirmed"]')
    expect(confirmed).to_have_count(2 + len(others))
    expect(diary.row_at("10:30")).to_have_count(0)
    note = diary.text(diary.by("cancel-note"))
    assert "יוני" in note and "10:30" in note, "told whose booking it was: the child's, by name"

    mine = bookings.listing(persona=me)["content"]
    by_start = {parse_instant(b["start"]): b for b in mine}
    first, second = by_start[at_local(shop_tz, day, "10:00")], by_start[at_local(shop_tz, day, "10:30")]
    assert first["group_id"] and first["group_id"] == second["group_id"]
    assert (second["for_name"], second["service_id"], second["status"]) == ("יוני", child_id, "cancelled")
    assert len(mine) == 2 + len(others) + 1, "only the bookings that went through are stored"


def test_a_product_goes_from_the_owners_shelf_to_a_booking_and_the_barber_reads_it(
    person, run_id, credentials, customers, bookings, shop_tz, signed_up, diary_of
):
    day = local_day(shop_tz, 7)
    owner = person(OwnerScreen).sign_in(*credentials("owner"))
    barber = open_a_barber(owner, run_id, WEEKDAYS[day.weekday()], "09:00", "12:00")
    cut, wax = f"QA cut {run_id}", f"ווקס {run_id}"
    add_a_service(owner, cut, 30, "80")
    owner.add_product(wax, "100 מ״ל", "65")
    expect(owner.message()).to_have_attribute("data-kind", "ok")
    wax_id = editor_named(owner, "product", "name", wax)

    buyer = signed_up(person(), new_account(run_id, "buyer"))
    card = buyer.product_card(wax_id)
    assert "65" in buyer.text(card.get_by_test_id("product-line"))
    expect(card.get_by_test_id("product-keep")).to_have_count(0)
    assert "קובעים תור" in buyer.text(buyer.by("products-for"))

    buyer.choose_by_name(barber["name"], cut, day).pick("10:00").book()
    buyer.keep_product(wax_id)
    card.get_by_test_id("product-more").click()
    buyer.settled()
    assert "10:00" in buyer.text(buyer.by("products-for"))
    buyer.show_tab("mine")
    assert buyer.text(buyer.row_at("10:00").get_by_test_id("booking-products")) == f"שמור לתור: {wax} ×2"

    diary = diary_of(barber)
    assert f"{wax} ×2" in diary.text(diary.row_at("10:00").get_by_test_id("booking-products"))

    # It runs out: what is kept stays, fewer may be kept and no more.
    owner.reload()
    owner.product_editor(wax_id).get_by_test_id("product-edit-stock").uncheck()
    owner.save_product(wax_id)
    buyer.reload()
    card = buyer.product_card(wax_id)
    expect(card.get_by_test_id("product-more")).to_have_count(0)
    card.get_by_test_id("product-less").click()
    buyer.settled()
    booked = bookings.listing(persona=as_persona(customers, buyer, f"journey-buyer-{run_id}"))["content"]
    assert [b["products"] for b in booked] == [[{"id": wax_id, "name": wax, "quantity": 1}]]

    # The booking is cancelled: nothing is kept for nothing, and the shelf says to book first.
    buyer.show_tab("mine")
    buyer.cancel("10:00")
    expect(buyer.product_card(wax_id).get_by_test_id("product-release")).to_have_count(0)
    expect(buyer.product_card(wax_id).get_by_test_id("product-out")).to_be_visible()
    assert "קובעים תור" in buyer.text(buyer.by("products-for"))

    owner.product_editor(wax_id).get_by_test_id("product-edit-active").uncheck()
    owner.save_product(wax_id)
    buyer.reload()
    expect(buyer.product_card(wax_id)).to_have_count(0)


def test_a_booking_moved_on_the_screen_frees_its_old_time_for_the_next_customer(
    person, run_id, credentials, bookings, shop_tz, signed_up, diary_of
):
    day = local_day(shop_tz, 7)
    owner = person(OwnerScreen).sign_in(*credentials("owner"))
    barber = open_a_barber(owner, run_id, WEEKDAYS[day.weekday()], "09:00", "12:00")
    cut = f"QA cut {run_id}"
    add_a_service(owner, cut, 30, "80")

    first = signed_up(person(), new_account(run_id, "first"))
    first.choose_by_name(barber["name"], cut, day).pick("10:00").book()
    first.start_moving("10:00")
    first.pick("11:00").book()
    assert first.last_answer["title"] == "המועד עודכן"
    expect(first.row_at("11:00")).to_have_attribute("data-status", "confirmed")
    expect(first.rows()).to_have_count(1)

    second = signed_up(person(), new_account(run_id, "second"))
    second.choose_by_name(barber["name"], cut, day)
    assert "10:00" in second.times() and "11:00" not in second.times()
    second.pick("10:00").book()
    assert second.last_answer["kind"] == "ok"

    diary = diary_of(barber)
    expect(diary.rows()).to_have_count(2)
    stored = bookings.listing("owner", barber_id=barber["id"])["content"]
    assert sorted((parse_instant(b["start"]), b["status"]) for b in stored) == [
        (at_local(shop_tz, day, "10:00"), "confirmed"),
        (at_local(shop_tz, day, "11:00"), "confirmed"),
    ], "a move is the same booking at another time: two bookings, none cancelled"


def test_a_course_typed_by_the_owner_is_a_card_for_customers_until_it_is_withdrawn(
    person, run_id, credentials, signed_up
):
    owner = person(OwnerScreen).sign_in(*credentials("owner"))
    title = f"קורס מסע {run_id}"
    owner.add_course(title, "8 מפגשים", "2027-11-02", "3200")
    expect(owner.message()).to_have_attribute("data-kind", "ok")
    course_id = editor_named(owner, "course", "title", title)
    owner.course_editor(course_id).get_by_test_id("course-image").set_input_files(
        files=[{"name": "c.png", "mimeType": "image/png", "buffer": PNG_1X1}]
    )
    owner.settled()
    expect(owner.course_editor(course_id).locator("img")).to_have_count(1)

    reader = signed_up(person(), new_account(run_id, "reader"))
    card = reader.course_card(title)
    expect(card).to_have_count(1)
    line = reader.text(card.get_by_test_id("course-line"))
    assert "8 מפגשים" in line and "3,200" in line, line
    assert reader.page.evaluate(
        "(img) => img.complete && img.naturalWidth > 0", card.locator("img").element_handle()
    )

    owner.course_editor(course_id).get_by_test_id("course-edit-active").uncheck()
    owner.save_course(course_id)
    reader.reload()
    expect(reader.course_card(title)).to_have_count(0)


def test_an_emergency_haircut_is_asked_for_in_the_night_and_the_owner_says_yes(
    person, run_id, credentials, bookings, shop_tz, signed_up
):
    day = local_day(shop_tz, 7)
    owner = person(OwnerScreen).sign_in(*credentials("owner"))
    barber = open_a_barber(owner, run_id, WEEKDAYS[day.weekday()], "09:00", "12:00")
    cut, emergency = f"QA cut {run_id}", f"QA emergency {run_id}"
    add_a_service(owner, cut, 30, "80")
    emergency_id = add_a_service(owner, emergency, 30, "200", needs_barber=True, any_time=True)

    caller = signed_up(person(), new_account(run_id, "caller"))
    caller.choose_by_name(barber["name"], cut, day)
    assert sorted(caller.times()) == quarter_hours("09:00", "11:30"), "an ordinary service keeps to the hours"
    caller.choose_by_name(barber["name"], emergency, day)
    assert {"03:00", "23:30"} <= set(caller.times()), "an emergency has the whole day"
    caller.pick("03:00").book(keep_answer=True)
    expect(caller.by("booking-done")).to_have_attribute("data-waiting", "")
    caller.go_to_my_bookings()

    owner.reload()
    owner.select_barber(barber["id"])
    owner.answer("03:00", "approve")
    yes = told(caller)
    assert "03:00" in yes["text"], yes
    expect(caller.row_at("03:00")).to_have_attribute("data-approval", "approved")

    [stored] = bookings.listing("owner", barber_id=barber["id"])["content"]
    assert (parse_instant(stored["start"]), stored["approval"], stored["price_minor"]) == (
        at_local(shop_tz, day, "03:00"),
        "approved",
        20000,
    )
    withdraw(owner, emergency_id)
