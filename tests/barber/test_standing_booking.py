"""A standing booking: a customer's regular time, every two, three or four weeks, made from a booking
still to come. Only the next booking is held; the one after it is made by the shop once that one has
begun - which takes weeks, so here only what a customer can do at once is checked."""

from __future__ import annotations

from utils.assertions import assert_refused
from utils.local_time import at_local, local_day


def stand(api, booking_id, persona, every=3):
    return api.request(
        "POST", f"/bookings/{booking_id}/standing", persona=persona, json={"every_weeks": every}
    )


def test_a_booking_ahead_stands_every_three_weeks_and_says_so_in_the_list(
    api, barbers, bookings, haircut, new_customer, shop_tz
):
    barber, me = barbers.create_fake_barber(), new_customer()
    made = bookings.create_booking(barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 3), "10:00"), persona=me)

    stood = stand(api, made["id"], me).assert_ok(201).as_dict

    assert stood["standing"]["every_weeks"] == 3
    listed = {b["id"]: b for b in bookings.listing(persona=me)["content"]}
    assert listed[made["id"]]["standing"] == stood["standing"]
    assert_refused(stand(api, made["id"], me, every=2), 409, "already_standing")


def test_only_two_three_or_four_weeks_and_only_ones_own(api, barbers, bookings, haircut, new_customer, shop_tz):
    barber, me, other = barbers.create_fake_barber(), new_customer(), new_customer()
    made = bookings.create_booking(barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 3), "11:00"), persona=me)

    assert stand(api, made["id"], me, every=5).status_code == 422
    assert stand(api, made["id"], other).status_code == 404


def test_a_cancelled_booking_or_one_for_two_cannot_stand(api, barbers, bookings, haircut, new_customer, shop_tz):
    barber, me = barbers.create_fake_barber(), new_customer()
    day = local_day(shop_tz, 4)
    single = bookings.create_booking(barber["id"], haircut["id"], at_local(shop_tz, day, "09:00"), persona=me)
    bookings.cancel(single["id"], persona=me).assert_ok(200)
    first, _ = bookings.create_group(
        barber["id"],
        at_local(shop_tz, day, "12:00"),
        [{"service_id": haircut["id"]}, {"service_id": haircut["id"], "name": "יוני"}],
        persona=me,
    )

    assert_refused(stand(api, single["id"], me), 409, "standing_not_ahead")
    assert_refused(stand(api, first["id"], me), 409, "standing_group")


def test_stopping_keeps_the_booking_and_takes_the_standing_off_it(
    api, barbers, bookings, haircut, new_customer, shop_tz
):
    barber, me = barbers.create_fake_barber(), new_customer()
    made = bookings.create_booking(barber["id"], haircut["id"], at_local(shop_tz, local_day(shop_tz, 3), "12:00"), persona=me)
    standing = stand(api, made["id"], me).assert_ok(201).as_dict["standing"]

    api.request("POST", f"/standing/{standing['id']}/stop", persona=me).assert_ok(204)

    listed = {b["id"]: b for b in bookings.listing(persona=me)["content"]}
    assert listed[made["id"]]["status"] == "confirmed" and listed[made["id"]]["standing"] is None
    assert api.request("POST", f"/standing/{standing['id']}/stop", persona=new_customer()).status_code == 404
