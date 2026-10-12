"""The products tab: the shop's shelf as cards. A customer with a booking ahead asks for a product
to be kept for it, and the booking says so - in their list and in the barber's diary. And the
owner's panel that keeps the shelf."""

import secrets

import pytest
from playwright.sync_api import expect

from obj.barber.courses import PNG_1X1
from utils.local_time import at_local, local_day


@pytest.fixture
def product(products):
    return products.create_fake_product(name=f"ווקס {secrets.token_hex(3)}", line="100 מ״ל", price_minor=6500)


@pytest.fixture
def ahead(account, bookings, barbers, ui_haircut, shop_tz):
    barber = barbers.create_fake_barber()
    start = at_local(shop_tz, local_day(shop_tz, 6), "11:00")
    return bookings.create_booking(barber["id"], ui_haircut["id"], start, persona=account["persona"])


def test_a_customer_sees_a_product_as_a_card_with_its_line_and_price(product, signed_in):
    card = signed_in.product_card(product["id"])

    assert product["name"] in signed_in.text(card.get_by_test_id("product-name"))
    line = signed_in.text(card.get_by_test_id("product-line"))
    assert "100 מ״ל" in line and "65" in line and ".00" not in line, line


def test_without_a_booking_ahead_there_is_nothing_to_keep_a_product_for(product, signed_in):
    card = signed_in.product_card(product["id"])

    expect(card).to_be_visible()
    expect(card.get_by_test_id("product-keep")).to_have_count(0)
    expect(signed_in.by("products-for")).to_be_hidden()


def test_with_a_booking_ahead_the_tab_says_which_booking_the_product_waits_for(product, ahead, signed_in):
    card = signed_in.product_card(product["id"])

    expect(card.get_by_test_id("product-keep")).to_have_text("שמור לי לתור")
    expect(signed_in.by("products-for")).to_be_visible()
    words = signed_in.text(signed_in.by("products-for"))
    assert "11:00" in words and "התשלום במספרה" in words, words


def test_keeping_a_product_writes_it_beside_the_booking_and_tells_the_shop(
    product, ahead, signed_in, bookings, account
):
    signed_in.keep_product(product["id"])

    assert product["name"] in signed_in.text(signed_in.message())
    expect(signed_in.product_card(product["id"]).get_by_test_id("product-release")).to_be_visible()
    expect(signed_in.product_card(product["id"]).get_by_test_id("product-keep")).to_have_count(0)
    stored = bookings.get_by_id(ahead["id"], persona=account["persona"]).as_dict["products"]
    assert stored == [{"id": product["id"], "name": product["name"]}]
    signed_in.show_tab("mine")
    kept = signed_in.text(signed_in.row_at("11:00").get_by_test_id("booking-products"))
    assert kept.startswith("שמור לתור:") and product["name"] in kept, kept


def test_a_kept_product_is_given_back_and_the_booking_no_longer_names_it(
    product, ahead, signed_in, products, bookings, account
):
    products.keep(ahead["id"], product["id"], persona=account["persona"]).assert_ok(200)
    signed_in.reload()

    signed_in.release_product(product["id"])

    expect(signed_in.product_card(product["id"]).get_by_test_id("product-keep")).to_be_visible()
    assert bookings.get_by_id(ahead["id"], persona=account["persona"]).as_dict["products"] == []
    signed_in.show_tab("mine")
    expect(signed_in.row_at("11:00").get_by_test_id("booking-products")).to_have_count(0)


def test_the_product_waits_for_the_nearest_booking(product, ahead, signed_in, bookings, account, shop_tz):
    sooner = bookings.create_booking(
        ahead["barber_id"],
        ahead["service_id"],
        at_local(shop_tz, local_day(shop_tz, 4), "09:00"),
        persona=account["persona"],
    )
    signed_in.reload()

    signed_in.keep_product(product["id"])

    assert [
        p["id"] for p in bookings.get_by_id(sooner["id"], persona=account["persona"]).as_dict["products"]
    ] == [product["id"]]
    assert bookings.get_by_id(ahead["id"], persona=account["persona"]).as_dict["products"] == []


def test_a_product_that_ran_out_says_so_and_cannot_be_kept(product, ahead, products, signed_in):
    products.run_out(product["id"])
    signed_in.reload()

    card = signed_in.product_card(product["id"])

    expect(card.get_by_test_id("product-out")).to_have_text("אזל מהמלאי")
    expect(card.get_by_test_id("product-keep")).to_have_count(0)


def test_what_is_already_kept_can_be_given_back_after_it_ran_out(
    product, ahead, products, signed_in, account
):
    products.keep(ahead["id"], product["id"], persona=account["persona"]).assert_ok(200)
    products.run_out(product["id"])
    signed_in.reload()

    signed_in.release_product(product["id"])

    expect(signed_in.product_card(product["id"]).get_by_test_id("product-out")).to_be_visible()


def test_a_cancelled_booking_is_nothing_to_keep_a_product_for(product, ahead, bookings, signed_in, account):
    bookings.cancel(ahead["id"], persona=account["persona"]).assert_ok(200)
    signed_in.reload()

    expect(signed_in.product_card(product["id"]).get_by_test_id("product-keep")).to_have_count(0)


