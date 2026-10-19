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


def test_on_a_phone_the_personal_area_is_a_tab_of_its_own(shop, account):
    shop.page.set_viewport_size({"width": 390, "height": 844})
    signed_in = shop.sign_in_as(account)

    signed_in.show_tab("mine")
    expect(signed_in.by("account-panel")).to_be_hidden()
    signed_in.show_tab("account")

    expect(signed_in.by("account-panel")).to_be_visible()
    expect(signed_in.by("right-panel")).to_be_hidden()


def test_a_customers_screen_has_no_bar_on_top_and_signs_out_from_the_personal_area(shop, account):
    signed_in = shop.sign_in_as(account)
    expect(signed_in.by("logout")).to_be_hidden()
    signed_in.show_tab("account")

    signed_in.by("account-logout").click()

    expect(signed_in.by("auth")).to_be_visible()


def test_the_personal_area_has_the_foot_of_the_page_the_ways_to_the_shop_and_the_two_pages(shop, account):
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("account")

    foot = signed_in.by("account-foot")

    expect(signed_in.by("account-privacy")).to_have_attribute("href", "/privacy")
    expect(signed_in.by("account-accessibility")).to_have_attribute("href", "/accessibility")
    assert foot.locator("a.action").count() == signed_in.page.locator("body > footer a.action").count()
    expect(foot.locator("[data-testid]")).to_have_count(2)


def test_the_staff_still_sign_out_from_the_bar(owner_screen):
    owner = owner_screen()

    expect(owner.by("logout")).to_be_visible()


def test_on_a_phone_the_personal_area_shows_the_ways_to_the_shop_once(shop, account):
    shop.page.set_viewport_size({"width": 390, "height": 844})
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("account")

    expect(signed_in.by("account-foot")).to_be_visible()
    expect(signed_in.page.locator("body > footer")).to_be_hidden()
    # On the other tabs the page's foot is back - when the shop has ways to be reached to show in it.
    if signed_in.page.locator("body > footer a.action").count():
        signed_in.show_tab("book")
        expect(signed_in.page.locator("body > footer")).to_be_visible()


def test_the_statement_and_the_policy_lead_back_to_the_personal_area(shop, account):
    shop.page.set_viewport_size({"width": 390, "height": 844})
    signed_in = shop.sign_in_as(account)
    for link in ("account-privacy", "account-accessibility"):
        signed_in.show_tab("account")
        signed_in.by(link).click()
        back = signed_in.page.get_by_test_id("back-top")
        expect(back).to_be_visible()
        expect(back).to_have_accessible_name("חזרה")
        expect(back).to_have_text("")
        box, width = back.bounding_box(), signed_in.page.viewport_size["width"]
        assert box["x"] + box["width"] < width / 2, "top left, out of the title's way"

        back.click()
        signed_in.settled()
        expect(signed_in.by("account-panel")).to_be_visible()
        assert "#" not in signed_in.page.url


def test_the_page_for_deleting_an_account_leads_to_the_personal_areas_question(shop, account, env_config):
    """Google Play asks for a web address to delete an account from outside the app: it explains, and its
    button opens the personal area with the dialog that asks."""
    signed_in = shop.sign_in_as(account)
    signed_in.page.goto(env_config["url"].rstrip("/") + "/delete-account")
    expect(signed_in.page.get_by_role("heading", name="מחיקת חשבון")).to_be_visible()

    signed_in.page.get_by_test_id("delete-start").click()
    signed_in.settled()

    expect(signed_in.by("account-panel")).to_be_visible()
    expect(signed_in.by("delete-dialog")).to_be_visible()
    assert "#" not in signed_in.page.url
