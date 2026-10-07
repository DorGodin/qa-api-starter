"""The card that asks for notifications. A headless browser has no push service to subscribe to, so
the browser's own pieces - the permission, the service worker, the subscription - are replaced by
stand-ins that keep a record; what is tested is what the page does with them and what it tells the
server."""

import json

import pytest
from playwright.sync_api import expect

STUB = """
(() => {
  const state = { permission: "default", sub: null, registered: null, ask: "granted", subscribes: 0 };
  window.__push = state;
  Object.defineProperty(window, "Notification", {
    configurable: true,
    value: { get permission() { return state.permission; }, requestPermission: async () => { state.permission = state.ask; return state.ask; } },
  });
  window.PushManager = window.PushManager || function () {};
  const registration = {
    pushManager: {
      getSubscription: async () => state.sub,
      subscribe: async () => {
        state.subscribes += 1;
        state.sub = { endpoint: "https://fcm.googleapis.com/fcm/send/stub-" + Math.random().toString(16).slice(2), unsubscribe: async () => { state.sub = null; return true; } };
        return state.sub;
      },
    },
  };
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: { register: async (url) => { state.registered = url; return registration; }, ready: Promise.resolve(registration), getRegistration: async () => registration },
  });
})();
"""


@pytest.fixture
def ready(push, new_customer):
    if push.key(new_customer()).status_code == 404:
        pytest.skip("this copy of the shop has no VAPID key pair set")


def sent_to(page, path):
    seen = []
    page.on(
        "request",
        lambda r: seen.append(json.loads(r.post_data))
        if r.method == "POST" and r.url.endswith(path)
        else None,
    )
    return seen


def test_a_customer_is_asked_once_and_the_card_says_what_it_is_for(ready, shop, account):
    shop.page.add_init_script(STUB)
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("mine")

    card = signed_in.by("push-card")

    expect(card).to_have_attribute("data-state", "ask")
    assert "עדכון כשיש תשובה" in signed_in.text(card.locator("h3"))
    assert "לא מכילה פרטים" in signed_in.text(card.locator("p"))


def test_saying_yes_asks_the_browser_registers_the_worker_and_tells_the_server(ready, shop, account):
    shop.page.add_init_script(STUB)
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("mine")
    sent = sent_to(shop.page, "/push/subscribe")

    signed_in.by("push-on").click()
    signed_in.settled()

    assert len(sent) == 1 and sent[0]["endpoint"].startswith("https://fcm.googleapis.com/")
    assert shop.page.evaluate("window.__push.registered") == "/sw.js?role=customer"
    expect(signed_in.by("push-card")).to_have_attribute("data-state", "on")
    assert "עדכונים פעילים" in signed_in.text(signed_in.by("push-card"))


def test_turning_it_off_unsubscribes_and_the_card_asks_again(ready, shop, account):
    shop.page.add_init_script(STUB)
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("mine")
    signed_in.by("push-on").click()
    signed_in.settled()
    sent = sent_to(shop.page, "/push/unsubscribe")

    signed_in.by("push-off").click()
    signed_in.settled()

    assert len(sent) == 1
    assert shop.page.evaluate("window.__push.sub") is None
    expect(signed_in.by("push-card")).to_have_attribute("data-state", "ask")


def test_a_browser_that_is_already_subscribed_shows_that_it_is_on(ready, shop, account):
    shop.page.add_init_script(
        STUB
        + "window.__push.sub = { endpoint: 'https://fcm.googleapis.com/fcm/send/already', unsubscribe: async () => true };"
    )
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("mine")

    expect(signed_in.by("push-card")).to_have_attribute("data-state", "on")


def test_not_now_hides_the_card_and_it_stays_hidden_after_opening_again(ready, shop, account):
    shop.page.add_init_script(STUB)
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("mine")

    signed_in.by("push-later").click()
    signed_in.settled()
    signed_in.reload()
    signed_in.show_tab("mine")

    expect(signed_in.by("push-card")).to_have_count(0)


def test_a_no_from_the_browser_subscribes_nothing(ready, shop, account):
    shop.page.add_init_script(STUB.replace('ask: "granted"', 'ask: "denied"'))
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("mine")
    sent = sent_to(shop.page, "/push/subscribe")

    signed_in.by("push-on").click()
    signed_in.settled()

    assert sent == []
    expect(signed_in.by("push-card")).to_have_count(0)


def test_a_shop_without_a_key_pair_offers_nothing(shop, account):
    shop.page.add_init_script(STUB)
    shop.page.route(
        "**/push/key",
        lambda route: route.fulfill(
            status=404, content_type="application/json", body='{"detail":"x","code":"push_unavailable"}'
        ),
    )
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("mine")

    expect(signed_in.by("push-card")).to_have_count(0)


def test_a_barber_is_asked_in_the_wording_of_a_barber_and_gets_the_barbers_worker(ready, barbers, shop):
    barber = barbers.create_fake_barber()
    shop.page.add_init_script(STUB)
    shop.sign_in(barber["username"], barber["password"])

    card = shop.by("push-card")
    assert "בקשה חדשה" in shop.text(card.locator("h3"))
    shop.by("push-on").click()
    shop.settled()

    assert shop.page.evaluate("window.__push.registered") == "/sw.js?role=barber"


def test_on_an_iphone_that_is_not_installed_the_card_says_how_to_add_the_page_to_the_home_screen(
    ready, shop, account
):
    shop.page.add_init_script(
        "delete window.PushManager; delete window.Notification;"
        "Object.defineProperty(navigator, 'userAgent', {value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'});"
    )
    signed_in = shop.sign_in_as(account)
    signed_in.show_tab("mine")

    card = signed_in.by("push-card")

    expect(card).to_have_attribute("data-state", "install")
    assert "הוספה למסך הבית" in signed_in.text(card)


def test_the_service_worker_and_the_manifest_are_served_from_the_root(api):
    worker = api.request("GET", "/sw.js", persona=None)
    manifest = api.request("GET", "/manifest.webmanifest", persona=None)

    assert worker.status_code == 200 and "javascript" in worker.headers["content-type"]
    assert "showNotification" in worker.text and "no-cache" in worker.headers["cache-control"]
    assert manifest.status_code == 200
    body = manifest.as_dict
    assert (body["start_url"], body["display"], body["lang"], body["dir"]) == ("/", "standalone", "he", "rtl")
