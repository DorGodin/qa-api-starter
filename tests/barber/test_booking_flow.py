"""A customer books, sees it, and cancels - with every number checked."""

from datetime import timedelta

from utils.local_time import local_day, parse_instant


def test_a_customer_books_the_first_free_slot_and_it_is_theirs(
    barbers, bookings, barber, haircut, new_customer, shop_tz
):
    me = new_customer()
    day = local_day(shop_tz, 3)
    first = barbers.slots(barber["id"], day, haircut["id"], persona=me)[0]

    booking = bookings.create_booking(barber["id"], haircut["id"], first["start"], persona=me)

    start, end = parse_instant(booking["start"]), parse_instant(booking["end"])
    assert booking["status"] == "confirmed"
    assert booking["start"] == first["start"]
    assert end - start == timedelta(minutes=haircut["duration_minutes"])
    assert booking["price_minor"] == haircut["price_minor"] and booking["currency"] == haircut["currency"]
    assert parse_instant(booking["start_local"]) == start, "start_local must be the same instant as start"
    assert parse_instant(booking["start_local"]).utcoffset() == start.astimezone(shop_tz).utcoffset()
    assert [b["id"] for b in bookings.listing(persona=me)["content"]] == [booking["id"]]
    assert first["start"] not in [
        s["start"] for s in barbers.slots(barber["id"], day, haircut["id"], persona=me)
    ]


def test_cancelling_gives_the_slot_back(barbers, bookings, barber, haircut, new_customer, shop_tz):
    me = new_customer()
    day = local_day(shop_tz, 4)
    slot = barbers.slots(barber["id"], day, haircut["id"], persona=me)[5]["start"]
    booking = bookings.create_booking(barber["id"], haircut["id"], slot, persona=me)

    cancelled = bookings.cancel(booking["id"], persona=me).assert_ok(200).as_dict

    assert cancelled["status"] == "cancelled" and cancelled["cancelled_at"] is not None
    assert slot in [s["start"] for s in barbers.slots(barber["id"], day, haircut["id"], persona=me)]
    assert bookings.listing(persona=me, status="confirmed")["total"] == 0


def test_a_price_change_does_not_reach_back_into_a_booking(
    barbers, bookings, services, barber, new_customer, shop_tz
):
    service = services.create_fake_service(duration_minutes=30, price_minor=8000)
    me = new_customer()
    day = local_day(shop_tz, 5)
    slots = barbers.slots(barber["id"], day, service["id"], persona=me)
    before = bookings.create_booking(barber["id"], service["id"], slots[0]["start"], persona=me)

    services.set_price(service["id"], 9900)
    after = bookings.create_booking(barber["id"], service["id"], slots[4]["start"], persona=me)

    assert bookings.get_by_id(before["id"], persona=me).assert_ok(200).as_dict["price_minor"] == 8000
    assert after["price_minor"] == 9900


def test_the_owner_sees_every_booking_and_a_barber_only_their_own(
    barbers, bookings, barber, haircut, new_customer, shop_tz
):
    other = barbers.create_fake_barber()
    other_persona = barbers.sign_in_as_persona(other)
    day = local_day(shop_tz, 6)
    mine = bookings.create_booking(
        other["id"],
        haircut["id"],
        barbers.slots(other["id"], day, haircut["id"])[0]["start"],
        persona=new_customer(),
    )
    elsewhere = bookings.create_booking(
        barber["id"],
        haircut["id"],
        barbers.slots(barber["id"], day, haircut["id"])[0]["start"],
        persona=new_customer(),
    )

    seen_by_barber = {b["id"] for b in bookings.listing(persona=other_persona, limit=100)["content"]}
    seen_by_owner = {
        b["id"] for b in bookings.listing(persona="owner", barber_id=other["id"], limit=100)["content"]
    }

    assert seen_by_barber == {mine["id"]}
    assert elsewhere["id"] not in seen_by_barber
    assert mine["id"] in seen_by_owner
