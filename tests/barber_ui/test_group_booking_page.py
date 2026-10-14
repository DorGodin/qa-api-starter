"""Booking for two on the page: the second service and name under the first, the times where both
fit, one card for both, and the list that says who the second is for."""

from playwright.sync_api import expect

from obj.barber.barbers import WEEK
from tests.barber_ui.test_owner_today import later_today
from utils.local_time import at_local, local_day


def add_a_second_person(screen, service) -> None:
    """Their service is chosen, never left to whatever the shop lists first: another test's
    service that waits for the barber's yes turned a booking for two into a request."""
    screen.by("add-person").click()
    screen.settled()
    screen.by("service-2").select_option(value=service["id"])
    screen.settled()


def test_the_times_for_two_are_where_both_fit_and_one_booking_makes_two(
    barbers, shop, account, bookings, ui_haircut, shop_tz
):
    barber = barbers.create_fake_barber()
    barbers.set_hours(barber["id"], {"hours": dict.fromkeys(WEEK, ["09:00", "10:00"])}).assert_ok(200)
    day = local_day(shop_tz, 6)
    signed_in = shop.sign_in_as(account)
    signed_in.choose(barber["id"], ui_haircut["id"], day)
    assert signed_in.times() == ["09:30", "09:15", "09:00"] or sorted(signed_in.times()) == [
        "09:00",
        "09:15",
        "09:30",
    ]

    add_a_second_person(signed_in, ui_haircut)
    signed_in.by("person-name").fill("יוני")
    signed_in.settled()

    assert signed_in.times() == ["09:00"]
    signed_in.pick("09:00")
    assert "+" in signed_in.text(signed_in.by("confirm-text"))
    signed_in.book(keep_answer=True)
    assert signed_in.last_answer["title"] == "שני התורים נקבעו"
    signed_in.go_to_my_bookings()
    expect(signed_in.rows()).to_have_count(2)
    assert "עבור יוני" in signed_in.text(signed_in.rows().nth(1).get_by_test_id("booking-detail"))
    assert len(bookings.listing(persona=account["persona"])["content"]) == 2


def test_removing_the_second_person_brings_back_the_single_times(barbers, shop, account, ui_haircut, shop_tz):
    barber = barbers.create_fake_barber()
    barbers.set_hours(barber["id"], {"hours": dict.fromkeys(WEEK, ["09:00", "10:00"])}).assert_ok(200)
    signed_in = shop.sign_in_as(account)
    signed_in.choose(barber["id"], ui_haircut["id"], local_day(shop_tz, 6))
    add_a_second_person(signed_in, ui_haircut)
    assert signed_in.times() == ["09:00"]

    signed_in.by("remove-person").click()
    signed_in.settled()

    assert len(signed_in.times()) == 3
    expect(signed_in.by("companion")).to_be_hidden()


def test_the_control_is_not_offered_to_the_owner(owner_screen):
    expect(owner_screen().by("add-person")).to_be_hidden()


def test_the_control_is_not_offered_while_moving_a_booking(
    barbers, shop, account, bookings, ui_haircut, shop_tz
):
    barber = barbers.create_fake_barber()
    day = local_day(shop_tz, 7)
    made = bookings.create_booking(
        barber["id"], ui_haircut["id"], at_local(shop_tz, day, "11:00"), persona=account["persona"]
    )
    signed_in = shop.sign_in_as(account)
    signed_in.choose(barber["id"], ui_haircut["id"], day)
    add_a_second_person(signed_in, ui_haircut)

    signed_in.start_moving(made["start_local"][11:16])

    expect(signed_in.by("companion-field")).to_be_hidden()
    expect(signed_in.by("companion")).to_be_hidden()


def test_the_confirm_button_keeps_one_line_beside_the_words_for_two(
    barbers, shop, account, ui_haircut, shop_tz
):
    barber = barbers.create_fake_barber()
    signed_in = shop.sign_in_as(account)
    signed_in.choose(barber["id"], ui_haircut["id"], local_day(shop_tz, 6))
    add_a_second_person(signed_in, ui_haircut)

    signed_in.pick("10:00")

    lines = signed_in.by("book").evaluate(
        "b => { const r = document.createRange(); r.selectNodeContents(b); return r.getClientRects().length; }"
    )
    assert lines == 1, f"the button's words are on {lines} lines"
    assert "סך הכול" not in signed_in.text(signed_in.by("confirm-text"))


def test_the_staffs_day_names_the_second_person_not_the_parent(
    barbers, bookings, account, ui_haircut, owner_screen, shop_tz
):
    barber = barbers.create_fake_barber()
    start = later_today(1, shop_tz, minutes=2 * ui_haircut["duration_minutes"])

    bookings.create_group(
        barber["id"],
        start,
        [{"service_id": ui_haircut["id"]}, {"service_id": ui_haircut["id"], "name": "יוני"}],
        persona=account["persona"],
    )
    owner = owner_screen().select_barber(barber["id"])

    blocks = [owner.text(b) for b in owner.by("timeline-booking").all()]
    assert any(account["display_name"] in b for b in blocks) and any("יוני" in b for b in blocks), blocks
