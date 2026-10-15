"""A customer deletes their own account through the API: what was theirs goes, what the shop needs stays.

A booking that is over cannot be made from outside, so how the past keeps its place in the diary, the
note, and the codes are the product's own tests (tests/test_delete_account.py)."""

from __future__ import annotations

from utils.assertions import assert_refused
from utils.local_time import at_local, local_day


def delete_me(api, persona):
    return api.request("DELETE", "/me", persona=persona)


def test_a_customer_deletes_their_account_and_what_is_ahead_is_cancelled_for_the_shop(
    api, customers, sms_inbox, bookings, barbers, haircut, shop_tz
):
    who = customers.sign_in_by_code(sms_inbox, full_name="רותם בדיקה")
    barber = barbers.create_fake_barber()
    ahead = bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 5), "10:00"), persona=who["persona"]
    )

    assert delete_me(api, who["persona"]).status_code == 204

    assert api.request("GET", "/me", persona=who["persona"]).status_code == 401
    seen = bookings.get_by_id(ahead["id"], persona="owner").as_dict
    assert (seen["status"], seen["cancelled_by"], seen["customer_deleted"], seen["customer_name"]) == (
        "cancelled",
        "customer",
        True,
        None,
    )
    assert_refused(
        api.request("GET", f"/customers/{ahead['customer_id']}/card", persona="owner"), 404, "not_found"
    )


def test_the_same_phone_signs_up_again_as_someone_new(customers, sms_inbox, api):
    first = customers.sign_in_by_code(sms_inbox, full_name="אורי")
    old = api.request("GET", "/me", persona=first["persona"]).as_dict
    delete_me(api, first["persona"])

    again = customers.sign_in_by_code(sms_inbox, full_name="אורי שוב", phone=first["phone"])
    new = api.request("GET", "/me", persona=again["persona"]).as_dict

    assert new["id"] != old["id"] and (new["display_name"], new["phone"]) == ("אורי שוב", first["phone"])


def test_only_a_customer_deletes_an_account_and_only_their_own(api, barbers):
    barber = barbers.create_fake_barber()

    assert_refused(delete_me(api, "owner"), 403, "forbidden")
    assert_refused(delete_me(api, barbers.sign_in_as_persona(barber)), 403, "forbidden")
    assert delete_me(api, None).status_code == 401
