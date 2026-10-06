"""The owner's panel for when a booking waits for its barber: the same rows as the
working hours. What a test changes it puts back (the approval_rules fixture)."""

import pytest
from playwright.sync_api import expect

from utils.local_time import at_local, local_day

WEEK = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@pytest.fixture
def owner(approval_rules, owner_screen):
    return owner_screen()


def test_the_panel_shows_the_switch_and_a_row_for_each_day(owner, approval_rules):
    rules = approval_rules.current()

    expect(owner.by("approval-panel")).to_be_visible()
    expect(owner.by("approval-row")).to_have_count(7)
    expect(owner.by("approval-enabled")).to_be_checked(checked=rules["enabled"])
    for day in WEEK:
        span = rules["hours"][day]
        row = owner.approval_row(day)
        expect(row.get_by_test_id("approval-asks")).to_be_checked(checked=span is not None)
        if span:
            expect(row.get_by_test_id("approval-from")).to_have_value(span[0])
            expect(row.get_by_test_id("approval-until")).to_have_value(span[1])


def test_the_owner_turns_it_off_and_a_customer_is_booked_at_once(
    owner, approval_rules, bookings, barbers, new_customer, ui_haircut, shop_tz
):
    barber, day = barbers.create_fake_barber(), local_day(shop_tz, 5)
    approval_rules.for_day(day, ["14:00", "16:00"])
    owner.page.reload()
    owner.settled()

    owner.by("approval-enabled").uncheck()
    owner.save_approval()

    assert "אישור הספר נשמר" in owner.text(owner.message())
    assert approval_rules.current()["enabled"] is False
    made = bookings.create_booking(
        barber["id"], ui_haircut["id"], at_local(shop_tz, day, "15:00"), persona=new_customer()
    )
    assert made["approval"] is None


def test_the_owner_sets_the_hours_of_one_day_and_the_others_never_ask(owner, approval_rules, shop_tz):
    day = local_day(shop_tz, 5)
    name = approval_rules.weekday_of(day)
    for other in WEEK:
        owner.set_approval_day(other, None)
    owner.set_approval_day(name, "09:00", "11:30")
    owner.by("approval-enabled").check()

    owner.save_approval()

    saved = approval_rules.current()
    assert saved["enabled"] is True
    assert saved["hours"][name] == ["09:00", "11:30"]
    assert all(span is None for other, span in saved["hours"].items() if other != name)


def test_hours_that_end_before_they_start_are_explained_and_nothing_is_saved(owner, approval_rules):
    before = approval_rules.current()

    owner.set_approval_day("mon", "16:00", "14:00")
    owner.save_approval()

    assert "אחרי" in owner.text(owner.message())
    assert approval_rules.current() == before


def test_hours_off_the_quarter_hour_are_explained_and_nothing_is_saved(owner, approval_rules):
    before = approval_rules.current()

    owner.set_approval_day("mon", "14:10", "16:00")
    owner.save_approval()

    assert "רבע שעה" in owner.text(owner.message())
    assert approval_rules.current() == before


def test_a_day_without_hours_cannot_be_edited_until_it_is_ticked(owner):
    owner.set_approval_day("tue", None)

    expect(owner.approval_row("tue").get_by_test_id("approval-from")).to_be_disabled()
    owner.approval_row("tue").get_by_test_id("approval-asks").check()
    expect(owner.approval_row("tue").get_by_test_id("approval-from")).to_be_enabled()


def test_a_customer_does_not_see_the_panel(signed_in):
    expect(signed_in.by("approval-panel")).to_be_hidden()
