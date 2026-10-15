"""The customer's own account, a tab of its own on a phone, and deleting it there - as both stores
require of an app one can sign up in."""

from playwright.sync_api import expect

from utils.local_time import at_local, local_day


def test_the_account_tab_shows_who_is_signed_in_and_the_way_to_the_privacy_policy(shop, account):
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("account")

    panel = signed_in.by("account-panel")

    expect(panel).to_be_visible()
    expect(signed_in.by("account-name")).to_have_text(account["display_name"])
    expect(signed_in.by("account-phone")).to_have_text(account["phone"])
    expect(signed_in.by("account-privacy")).to_have_attribute("href", "/privacy")


def test_cancel_keeps_the_account(shop, account, api):
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("account")

    signed_in.by("account-delete").click()
    expect(signed_in.by("delete-dialog")).to_be_visible()
    expect(signed_in.by("delete-cancel")).to_be_focused()
    signed_in.by("delete-cancel").click()

    expect(signed_in.by("delete-dialog")).to_be_hidden()
    assert api.request("GET", "/me", persona=account["persona"]).status_code == 200


def test_deleting_signs_out_cancels_what_is_ahead_and_says_so(
    shop, account, api, bookings, barbers, ui_haircut, shop_tz
):
    barber = barbers.create_fake_barber()
    made = bookings.create_booking(
        barber["id"],
        ui_haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 6), "11:00"),
        persona=account["persona"],
    )
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("account")

    signed_in.by("account-delete").click()
    signed_in.by("delete-confirm").click()
    signed_in.settled()

    expect(signed_in.by("auth")).to_be_visible()
    expect(signed_in.by("account-panel")).to_be_hidden()
    expect(signed_in.by("account-deleted")).to_be_visible()
    assert "החשבון נמחק" in signed_in.text(signed_in.by("account-deleted"))
    assert account["display_name"] not in signed_in.page.evaluate("document.body.innerText")
    assert api.request("GET", "/me", persona=account["persona"]).status_code == 401
    assert bookings.get_by_id(made["id"], persona="owner").as_dict["status"] == "cancelled"


def test_the_owner_is_told_a_deleted_customer_cancelled_without_their_name(
    shop, account, api, bookings, barbers, ui_haircut, owner_screen, shop_tz
):
    barber = barbers.create_fake_barber()
    bookings.create_booking(
        barber["id"],
        ui_haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 6), "12:00"),
        persona=account["persona"],
    )
    api.request("DELETE", "/me", persona=account["persona"])

    owner = owner_screen().select_barber(barber["id"])

    note = owner.text(owner.by("cancel-note"))
    assert "לקוח שנמחק" in note and account["display_name"] not in note


def test_the_staff_have_no_account_tab(owner_screen):
    owner = owner_screen()

    expect(owner.by("account-panel")).to_be_hidden()
    expect(owner.by("tab-account")).to_be_hidden()