def test_a_withdrawn_product_is_not_shown(product, products, signed_in):
    products.withdraw(product["id"])
    signed_in.reload()

    expect(signed_in.product_card(product["id"])).to_have_count(0)


def test_a_name_that_looks_like_a_tag_is_written_as_text(products, ahead, signed_in, account):
    hostile = products.create_fake_product(name='<img src=x onerror="document.title=1">')
    products.keep(ahead["id"], hostile["id"], persona=account["persona"]).assert_ok(200)
    signed_in.reload()

    assert "<img" in signed_in.text(signed_in.product_card(hostile["id"]).get_by_test_id("product-name"))
    signed_in.show_tab("mine")
    assert "<img" in signed_in.text(signed_in.row_at("11:00").get_by_test_id("booking-products"))
    assert signed_in.page.title() != "1"


def test_the_picture_is_over_the_words(product, products, signed_in):
    url = products.set_image(product["id"], PNG_1X1).assert_ok(200).as_dict["image_url"]
    signed_in.reload()

    expect(signed_in.product_card(product["id"]).locator("img")).to_have_attribute("src", url)


def test_with_nothing_on_the_shelf_the_tab_says_so(signed_in):
    signed_in.page.route(
        "**/products",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body='{"total":0,"content":[]}'
        ),
    )
    signed_in.reload()
    signed_in.show_tab("products")

    expect(signed_in.by("no-products")).to_be_visible()
    expect(signed_in.by("product")).to_have_count(0)


def test_the_barbers_diary_and_the_owners_say_what_to_have_ready(
    product, ahead, products, barbers, account, owner_screen, page, env_config
):
    products.keep(ahead["id"], product["id"], persona=account["persona"]).assert_ok(200)

    owner = owner_screen().select_barber(ahead["barber_id"])

    assert product["name"] in owner.text(owner.row_at("11:00").get_by_test_id("booking-products"))


def test_the_owner_has_no_customers_shelf_but_a_panel_of_his_own(owner_screen):
    owner = owner_screen()

    expect(owner.by("products-panel")).to_be_hidden()
    expect(owner.by("products-admin-panel")).to_be_visible()


def test_the_owner_puts_a_product_on_the_shelf(owner_screen, products):
    owner, name = owner_screen(), f"שמן {secrets.token_hex(3)}"

    owner.add_product(name, "30 מ״ל", "80")

    assert "נוסף" in owner.text(owner.message())
    made = next(p for p in products.listing("owner") if p["name"] == name)
    products.withdraw(made["id"])
    assert (made["line"], made["price_minor"], made["in_stock"]) == ("30 מ״ל", 8000, True)


@pytest.mark.parametrize(
    ("name", "price", "word"), [("", "80", "שם"), ("שמן", "abc", "מחיר"), ("שמן", "", "מחיר")]
)
def test_a_new_product_needs_a_name_and_a_price(owner_screen, products, name, price, word):
    owner = owner_screen()
    before = len(products.listing("owner"))

    owner.add_product(name, "", price)

    assert word in owner.text(owner.message())
    assert len(products.listing("owner")) == before


def test_the_owner_reprices_a_product_and_marks_it_run_out(product, products, owner_screen, new_customer):
    owner = owner_screen()
    editor = owner.product_editor(product["id"])

    editor.get_by_test_id("product-edit-price").fill("72.50")
    editor.get_by_test_id("product-edit-stock").uncheck()
    owner.save_product(product["id"])

    saved = products.one(product["id"], persona=new_customer())
    assert (saved["price_minor"], saved["in_stock"], saved["active"]) == (7250, False, True)


def test_the_owner_takes_a_product_off_the_shelf(product, products, owner_screen, new_customer):
    owner = owner_screen()

    owner.product_editor(product["id"]).get_by_test_id("product-edit-active").uncheck()
    owner.save_product(product["id"])

    assert product["id"] not in [p["id"] for p in products.listing(new_customer())]
    assert products.one(product["id"])["active"] is False


def test_the_owner_uploads_and_removes_a_picture(product, products, owner_screen):
    owner = owner_screen()

    owner.product_editor(product["id"]).get_by_test_id("product-image").set_input_files(
        files=[{"name": "p.png", "mimeType": "image/png", "buffer": PNG_1X1}]
    )
    owner.settled()

    assert products.one(product["id"])["image_url"] is not None
    owner.product_editor(product["id"]).get_by_test_id("remove-product-image").click()
    owner.settled()
    assert products.one(product["id"])["image_url"] is None


def test_a_barber_sees_what_is_kept_and_has_no_shelf(product, ahead, products, barbers, account, shop):
    products.keep(ahead["id"], product["id"], persona=account["persona"]).assert_ok(200)
    barber = barbers.create_fake_barber()
    screen = shop.sign_in(barber["username"], barber["password"])

    expect(screen.by("products-panel")).to_be_hidden()
    expect(screen.by("tabbar")).to_be_hidden()
