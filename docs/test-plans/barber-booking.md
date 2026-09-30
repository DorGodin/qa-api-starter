# Test plan: barbershop (barber-booking-api)

**Status:** Implemented — 39 tests, all passing against the product's main.

**Product:** [github.com/DorGodin/barber-booking-api](https://github.com/DorGodin/barber-booking-api),
in its own repository, sharing no code with this one. It has no test hooks: nothing here can
reset it, and nothing here needs to.

## How isolation works without a reset

- Each module gets **barbers of its own**, created by the owner through `POST /barbers` and
  given known hours (around the clock by default), so no test depends on the time of day.
- Each test **signs up the customers it needs** through the public `POST /customers` and logs
  them in as personas of their own. Two runs never book into each other.
- Each module gets **services of its own**, so a price change in one test never changes
  another module's arithmetic.

The price: the product cannot delete anything through its API, so every run leaves its
barbers, customers, services and bookings behind. `make cleanup ENV=barber` says so — it
reads the product's OpenAPI document, finds no delete endpoints, and reports every object as
`no delete endpoint` without sending a request. Locally, `make reset-db` in the product
starts over.

## Tests

| File | Test |
|---|---|
| `test_booking_flow.py` | test a customer books the first free slot and it is theirs |
| `test_booking_flow.py` | test cancelling gives the slot back |
| `test_booking_flow.py` | test a price change does not reach back into a booking |
| `test_booking_flow.py` | test the owner sees every booking and a barber only their own |
| `test_booking_rules.py` | test a haircut that would run past closing is refused but one ending at closing is not |
| `test_booking_rules.py` | test nothing before opening |
| `test_booking_rules.py` | test the listing offers the slots right before and right after a booking |
| `test_booking_rules.py` | test back to back is allowed and an overlap is not |
| `test_booking_rules.py` | test one customer cannot be in two chairs at once |
| `test_booking_rules.py` | test a start off the quarter hour is assert refused |
| `test_booking_rules.py` | test a start without a utc offset is assert refused |
| `test_booking_rules.py` | test the past is refused in the listing and the booking |
| `test_booking_rules.py` | test the booking window is enforced in the listing and the booking |
| `test_booking_rules.py` | test nothing is offered or booked on a day off |
| `test_booking_rules.py` | test a withdrawn service is neither listed nor booked |
| `test_booking_rules.py` | test every slot the listing offers can actually be booked |
| `test_cancellation.py` | test a customer cannot cancel inside the cutoff but the owner can |
| `test_cancellation.py` | test cancelling twice is assert refused |
| `test_cancellation.py` | test a barber cannot cancel even their own booking |
| `test_cancellation.py` | test another customer can neither see nor cancel it |
| `test_concurrency.py` | test many customers racing for one slot get exactly one booking[same-start] |
| `test_concurrency.py` | test many customers racing for one slot get exactly one booking[overlapping-starts] |
| `test_concurrency.py` | test one customer double submitting without a key books once |
| `test_dst.py` | test a transition day offers the hours it really has |
| `test_dst.py` | test the repeated hour can be booked twice as two different moments |
| `test_dst.py` | test opening time stays on the local clock across the change |
| `test_idempotency.py` | test the same key twice returns the first booking |
| `test_idempotency.py` | test a key reused for a different booking is refused |
| `test_idempotency.py` | test a double tap that arrives at the same instant is still one booking |
| `test_idempotency.py` | test the same key from two customers is two bookings |
| `test_permissions.py` | test a customer cannot run the shop[create-service] |
| `test_permissions.py` | test a customer cannot run the shop[create-barber] |
| `test_permissions.py` | test a customer cannot run the shop[set-hours] |
| `test_permissions.py` | test a customer cannot run the shop[add-time-off] |
| `test_permissions.py` | test a customer cannot run the shop[change-a-price] |
| `test_permissions.py` | test a barber cannot change the menu |
| `test_permissions.py` | test every bad credential looks the same to an outsider |
| `test_permissions.py` | test an unknown user and a wrong password get the same answer |
| `test_permissions.py` | test each customer lists only their own bookings |

## Key implementation details

- **The race assertion is three assertions.** Exactly one 201, every other a 409
  `slot_taken`, and zero 5xx. On SQLite an unlocked check-then-insert answers the losers with
  500s and leaves one booking, so "one booking exists" alone passes a broken server. On
  Postgres the same bug double books; this catches both. The calls are released together by
  a barrier (`utils/concurrency.at_once`), not merely submitted to a pool.
- **Compare instants, never strings.** The product writes `…T06:15:00Z` and `to_iso` writes
  `…T06:15:00.000Z`. A membership check across the two formats is always False — which once
  made an assertion pass whatever the product did. `offered_instants()` parses first.
- **DST dates are found, not hardcoded.** `utils/local_time.dst_transitions` scans the booking
  window; when no transition falls inside it, the DST tests skip and say so. Day lengths are
  measured between UTC instants: two aware datetimes sharing a tzinfo subtract on the wall
  clock and always give 24 hours.
- **A refusal is its status and its code.** `utils/assertions.assert_refused` checks both —
  `slot_taken` and `customer_overlap` are both 409 and mean different things to the person
  booking.
- **The product's rules are constants in `obj/barber/__init__.py`** — a 60 day window, a 24
  hour cutoff, 15 minute slots. When the product changes one, these suites fail until someone
  decides which side is right.

## Mutation check

Every rule was broken in the product one at a time, with the suites run against each
broken build: the ignored booking lock, back-to-back counted as overlap, a service ending at
closing refused, a fixed UTC offset, the Idempotency-Key ignored, 403 instead of 404, the
cutoff removed, a customer in two chairs, a price change reaching back, availability offering
a clashing slot, a barber allowed to cancel. **11 of 11 caught.** The first pass caught 9 —
the two survivors were a vacuous string comparison and a missing check that the listing
offers back-to-back slots.

## Test data prerequisites

The product's three seeded accounts (`owner`, `barber`, `customer`) with the passwords from
its `.env.example`. Everything else each run creates for itself.

## Running

```bash
# in barber-booking-api
cp .env.example .env && make install && make run

# here
make env-check ENV=barber
ENV=barber pytest
```
