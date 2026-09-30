"""Who can cancel, and until when."""

from obj.barber import CANCEL_CUTOFF_HOURS
from utils.assertions import assert_refused
from utils.helpers import now_utc
from utils.local_time import local_day, parse_instant


def soonest_slot(barbers, barber_id, service_id, tz):
    """The second free time from now, not the first: the first can be seconds
    away and expire between being listed and being booked."""
    upcoming = barbers.slots(barber_id, local_day(tz, 0), service_id) + barbers.slots(
        barber_id, local_day(tz, 1), service_id
    )
    return upcoming[1]


def test_a_customer_cannot_cancel_inside_the_cutoff_but_the_owner_can(
    barbers, bookings, barber, trim, new_customer, shop_tz
):
    me = new_customer()
    booking = bookings.create_booking(
        barber["id"],
        trim["id"],
        soonest_slot(barbers, barber["id"], trim["id"], shop_tz)["start"],
        persona=me,
    )
    assert (parse_instant(booking["start"]) - now_utc()).total_seconds() < CANCEL_CUTOFF_HOURS * 3600

    assert_refused(bookings.cancel(booking["id"], persona=me), 409, "late_cancellation")
    assert bookings.cancel(booking["id"], persona="owner").assert_ok(200).as_dict["status"] == "cancelled"


def test_cancelling_twice_is_assert_refused(barbers, bookings, barber, haircut, new_customer, shop_tz):
    me = new_customer()
    booking = bookings.create_booking(
        barber["id"],
        haircut["id"],
        barbers.slots(barber["id"], local_day(shop_tz, 3), haircut["id"])[10]["start"],
        persona=me,
    )
    bookings.cancel(booking["id"], persona=me).assert_ok(200)

    assert_refused(bookings.cancel(booking["id"], persona=me), 409, "already_cancelled")


def test_a_barber_cannot_cancel_even_their_own_booking(barbers, bookings, haircut, new_customer, shop_tz):
    own = barbers.create_fake_barber()
    own_persona = barbers.sign_in_as_persona(own)
    booking = bookings.create_booking(
        own["id"],
        haircut["id"],
        barbers.slots(own["id"], local_day(shop_tz, 3), haircut["id"])[0]["start"],
        persona=new_customer(),
    )

    assert_refused(bookings.cancel(booking["id"], persona=own_persona), 403, "forbidden")


def test_another_customer_can_neither_see_nor_cancel_it(
    barbers, bookings, barber, haircut, new_customer, shop_tz
):
    owner_of_it, stranger = new_customer(), new_customer()
    booking = bookings.create_booking(
        barber["id"],
        haircut["id"],
        barbers.slots(barber["id"], local_day(shop_tz, 3), haircut["id"])[12]["start"],
        persona=owner_of_it,
    )

    assert (
        bookings.get_by_id(booking["id"], persona=stranger).status_code == 404
    ), "404, not 403: a 403 confirms it exists"
    assert bookings.cancel(booking["id"], persona=stranger).status_code == 404
    assert bookings.get_by_id(booking["id"], persona="owner").assert_ok(200).as_dict["status"] == "confirmed"
