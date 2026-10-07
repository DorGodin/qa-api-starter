"""The calendar opens whole for a service that works at any time; the owner ticks it per service."""

import secrets

from playwright.sync_api import expect

from utils.local_time import at_local, local_day


def test_a_customer_choosing_it_sees_every_hour_but_not_the_ones_taken(
    barbers, bookings, shop, account, new_customer, services, shop_tz
):
    barber = barbers.create_fake_barber(opening="09:00", closing="10:00")
    emergency = services.create_fake_service(any_time=True)
    day = local_day(shop_tz, 6)
    bookings.create_booking(
        barber["id"], emergency["id"], at_local(shop_tz, day, "18:00"), persona=new_customer()
    )
    signed_in = shop.sign_in_as(account)

    signed_in.choose(barber["id"], emergency["id"], day)

    times = signed_in.times()
    assert "03:00" in times and "23:15" in times and "18:30" in times
    assert "18:00" not in times and "17:45" not in times


def test_the_owner_ticks_a_service_as_working_at_any_time(owner_screen, services):
    service = services.create_fake_service()
    owner = owner_screen()
    expect(owner.service_row(service["id"]).get_by_test_id("service-any-time")).not_to_be_checked()

    owner.save_service(service["id"], any_time=True)

    saved = next(s for s in services.find(persona="owner").assert_ok(200).content if s["id"] == service["id"])
    assert saved["any_time"] is True


def test_the_owner_adds_a_service_that_works_at_any_time(owner_screen, services):
    name = f"חירום {secrets.token_hex(3)}"

    owner_screen().add_service(name, 30, "200", needs_barber=True, any_time=True)

    made = next(s for s in services.find(persona="owner").assert_ok(200).content if s["name"] == name)
    assert (made["any_time"], made["requires_approval"]) == (True, True)
