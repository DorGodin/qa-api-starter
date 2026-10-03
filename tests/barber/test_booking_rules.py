"""The rules a booking must satisfy, each at its boundary, each refused with its code."""

import pytest

from obj.barber import BOOKING_WINDOW_DAYS
from utils.assertions import assert_refused
from utils.local_time import at_local, local_day, parse_instant


@pytest.fixture(scope="module")
def shop_hours_barber(barbers):
    """Nine to seven, every day - for the rules that are about closing time."""
    return barbers.create_fake_barber(opening="09:00", closing="19:00")


def test_a_haircut_that_would_run_past_closing_is_refused_but_one_ending_at_closing_is_not(
    barbers, bookings, shop_hours_barber, haircut, new_customer, shop_tz
):
    day = local_day(shop_tz, 4)
    last_offered = barbers.slots(shop_hours_barber["id"], day, haircut["id"])[-1]

    too_late = bookings.book(
        shop_hours_barber["id"], haircut["id"], at_local(shop_tz, day, "18:45"), persona=new_customer()
    )
    just_fits = bookings.book(
        shop_hours_barber["id"], haircut["id"], at_local(shop_tz, day, "18:30"), persona=new_customer()
    )

    assert (
        parse_instant(last_offered["start_local"]).strftime("%H:%M") == "18:30"
    ), "the listing offers what the booking refuses"
    assert_refused(too_late, 422, "outside_hours")
    assert just_fits.status_code == 201, just_fits.as_dict


def test_nothing_before_opening(bookings, shop_hours_barber, haircut, new_customer, shop_tz):
    early = bookings.book(
        shop_hours_barber["id"],
        haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 4), "08:45"),
        persona=new_customer(),
    )

    assert_refused(early, 422, "outside_hours")


def offered_instants(barbers, barber_id, day, service_id, persona="customer") -> set:
    """Compare instants, never strings: the product writes 06:15:00Z and to_iso
    writes 06:15:00.000Z, and a membership check across the two formats is always
    False - which once made an assertion here pass whatever the product did."""
    return {parse_instant(s["start"]) for s in barbers.slots(barber_id, day, service_id, persona=persona)}


def test_the_listing_offers_the_slots_right_before_and_right_after_a_booking(
    barbers, bookings, haircut, trim, new_customer, shop_tz
):
    fresh = barbers.create_fake_barber()
    day = local_day(shop_tz, 5)
    bookings.create_booking(
        fresh["id"], haircut["id"], at_local(shop_tz, day, "10:00"), persona=new_customer()
    )

    offered = offered_instants(barbers, fresh["id"], day, trim["id"])

    assert (
        at_local(shop_tz, day, "09:45") in offered
    ), "09:45-10:00 touches the booking and does not overlap it"
    assert at_local(shop_tz, day, "10:30") in offered, "10:30 starts where the booking ends"
    assert at_local(shop_tz, day, "10:00") not in offered and at_local(shop_tz, day, "10:15") not in offered


def test_back_to_back_is_allowed_and_an_overlap_is_not(
    bookings, barber, haircut, trim, new_customer, shop_tz
):
    day = local_day(shop_tz, 5)
    bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, day, "10:00"), persona=new_customer()
    )

    overlapping = bookings.book(
        barber["id"], trim["id"], at_local(shop_tz, day, "10:15"), persona=new_customer()
    )
    right_after = bookings.book(
        barber["id"], trim["id"], at_local(shop_tz, day, "10:30"), persona=new_customer()
    )
    right_before = bookings.book(
        barber["id"], trim["id"], at_local(shop_tz, day, "09:45"), persona=new_customer()
    )

    assert_refused(overlapping, 409, "slot_taken")
    assert right_after.status_code == 201, "10:30 starts where 10:00-10:30 ends"
    assert right_before.status_code == 201, "09:45-10:00 ends where 10:00 starts"


def test_one_customer_cannot_be_in_two_chairs_at_once(
    barbers, bookings, barber, haircut, new_customer, shop_tz
):
    me = new_customer()
    second = barbers.create_fake_barber()
    day = local_day(shop_tz, 5)
    bookings.create_booking(barber["id"], haircut["id"], at_local(shop_tz, day, "12:00"), persona=me)

    clash = bookings.book(second["id"], haircut["id"], at_local(shop_tz, day, "12:15"), persona=me)
    offered_to_me = offered_instants(barbers, second["id"], day, haircut["id"], persona=me)
    offered_to_others = offered_instants(barbers, second["id"], day, haircut["id"], persona=new_customer())

    assert_refused(clash, 409, "customer_overlap")
    assert (
        at_local(shop_tz, day, "12:15") in offered_to_others
    ), "the check below would be vacuous if nobody were offered it"
    assert at_local(shop_tz, day, "12:15") not in offered_to_me, "offered a time the booking then refuses"


