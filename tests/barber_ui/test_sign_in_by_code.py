"""Signing in with a code on the page: name and phone, then the four digits
from the SMS - read from the fake provider's inbox, as from a phone."""

from playwright.sync_api import expect

from obj.barber.customers import Customers
from tests.barber_ui.test_booking_page_accessibility import violations


def to_code_screen(shop, inbox, name="דנה כהן", phone=None):
    phone = phone or Customers.new_phone()
    seen = inbox.last_id(phone)
    shop.open()
    shop.by("full-name").fill(name)
    # Typed the way people type it; the page and the server read it anyway.
    shop.by("phone").fill(f"{phone[:3]}-{phone[3:6]}-{phone[6:]}")
    shop.by("send-code").click()
    expect(shop.by("code-form")).to_be_visible()
    return phone, inbox.code_for(phone, after=seen)


def wrong(code: str) -> str:
    return f"{(int(code) + 1) % 10_000:04d}"


def test_a_first_sign_in_by_code_opens_the_account_under_the_name_given(shop, sms_inbox):
    phone, code = to_code_screen(shop, sms_inbox, name="יעל לוי")

    sent_to = shop.text(shop.by("code-sent-to"))
    assert phone[-4:] in sent_to and phone not in sent_to and phone[:3] not in sent_to, sent_to
    expect(shop.by("code")).to_be_focused()
    shop.by("code").fill(code)

    expect(shop.by("app")).to_be_visible()
    expect(shop.by("display-name")).to_contain_text("יעל לוי")


def test_a_wrong_code_says_how_many_tries_are_left_and_locks_the_button_until_a_digit_changes(
    shop, sms_inbox
):
    _, code = to_code_screen(shop, sms_inbox)

    shop.by("code").fill(wrong(code))

    expect(shop.by("code-error")).to_contain_text("נשארו 2 ניסיונות")
    expect(shop.by("code")).to_have_attribute("aria-invalid", "true")
    borders = shop.page.locator(".code-boxes span").evaluate_all(
        "bs => bs.map(b => getComputedStyle(b).borderTopColor)"
    )
    assert len(set(borders)) == 1, f"after a wrong code every box is red, the next one included: {borders}"
    expect(shop.by("verify-code")).to_be_disabled()
    expect(shop.by("code-locked-hint")).to_be_visible()
    shop.by("code").press("Backspace")
    expect(shop.by("verify-code")).to_be_enabled()
    expect(shop.by("code-locked-hint")).to_be_hidden()


def test_after_the_third_wrong_code_the_button_stays_locked_until_a_new_code(shop, sms_inbox):
    _, code = to_code_screen(shop, sms_inbox)

    # Three different wrong codes: the same refused one is not even sent again.
    for step in (1, 2, 3):
        shop.by("code").fill("")
        shop.by("code").fill(f"{(int(code) + step) % 10_000:04d}")
        shop.settled()

    expect(shop.by("code-error")).to_contain_text("קוד חדש")
    shop.by("code").fill(code[:3])
    expect(shop.by("verify-code")).to_be_disabled()


def test_a_new_code_is_offered_only_after_the_countdown(shop, sms_inbox):
    to_code_screen(shop, sms_inbox)

    expect(shop.by("resend-code")).to_be_disabled()
    expect(shop.by("resend-wait")).to_contain_text("אפשר בעוד")


def test_changing_the_number_goes_back_with_what_was_typed(shop, sms_inbox):
    to_code_screen(shop, sms_inbox, name="רון כץ")

    shop.by("change-phone").click()

    expect(shop.by("code-request-form")).to_be_visible()
    expect(shop.by("full-name")).to_have_value("רון כץ")
    expect(shop.by("phone")).to_be_focused()


def test_a_number_that_is_not_a_mobile_is_explained_in_hebrew(shop):
    shop.open()
    shop.by("full-name").fill("דנה כהן")
    shop.by("phone").fill("031234567")
    shop.by("send-code").click()

    expect(shop.by("code-request-error")).to_contain_text("05 ועוד 8 ספרות")
    expect(shop.by("code-form")).to_be_hidden()


def test_the_code_field_lets_the_phone_fill_it_from_the_sms(shop, sms_inbox):
    to_code_screen(shop, sms_inbox)

    expect(shop.by("code")).to_have_attribute("autocomplete", "one-time-code")
    expect(shop.by("code")).to_have_attribute("inputmode", "numeric")


def test_the_code_screen_meets_wcag_2_2_aa_and_so_does_a_wrong_code(shop, sms_inbox):
    _, code = to_code_screen(shop, sms_inbox)
    assert violations(shop.page) == [], "the code screen"

    shop.by("code").fill(wrong(code))
    expect(shop.by("code-error")).to_be_visible()
    assert violations(shop.page) == [], "the code screen after a wrong code"


def test_the_code_screen_offers_no_password_sign_in_and_changing_the_number_brings_it_back(shop, sms_inbox):
    to_code_screen(shop, sms_inbox)

    expect(shop.by("password-sign-in")).to_be_hidden()
    shop.by("change-phone").click()
    expect(shop.by("password-sign-in")).to_be_visible()


def test_a_cursor_blinks_in_the_box_the_next_digit_goes_to(shop, sms_inbox):
    to_code_screen(shop, sms_inbox)
    shop.by("code").press_sequentially("12")

    caret = (
        shop.page.locator(".code-boxes span")
        .nth(2)
        .evaluate(
            "b => { const a = getComputedStyle(b, '::after'); return [a.content, a.width, a.animationName]; }"
        )
    )

    assert caret == ['""', "2px", "caret"], f"no blinking cursor in the third box: {caret}"
