"""The shop's header: its brand and the ways to reach it, as the shop's settings
give them - checked against what the shop's own /shop says, so it holds with
every link set or none."""

import requests
from playwright.sync_api import expect

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

    for decoration in (".pole.right", ".pole.left", ".cut"):
        expect(shop.page.locator(decoration)).to_have_attribute("aria-hidden", "true")


def test_the_poles_stand_still_for_whoever_asked_for_less_motion(browser, env_config):
    context = browser.new_context(reduced_motion="reduce")
    page = context.new_page()
    page.goto(env_config["url"].rstrip("/") + "/")
    try:
        animation = page.locator(".pole.right").evaluate("e => getComputedStyle(e).animationName")
        assert animation == "none", animation
    finally:
        context.close()
