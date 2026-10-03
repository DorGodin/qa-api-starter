"""Signing in with a code by SMS, from outside: the code is read from the fake
provider's inbox, as a person reads it off their phone."""

from concurrent.futures import ThreadPoolExecutor

from obj.barber.customers import new_device_address
from utils.assertions import assert_refused


def wrong(code: str) -> str:
    return f"{(int(code) + 1) % 10_000:04d}"


def test_the_first_sign_in_opens_the_account_and_shows_only_the_last_four_digits(customers, sms_inbox, api):
    phone = customers.new_phone()
    seen = sms_inbox.last_id(phone)

    asked = customers.request_code(phone, "דנה כהן").assert_ok(202).as_dict
    code = sms_inbox.code_for(phone, after=seen)
    signed_in = customers.verify_code(phone, code).assert_ok(200).as_dict

    assert asked["phone_last4"] == phone[-4:] and phone not in str(asked), "the full number came back"
    assert code not in str(asked), "the code came back in the answer"
    assert "TomGoldin" in sms_inbox.messages(phone)[-1]["text"]
    api.register_persona_headers("by-code", {"Authorization": f"Bearer {signed_in['access_token']}"})
    me = api.request("GET", "/me", persona="by-code").assert_ok(200).as_dict
    assert (me["display_name"], me["role"]) == ("דנה כהן", "customer")


def test_the_same_phone_however_it_is_typed_is_the_same_account(customers, sms_inbox, api):
    first = customers.sign_in_by_code(sms_inbox)
    typed = "+972 " + first["phone"][1:3] + "-" + first["phone"][3:]

    again = api.request("GET", "/me", persona=first["persona"]).assert_ok(200).as_dict
    refused_soon = customers.request_code(typed, "שם אחר")

    # A minute between codes to one phone - so the second form of the number
    # is checked by its refusal: it is the same phone, already sent a code.
    assert_refused(refused_soon, 429, "code_too_soon")
    assert 0 < refused_soon.as_dict["retry_after_seconds"] <= 60
    assert again["display_name"] == first["name"]


def test_wrong_codes_count_down_and_the_third_uses_the_code_up(customers, sms_inbox):
    phone = customers.new_phone()
    seen = sms_inbox.last_id(phone)
    customers.request_code(phone, "יעל לוי").assert_ok(202)
    code = sms_inbox.code_for(phone, after=seen)

    lefts = [customers.verify_code(phone, wrong(code)).as_dict["attempts_left"] for _ in range(3)]

    assert lefts == [2, 1, 0]
    assert_refused(customers.verify_code(phone, code), 409, "code_used_up")


def test_a_code_signs_in_once(customers, sms_inbox):
    phone = customers.new_phone()
    seen = sms_inbox.last_id(phone)
    customers.request_code(phone, "רון כץ").assert_ok(202)
    code = sms_inbox.code_for(phone, after=seen)

    customers.verify_code(phone, code).assert_ok(200)

    assert_refused(customers.verify_code(phone, code), 409, "no_code")


def test_the_same_code_sent_six_times_at_once_signs_in_exactly_once(customers, sms_inbox):
    phone = customers.new_phone()
    seen = sms_inbox.last_id(phone)
    customers.request_code(phone, "מרוץ").assert_ok(202)
    code = sms_inbox.code_for(phone, after=seen)

    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = sorted(pool.map(lambda _: customers.verify_code(phone, code).status_code, range(6)))

    assert [c for c in codes if c >= 500] == [], f"the losers crashed instead of being refused: {codes}"
    assert codes.count(200) == 1, f"one code signed in more than once: {codes}"


def test_one_address_gets_only_so_many_codes_an_hour(customers):
    address = new_device_address()

    answers = [customers.request_code(customers.new_phone(), "כתובת אחת", address=address) for _ in range(21)]

    assert [a.status_code for a in answers[:20]] == [202] * 20
    assert_refused(answers[20], 429, "too_many_codes")


def test_only_a_mobile_number_gets_a_code(customers):
    for phone in ("12345", "0721234567", "05012345678"):
        assert_refused(customers.request_code(phone, "דנה כהן"), 422, "bad_phone")
