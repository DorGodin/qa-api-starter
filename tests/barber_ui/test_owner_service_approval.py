"""The owner's services list: a tick for the services whose every booking waits for the barber."""

import secrets

from playwright.sync_api import expect


def test_the_owner_ticks_a_service_and_saves_it(owner_screen, services):
    service = services.create_fake_service()
    owner = owner_screen()
    expect(owner.service_row(service["id"]).get_by_test_id("service-approval")).not_to_be_checked()

    owner.save_service(service["id"], needs_barber=True)

    saved = next(s for s in services.find(persona="owner").assert_ok(200).content if s["id"] == service["id"])
    assert saved["requires_approval"] is True
    expect(owner.service_row(service["id"]).get_by_test_id("service-approval")).to_be_checked()


def test_the_owner_adds_a_service_that_needs_the_barber(owner_screen, services):
    name = f"חירום {secrets.token_hex(3)}"
    owner = owner_screen()

    owner.add_service(name, 30, "200", needs_barber=True)

    made = next(s for s in services.find(persona="owner").assert_ok(200).content if s["name"] == name)
    assert made["requires_approval"] is True
    expect(owner.by("new-service-approval")).not_to_be_checked()
