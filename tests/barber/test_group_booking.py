"""Booking for two - the customer and a child or a friend - back to back with one barber, all or none."""

from __future__ import annotations

import pytest

from obj.barber import GROUP_MAX
from obj.barber.barbers import WEEK
from utils.assertions import assert_refused
from utils.local_time import at_local, local_day, parse_instant


@pytest.fixture
def own_barber(barbers):
    return barbers.create_fake_barber()


@pytest.fixture
def short_barber(barbers):
    barber = barbers.create_fake_barber()
    barbers.set_hours(barber["id"], {"hours": dict.fromkeys(WEEK, ["09:00", "10:00"])}).assert_ok(200)
    return barber


def people(*services, name=None):
    return [{"service_id": s["id"], **({"name": name} if i and name else {})} for i, s in enumerate(services)]


def test_two_bookings_back_to_back_with_one_barber_for_one_customer(
    bookings, own_barber, haircut, services, new_customer, shop_tz
):
    trim = services.create_fake_service(duration_minutes=15, price_minor=4000)
    me = new_customer()

    first, second = bookings.create_group(
        own_barber["id"],
        at_local(shop_tz, local_day(shop_tz, 4), "10:00"),
        people(haircut, trim, name="יוני"),
        persona=me,
    )

    assert parse_instant(second["start"]) == parse_instant(first["end"])
    assert (first["barber_id"], first["customer_id"]) == (second["barber_id"], second["customer_id"])
    assert first["group_id"] == second["group_id"] and first["group_id"]
    assert (first["for_name"], second["for_name"]) == (None, "יוני")
    assert second["price_minor"] == trim["price_minor"] and first["price_minor"] == haircut["price_minor"]


def test_if_the_second_does_not_fit_in_the_barbers_hours_nothing_is_booked(
    bookings, short_barber, haircut, new_customer, shop_tz
):
    me = new_customer()

    refused = bookings.book_group(
        short_barber["id"],
        at_local(shop_tz, local_day(shop_tz, 4), "09:30"),
        people(haircut, haircut),
        persona=me,
    )

    assert_refused(refused, 422, "outside_hours")
    assert bookings.listing(persona=me)["total"] == 0


def test_if_the_second_time_is_taken_nothing_is_booked(bookings, own_barber, haircut, new_customer, shop_tz):
    day, me = local_day(shop_tz, 4), new_customer()
    bookings.create_booking(
        own_barber["id"], haircut["id"], at_local(shop_tz, day, "10:30"), persona=new_customer()
    )

    refused = bookings.book_group(
        own_barber["id"], at_local(shop_tz, day, "10:00"), people(haircut, haircut), persona=me
    )

    assert_refused(refused, 409, "slot_taken")
    assert bookings.listing(persona=me)["total"] == 0


def test_a_group_counts_as_one_toward_the_limit_of_bookings_ahead(
    bookings, own_barber, haircut, new_customer, shop_tz
):
    me = new_customer()
    bookings.create_group(
        own_barber["id"],
        at_local(shop_tz, local_day(shop_tz, 4), "10:00"),
        people(haircut, haircut),
        persona=me,
    )

    bookings.create_booking(
        own_barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 5), "10:00"), persona=me
    )

    refused = bookings.book(
        own_barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 6), "10:00"), persona=me
    )
    assert_refused(refused, 409, "too_many_bookings")


def test_a_customer_at_the_limit_cannot_book_a_group(bookings, own_barber, haircut, new_customer, shop_tz):
    me = new_customer()
    for hhmm in ("09:00", "11:00"):
        bookings.create_booking(
            own_barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 3), hhmm), persona=me
        )

    refused = bookings.book_group(
        own_barber["id"],
        at_local(shop_tz, local_day(shop_tz, 4), "10:00"),
        people(haircut, haircut),
        persona=me,
    )

    assert_refused(refused, 409, "too_many_bookings")


def test_more_people_than_the_shop_allows_is_refused(bookings, own_barber, haircut, new_customer, shop_tz):
    crowd = people(*([haircut] * (GROUP_MAX + 1)))

    refused = bookings.book_group(
        own_barber["id"], at_local(shop_tz, local_day(shop_tz, 4), "10:00"), crowd, persona=new_customer()
    )

    assert refused.status_code == 422


def test_one_person_is_not_a_group(bookings, own_barber, haircut, new_customer, shop_tz):
    refused = bookings.book_group(
        own_barber["id"],
        at_local(shop_tz, local_day(shop_tz, 4), "10:00"),
        people(haircut),
        persona=new_customer(),
    )

    assert refused.status_code == 422


def test_only_a_customer_books_a_group(bookings, own_barber, haircut, shop_tz):
    refused = bookings.book_group(
        own_barber["id"],
        at_local(shop_tz, local_day(shop_tz, 4), "10:00"),
        people(haircut, haircut),
        persona="owner",
    )

    assert_refused(refused, 403, "forbidden")


def test_the_times_offered_for_two_are_where_both_fit_one_after_the_other(
    barbers, short_barber, haircut, new_customer, shop_tz
):
    me, day = new_customer(), local_day(shop_tz, 4)

    alone = barbers.slots(short_barber["id"], day, haircut["id"], persona=me)
    both = barbers.availability(
        short_barber["id"], day, haircut["id"], persona=me, also=[haircut["id"]]
    ).assert_ok(200)

    assert len(alone) == 3
    assert [parse_instant(s["start"]) for s in both.as_dict["slots"]] == [at_local(shop_tz, day, "09:00")]


def test_the_calendar_counts_the_times_for_two(barbers, short_barber, haircut, new_customer, shop_tz):
    me, month = new_customer(), local_day(shop_tz, 4).isoformat()[:7]

    alone = barbers.days(short_barber["id"], month, haircut["id"], persona=me).assert_ok(200).as_dict["days"]
    paired = (
        barbers.days(short_barber["id"], month, haircut["id"], persona=me, also=[haircut["id"]])
        .assert_ok(200)
        .as_dict["days"]
    )

    assert alone[2]["free"] == 3 and paired[2]["free"] == 1


def test_each_booking_waits_for_the_barber_by_the_same_rules(
    bookings, own_barber, haircut, new_customer, shop_tz
):
    made = bookings.create_group(
        own_barber["id"],
        at_local(shop_tz, local_day(shop_tz, 4), "15:00"),
        people(haircut, haircut),
        persona=new_customer(),
    )

    assert [b["approval"] for b in made] == ["pending", "pending"]


def test_afterwards_each_is_a_booking_of_its_own(bookings, own_barber, haircut, new_customer, shop_tz):
    me = new_customer()
    first, second = bookings.create_group(
        own_barber["id"],
        at_local(shop_tz, local_day(shop_tz, 5), "10:00"),
        people(haircut, haircut),
        persona=me,
    )

    cancelled = bookings.cancel(first["id"], persona=me).assert_ok(200).as_dict

    assert cancelled["status"] == "cancelled"
    assert bookings.get_by_id(second["id"], persona=me).assert_ok(200).as_dict["status"] == "confirmed"
