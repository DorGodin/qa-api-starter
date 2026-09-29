import re

import pytest
from playwright.sync_api import expect


def test_sign_in_shows_the_signed_in_identity(signed_in):
    page = signed_in("member")
    expect(page.get_by_test_id("whoami")).to_contain_text("member")
    expect(page.get_by_test_id("login-error")).to_be_hidden()


def test_bad_password_keeps_the_user_out(page, ui_base_url):
    page.goto(ui_base_url)
    page.get_by_test_id("username").fill("member")
    page.get_by_test_id("password").fill("wrong")
    page.get_by_test_id("login").click()

    expect(page.get_by_test_id("login-error")).to_be_visible()
    expect(page.get_by_test_id("budget")).to_be_hidden()


def test_catalogue_shows_the_seeded_item(items, signed_in):
    items.create_fake_item(name="Desk Lamp", price=42.0)
    page = signed_in("member")

    row = page.get_by_test_id("item-row").filter(has_text="Desk Lamp")
    expect(row.get_by_test_id("item-price")).to_have_text("42.00")


def test_ordering_from_the_ui_creates_a_draft_with_the_right_total(items, signed_in):
    items.create_fake_item(name="Notebook", price=12.50)
    page = signed_in("member")

    row = page.get_by_test_id("item-row").filter(has_text="Notebook")
    row.get_by_test_id("qty").fill("4")
    row.get_by_test_id("order").click()

    order = page.get_by_test_id("order-row").last
    expect(order.get_by_test_id("order-total")).to_have_text("50.00")
    expect(order.get_by_test_id("order-status")).to_have_text("draft")


def test_submitting_draws_the_budget_down_on_screen(items, signed_in):
    items.create_fake_item(name="Chair", price=100.0)
    page = signed_in("member")
    before = float(page.get_by_test_id("budget").inner_text())

    page.get_by_test_id("item-row").filter(has_text="Chair").get_by_test_id("order").click()
    page.get_by_test_id("order-row").last.get_by_test_id("submit").click()

    expect(page.get_by_test_id("order-row").last.get_by_test_id("order-status")).to_have_text("submitted")
    expect(page.get_by_test_id("budget")).to_have_text(f"{before - 100.0:.2f}")


def test_an_order_over_budget_shows_a_message_a_user_can_understand(items, signed_in):
    items.create_fake_item(name="Server Rack", price=5000.0)
    page = signed_in("member")

    page.get_by_test_id("item-row").filter(has_text="Server Rack").get_by_test_id("order").click()
    page.get_by_test_id("order-row").last.get_by_test_id("submit").click()

    error = page.get_by_test_id("order-error")
    expect(error).to_be_visible()
    expect(error).to_have_text(re.compile("budget", re.I))
    expect(page.get_by_test_id("order-row").last.get_by_test_id("order-status")).to_have_text("draft")


def test_empty_catalogue_says_so_instead_of_showing_a_blank_table(signed_in):
    page = signed_in("member")
    expect(page.get_by_test_id("empty-catalogue")).to_be_visible()
