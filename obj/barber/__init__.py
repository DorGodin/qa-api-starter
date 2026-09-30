"""The barbershop product (github.com/DorGodin/barber-booking-api), seen from outside.

Nothing here imports that product. Everything it knows came from the product's
documented contract, and the constants below are that contract: when the product
changes one, these suites are meant to fail until someone decides which is right.
"""

from obj.barber.barbers import Barbers
from obj.barber.bookings import Bookings
from obj.barber.customers import Customers
from obj.barber.services import Services

BOOKING_WINDOW_DAYS = 60
CANCEL_CUTOFF_HOURS = 24
SLOT_MINUTES = 15

__all__ = [
    "BOOKING_WINDOW_DAYS",
    "CANCEL_CUTOFF_HOURS",
    "SLOT_MINUTES",
    "Barbers",
    "Bookings",
    "Customers",
    "Services",
]
