"""Moving a booking: the same booking, barber, service and price at another
time - until MOVE_CUTOFF_HOURS before it, for the customer."""

from datetime import timedelta

from utils.assertions import assert_refused
from utils.helpers import now_utc, to_iso
from utils.local_time import at_local, local_day, parse_instant


def quarter_hour_from_now(hours: float) -> str:
    t = now_utc() + timedelta(hours=hours)
    return to_iso(t.replace(second=0, microsecond=0) + timedelta(minutes=15 - t.minute % 15))


def test_a_move_is_the_same_booking_at_the_new_time_and_frees_the_old_one(
    barbers, bookings, barber, haircut, new_customer, shop_tz
):
    me = new_customer()
    day = local_day(shop_tz, 5)
    booking = bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, day, "11:00"), persona=me
    )

    moved = bookings.move(booking["id"], at_local(shop_tz, day, "15:00"), persona=me).assert_ok(200).as_dict

    assert moved["id"] == booking["id"]
    assert parse_instant(moved["start"]) == at_local(shop_tz, day, "15:00")
    assert parse_instant(moved["end"]) - parse_instant(moved["start"]) == timedelta(minutes=30)
    assert (moved["barber_id"], moved["service_id"], moved["price_minor"]) == (
        booking["barber_id"],
        booking["service_id"],
        booking["price_minor"],
    )
    free = [parse_instant(s["start"]) for s in barbers.slots(barber["id"], day, haircut["id"], persona=me)]
    assert at_local(shop_tz, day, "11:00") in free
    assert at_local(shop_tz, day, "15:00") not in free
    assert bookings.listing(persona=me)["total"] == 1


def test_a_move_to_a_taken_time_is_refused_and_the_booking_stays(
    bookings, barber, haircut, new_customer, shop_tz
):
    me, other = new_customer(), new_customer()
    day = local_day(shop_tz, 5)
    booking = bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, day, "12:00"), persona=me
    )
    bookings.create_booking(barber["id"], haircut["id"], at_local(shop_tz, day, "16:00"), persona=other)

    assert_refused(
        bookings.move(booking["id"], at_local(shop_tz, day, "16:00"), persona=me), 409, "slot_taken"
    )
    kept = bookings.get_by_id(booking["id"], persona=me).assert_ok(200).as_dict
    assert parse_instant(kept["start"]) == at_local(shop_tz, day, "12:00")
    assert kept["status"] == "confirmed"


def test_the_listing_for_a_move_offers_its_own_time_and_the_move_accepts_it(
    barbers, bookings, barber, haircut, new_customer, shop_tz
):
    me = new_customer()
    day = local_day(shop_tz, 6)
    booking = bookings.create_booking(
        barber["id"], haircut["id"], at_local(shop_tz, day, "13:00"), persona=me
    )
    quarter_later = at_local(shop_tz, day, "13:15")

    offered = barbers.availability(barber["id"], day, haircut["id"], persona=me, moving=booking["id"])

    assert quarter_later in [parse_instant(s["start"]) for s in offered.assert_ok(200).as_dict["slots"]]
    assert quarter_later not in [
        parse_instant(s["start"]) for s in barbers.slots(barber["id"], day, haircut["id"], persona=me)
    ], "without moving=, a 13:15 haircut overlaps the 13:00 one"
    bookings.move(booking["id"], quarter_later, persona=me).assert_ok(200)


def test_inside_the_move_cutoff_only_the_owner_can_move(bookings, barber, trim, new_customer):
    me = new_customer()
    booking = bookings.create_booking(barber["id"], trim["id"], quarter_hour_from_now(2), persona=me)

    assert_refused(bookings.move(booking["id"], quarter_hour_from_now(40), persona=me), 409, "late_move")
    bookings.move(booking["id"], quarter_hour_from_now(40), persona="owner").assert_ok(200)


def test_a_barber_cannot_move_and_a_stranger_does_not_find_it(
    barbers, bookings, haircut, new_customer, shop_tz
):
    own = barbers.create_fake_barber()
    day = local_day(shop_tz, 5)
    me, stranger = new_customer(), new_customer()
    booking = bookings.create_booking(own["id"], haircut["id"], at_local(shop_tz, day, "11:00"), persona=me)
    later = at_local(shop_tz, day, "15:00")

    assert_refused(
        bookings.move(booking["id"], later, persona=barbers.sign_in_as_persona(own)), 403, "forbidden"
    )
    assert bookings.move(booking["id"], later, persona=stranger).status_code == 404
    assert (
        barbers.availability(
            own["id"], day, haircut["id"], persona=stranger, moving=booking["id"]
        ).status_code
        == 404
    )
