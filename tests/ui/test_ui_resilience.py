"""What the user sees when the API misbehaves.

Intercepting the network is the only way to test this: you cannot ask a healthy
server to fail on demand, and a UI that shows a blank page on a 500 is a defect
even when the API is fixed the same day.
"""

from playwright.sync_api import expect


def test_a_failing_catalogue_does_not_leave_a_blank_page(page, ui_base_url, signed_in, items):
    items.create_fake_item(name="Lamp", price=20.0)
    page = signed_in("member")

    page.route("**/items*", lambda route: route.fulfill(status=500, json={"detail": "boom"}))
    page.reload()
    page.get_by_test_id("username").fill("member")
    page.get_by_test_id("password").fill("member-secret")
    page.get_by_test_id("login").click()

    expect(page.get_by_test_id("budget")).to_be_visible()
    expect(page.get_by_test_id("empty-catalogue")).to_be_visible()


def test_a_slow_response_does_not_lose_the_order(page, signed_in, items):
    items.create_fake_item(name="Chair", price=15.0)
    page = signed_in("member")

    page.route("**/orders", lambda route: (page.wait_for_timeout(800), route.continue_())[-1])
    page.get_by_test_id("item-row").filter(has_text="Chair").get_by_test_id("order").click()

    expect(page.get_by_test_id("order-row")).to_have_count(1, timeout=5000)


def test_a_rejected_submit_keeps_the_order_visible_and_explains_itself(page, signed_in, items):
    items.create_fake_item(name="Rack", price=9000.0)
    page = signed_in("member")

    page.get_by_test_id("item-row").filter(has_text="Rack").get_by_test_id("order").click()
    page.get_by_test_id("order-row").last.get_by_test_id("submit").click()

    expect(page.get_by_test_id("order-error")).to_be_visible()
    (
        expect(page.get_by_test_id("order-row")).to_have_count(1),
        "the order must not vanish because it was refused",
    )


def test_the_error_message_clears_once_the_next_action_succeeds(page, signed_in, items):
    items.create_fake_item(name="Rack", price=9000.0)
    items.create_fake_item(name="Pen", price=3.0)
    page = signed_in("member")

    page.get_by_test_id("item-row").filter(has_text="Rack").get_by_test_id("order").click()
    page.get_by_test_id("order-row").last.get_by_test_id("submit").click()
    expect(page.get_by_test_id("order-error")).to_be_visible()

    page.get_by_test_id("item-row").filter(has_text="Pen").get_by_test_id("order").click()
    page.get_by_test_id("order-row").last.get_by_test_id("submit").click()
    expect(page.get_by_test_id("order-error")).to_be_hidden(), "a stale error is worse than no error"


def test_reloading_signs_the_user_out_rather_than_showing_a_half_logged_in_page(page, signed_in):
    page = signed_in("member")
    expect(page.get_by_test_id("budget")).to_be_visible()

    page.reload()

    expect(page.get_by_test_id("login")).to_be_visible()
    expect(page.get_by_test_id("budget")).to_be_hidden()