def test_a_start_off_the_quarter_hour_is_assert_refused(bookings, barber, haircut, new_customer, shop_tz):
    assert_refused(
        bookings.book(
            barber["id"],
            haircut["id"],
            at_local(shop_tz, local_day(shop_tz, 5), "10:05"),
            persona=new_customer(),
        ),
        422,
        "not_aligned",
    )


def test_a_start_without_a_utc_offset_is_assert_refused(bookings, barber, haircut, new_customer, shop_tz):
    naive = f"{local_day(shop_tz, 5).isoformat()}T10:00:00"

    assert bookings.book(barber["id"], haircut["id"], naive, persona=new_customer()).status_code == 422


def test_the_past_is_refused_in_the_listing_and_the_booking(
    barbers, bookings, barber, haircut, new_customer, shop_tz
):
    yesterday = local_day(shop_tz, -1)

    assert_refused(barbers.availability(barber["id"], yesterday, haircut["id"]), 422, "in_past")
    assert_refused(
        bookings.book(
            barber["id"], haircut["id"], at_local(shop_tz, yesterday, "10:00"), persona=new_customer()
        ),
        422,
        "in_past",
    )


def test_the_booking_window_is_enforced_in_the_listing_and_the_booking(
    barbers, bookings, barber, haircut, new_customer, shop_tz
):
    inside, outside = local_day(shop_tz, BOOKING_WINDOW_DAYS - 1), local_day(shop_tz, BOOKING_WINDOW_DAYS + 1)

    assert barbers.availability(barber["id"], inside, haircut["id"]).status_code == 200
    assert_refused(barbers.availability(barber["id"], outside, haircut["id"]), 422, "beyond_window")
    assert_refused(
        bookings.book(
            barber["id"], haircut["id"], at_local(shop_tz, outside, "10:00"), persona=new_customer()
        ),
        422,
        "beyond_window",
    )


def test_nothing_is_offered_or_booked_on_a_day_off(barbers, bookings, haircut, new_customer, shop_tz):
    off = barbers.create_fake_barber()
    day = local_day(shop_tz, 6)
    barbers.add_time_off(off["id"], day).assert_ok(201)

    assert barbers.slots(off["id"], day, haircut["id"]) == []
    assert_refused(
        bookings.book(off["id"], haircut["id"], at_local(shop_tz, day, "10:00"), persona=new_customer()),
        422,
        "barber_off",
    )


def test_a_withdrawn_service_is_neither_listed_nor_booked(
    barbers, bookings, services, barber, new_customer, shop_tz
):
    service = services.create_fake_service()
    services.deactivate(service["id"])
    day = local_day(shop_tz, 6)

    assert_refused(barbers.availability(barber["id"], day, service["id"]), 422, "service_inactive")
    assert_refused(
        bookings.book(barber["id"], service["id"], at_local(shop_tz, day, "10:00"), persona=new_customer()),
        422,
        "service_inactive",
    )


def test_every_slot_the_listing_offers_can_actually_be_booked(
    barbers, bookings, haircut, new_customer, shop_tz
):
    fresh = barbers.create_fake_barber(opening="09:00", closing="19:00")
    day = local_day(shop_tz, 7)
    offered = barbers.slots(fresh["id"], day, haircut["id"])

    results = [
        bookings.book(fresh["id"], haircut["id"], slot["start"], persona=new_customer()).status_code
        for slot in offered[::2]
    ]

    assert results == [201] * len(results), f"offered slots that were then refused: {results}"


def test_a_new_barber_starts_on_the_shop_hours_friday_until_two(barbers):
    created = barbers.create(barbers.build_barber_payload(), persona="owner").assert_ok(201).as_dict

    hours = barbers.hours(created["id"])

    assert {day: tuple(span) for day, span in hours.items() if span} == {
        **dict.fromkeys(("sun", "mon", "tue", "wed", "thu"), ("10:00", "19:00")),
        "fri": ("10:00", "14:00"),
    }
    assert hours["sat"] is None
