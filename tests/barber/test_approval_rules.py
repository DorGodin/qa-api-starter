"""The owner decides when a customer's booking waits for its barber: one switch for
the shop, and per day the hours from and up to (not including). The setting is the
shop's, so each test puts back what it changed."""

from __future__ import annotations

import pytest

from utils.assertions import assert_refused
from utils.local_time import at_local, local_day


@pytest.fixture
def own_barber(barbers):
    return barbers.create_fake_barber()


def test_the_rules_have_a_switch_and_a_span_or_nothing_for_each_day(approval_rules):
    rules = approval_rules.current()

    assert isinstance(rules["enabled"], bool)
    assert set(rules["hours"]) == {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
    assert all(span is None or len(span) == 2 for span in rules["hours"].values())


def test_the_owner_saves_the_rules_and_reads_them_back(approval_rules):
    chosen = approval_rules.build_rules({"mon": ["09:00", "11:15"], "fri": ["14:00", "16:00"]}, enabled=True)

    saved = approval_rules.save(chosen).assert_ok(200).as_dict

    assert saved == chosen
    assert approval_rules.current() == chosen


def test_only_the_owner_reads_or_changes_the_rules(approval_rules, new_customer):
    me = new_customer()

    assert_refused(approval_rules.read(persona=me), 403, "forbidden")
    assert_refused(approval_rules.save(approval_rules.build_rules(), persona=me), 403, "forbidden")


@pytest.mark.parametrize(
    "rules",
    [
        {"enabled": True, "hours": {"mon": ["14:00", "16:00"]}},
        {
            "enabled": True,
            "hours": {d: ["16:00", "14:00"] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        },
        {
            "enabled": True,
            "hours": {d: ["14:10", "16:00"] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        },
        {"hours": {d: None for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}},
    ],
    ids=["a day missing", "backwards", "off the quarter hour", "no switch"],
)
def test_rules_that_make_no_sense_are_refused_and_change_nothing(approval_rules, rules):
    before = approval_rules.current()

    assert approval_rules.save(rules).status_code == 422
    assert approval_rules.current() == before


def test_turned_off_a_booking_in_the_hours_is_booked_at_once(
    approval_rules, bookings, own_barber, haircut, new_customer, shop_tz
):
    day = local_day(shop_tz, 5)
    approval_rules.for_day(day, ["14:00", "16:00"], enabled=False)

    made = bookings.create_booking(
        own_barber["id"], haircut["id"], at_local(shop_tz, day, "15:00"), persona=new_customer()
    )

    assert made["approval"] is None


def test_it_asks_only_on_the_days_and_hours_the_owner_chose(
    approval_rules, bookings, own_barber, haircut, new_customer, shop_tz
):
    day, next_day = local_day(shop_tz, 5), local_day(shop_tz, 6)
    approval_rules.for_day(day, ["09:00", "11:00"])

    def booked(on, hhmm):
        return bookings.create_booking(
            own_barber["id"], haircut["id"], at_local(shop_tz, on, hhmm), persona=new_customer()
        )["approval"]

    assert booked(day, "10:00") == "pending"
    assert booked(day, "15:00") is None
    assert booked(next_day, "10:00") is None


def test_a_change_leaves_bookings_already_waiting_to_wait(
    approval_rules, bookings, own_barber, haircut, new_customer, shop_tz
):
    day, me = local_day(shop_tz, 5), new_customer()
    approval_rules.for_day(day, ["14:00", "16:00"])
    waiting = bookings.create_booking(
        own_barber["id"], haircut["id"], at_local(shop_tz, day, "15:00"), persona=me
    )

    approval_rules.for_day(day, None, enabled=False)

    assert bookings.get_by_id(waiting["id"], persona=me).assert_ok(200).as_dict["approval"] == "pending"
