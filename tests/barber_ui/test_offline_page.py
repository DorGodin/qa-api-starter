"""The shop on a home screen with no connection: the worker answers with the shop's own page, not the phone's
error, and the shop comes back when the connection does."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect


@pytest.fixture
def chromium_only(browser_name):
    if browser_name == "webkit":
        pytest.skip(
            "Playwright's WebKit, set offline, fails the navigation before the page's worker sees it - the "
            "browser's own shortcut, not Safari's: on an iPhone the worker answers (checked on the simulator)"
        )


def test_with_no_connection_the_shop_shows_its_own_page(chromium_only, shop):
    shop.open().kept_for_no_connection()
    shop.page.context.set_offline(True)

    shop.page.goto(shop.base_url + "/")

    expect(shop.by("offline")).to_contain_text("אין חיבור כרגע")
    expect(shop.by("offline")).to_contain_text("TomGoldin")
    expect(shop.by("offline-retry")).to_be_visible()


def test_the_shop_opens_by_itself_when_the_connection_comes_back(chromium_only, shop):
    shop.open().kept_for_no_connection()
    shop.page.context.set_offline(True)
    shop.page.goto(shop.base_url + "/")
    expect(shop.by("offline")).to_be_visible()

    shop.page.context.set_offline(False)

    expect(shop.by("code-request-form")).to_be_visible()
