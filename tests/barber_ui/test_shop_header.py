"""The shop's header: its brand and the ways to reach it, as the shop's settings
give them - checked against what the shop's own /shop says, so it holds with
every link set or none."""

import requests
from playwright.sync_api import expect

from tests.barber_ui.test_booking_page_accessibility import violations

NAMES = {
    "whatsapp": "וואטסאפ",
    "phone": "התקשרות",
    "instagram": "אינסטגרם",
    "tiktok": "טיקטוק",
    "waze": "ניווט ב־Waze",
}


def shop_info(env_config) -> dict:
    resp = requests.get(env_config["url"].rstrip("/") + "/shop", timeout=10)
    resp.raise_for_status()
    return resp.json()


def test_the_brand_names_the_page_and_its_tab(shop, env_config):
    info = shop_info(env_config)

    shop.open()

    expect(shop.by("shop-brand")).to_have_text(info["brand"])
    assert shop.page.title().startswith(info["brand"])
    if info["under_brand"]:
        expect(shop.by("shop-line")).to_have_text(info["under_brand"])


def test_every_way_to_reach_the_shop_is_a_named_button_and_nothing_else_is(shop, env_config):
    links = shop_info(env_config)["links"]

    shop.open()

    for kind, name in NAMES.items():
        button = shop.by(f"shop-{kind}")
        if kind in links:
            expect(button).to_have_attribute("href", links[kind])
            expect(button).to_have_accessible_name(name)
        else:
            expect(button).to_have_count(0)


def test_the_poles_and_the_scissors_are_decoration_a_screen_reader_never_meets(shop):
    shop.open()

    for decoration in (".pole.right", ".pole.left", ".cut", '[data-testid="legal-scissors"]'):
        found = shop.page.locator(decoration)
        assert found.count() >= 1, decoration
        for i in range(found.count()):
            expect(found.nth(i)).to_have_attribute("aria-hidden", "true")


def test_the_poles_stand_still_for_whoever_asked_for_less_motion(browser, env_config):
    context = browser.new_context(reduced_motion="reduce")
    page = context.new_page()
    page.goto(env_config["url"].rstrip("/") + "/")
    try:
        animation = page.locator(".pole.right").evaluate("e => getComputedStyle(e).animationName")
        assert animation == "none", animation
    finally:
        context.close()


def test_the_privacy_policy_is_one_step_from_the_sign_in_screen(shop):
    shop.open()

    shop.by("privacy-link").click()

    expect(shop.page.get_by_role("heading", level=1)).to_have_text("מדיניות פרטיות")
    expect(shop.page.get_by_text("חוק הגנת הפרטיות")).to_be_visible()
    assert "{{" not in shop.page.content(), "a placeholder was left on the privacy policy"
    assert violations(shop.page) == [], "the privacy policy"


def test_the_ways_to_reach_the_shop_come_after_the_sign_in_not_before_it(shop, env_config):
    if not shop_info(env_config)["links"]:
        return
    shop.open()

    first_button = shop.page.locator("footer .action").first
    form_bottom = shop.by("code-request-form").bounding_box()
    assert first_button.bounding_box()["y"] > form_bottom["y"] + form_bottom["height"]


def test_the_statement_and_the_policy_end_like_every_screen(shop, env_config):
    base = env_config["url"].rstrip("/")
    for path in ("/accessibility", "/privacy"):
        shop.page.goto(base + path)

        cuts = shop.page.locator(".cut")
        assert cuts.count() == 2, f"{path}: a cut line above the content and one at its foot"
        for i in range(2):
            expect(cuts.nth(i)).to_have_attribute("aria-hidden", "true")
        expect(shop.by("accessibility-link")).to_have_attribute("href", "/accessibility")
        expect(shop.by("privacy-link")).to_have_attribute("href", "/privacy")
        expect(shop.by("legal-scissors")).to_have_attribute("aria-hidden", "true")
        assert violations(shop.page) == [], path
