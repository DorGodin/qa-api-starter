"""The booking page inside the shop's app: notifications are the phone's own, through Firebase. The app's
plugin is a stand-in here, as the browser's push pieces are in test_push_card.py; what it gives the page goes
to the server, and the server's message reaches the fake Firebase."""

import pytest
from playwright.sync_api import expect

from utils.local_time import at_local, local_day

APP = """
window.__device = %r;
window.__asked = 0;
window.Capacitor = {
  isNativePlatform: () => true,
  getPlatform: () => "android",
  Plugins: { FirebaseMessaging: {
    requestPermissions: async () => { window.__asked += 1; return { receive: "granted" }; },
    getToken: async () => ({ token: window.__device }),
    deleteToken: async () => {},
  } },
};
"""


@pytest.fixture
def in_the_app(shop, push, push_inbox, new_customer):
    if push.register_device(push_inbox.new_device_token(), new_customer()).status_code == 404:
        pytest.skip("this copy of the shop sends no phone notifications (no FCM_CREDENTIALS)")
    token = push_inbox.new_device_token()
    shop.page.add_init_script(APP % token)
    return token


def test_in_the_app_turning_notifications_on_registers_the_phone_and_it_is_told(
    in_the_app, shop, account, push_inbox, bookings, barbers, ui_haircut, shop_tz
):
    barber = barbers.create_fake_barber()
    made = bookings.create_booking(
        barber["id"],
        ui_haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 9), "15:00"),
        persona=account["persona"],
    )
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("mine")
    expect(signed_in.by("install-card")).to_be_hidden()

    signed_in.by("push-on").click()
    signed_in.settled()
    expect(signed_in.by("push-card")).to_have_attribute("data-state", "on")
    bookings.approve(made["id"], persona="owner").assert_ok(200)

    told = push_inbox.wait_for_phone(in_the_app)
    assert [m["message"]["notification"]["title"] for m in told] == ["עדכון על התור שלך"]
    assert signed_in.page.evaluate("window.__asked") == 1


def test_signing_out_in_the_app_tells_that_phone_nothing_more(
    in_the_app, shop, account, push, push_inbox, bookings, barbers, ui_haircut, shop_tz
):
    barber = barbers.create_fake_barber()
    made = bookings.create_booking(
        barber["id"],
        ui_haircut["id"],
        at_local(shop_tz, local_day(shop_tz, 9), "15:00"),
        persona=account["persona"],
    )
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("mine")
    signed_in.by("push-on").click()
    signed_in.settled()

    with signed_in.page.expect_response(lambda r: r.url.endswith("/push/devices/remove")):
        signed_in.sign_out()
    expect(signed_in.by("auth")).to_be_visible()
    bookings.approve(made["id"], persona="owner").assert_ok(200)

    assert push_inbox.phone_stays_quiet(in_the_app) == []
