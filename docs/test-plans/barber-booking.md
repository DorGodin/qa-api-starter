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
| `test_move.py` | test a move is the same booking at the new time and frees the old one |
| `test_move.py` | test a move to a taken time is refused and the booking stays |
| `test_move.py` | test the listing for a move offers its own time and the move accepts it |
| `test_move.py` | test inside the move cutoff only the owner can move |
| `test_move.py` | test between the two cutoffs a customer can move but not cancel |
| `test_move.py` | test a barber cannot move and a stranger does not find it |
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


## The booking page (tests/barber_ui, with --ui)

42 tests drive the page at `/` - Hebrew, right to left - through Playwright, checked twice:
on the screen, and through the API behind it.

| Test | What it proves |
|---|---|
| signing in replaces the form | the sign-in form is really gone, not only marked hidden |
| the Book button appears only after a time is chosen | a hidden panel stays hidden |
| a customer books a time and sees it | the message, the list, the price, the time gone from the grid, and the stored start |
| cancelling gives the time back | the list shows cancelled and the grid offers the time again |
| a late cancellation explains why | the reason, what to do next ("call the shop"), and the booking still there |
| moving a booking from the list | the same booking id at the new time, barber and service locked while choosing, its own quarter-hour offered, the panel back to booking after |
| a time taken while moving | told it has just gone, and the booking still at its old time |
| a late move explains why | the 12-hour rule in Hebrew, and the booking unmoved |
| stopping a move | the panel back as it was, nothing changed |
| a double click books once | counted on the wire: one POST, and "Booked" rather than a refusal |
| signing up signs you straight in | the new account lands on the booking screen |
| a time taken while you were looking | two windows; the second is told it has just gone, and no longer offered it |
| times on the shop clock in any browser time zone | a New York browser still sees 09:00 opening and 18:30 last start |
| a name that looks like HTML | shown as text, never run |
| a wrong password and an unknown user | the same message |
| every field has a label | fields are reachable by their exact label, outcomes are announced |
| the page is Hebrew and mirrored | `lang="he" dir="rtl"`, and the booking panel sits on the right |
| times keep their own order | a time is `direction: ltr` inside the RTL page; the grid still flows right to left |
| a Latin name is isolated | the barber's name sits inside FSI...PDI in the Hebrew sentence |
| prices the Israeli way | the amount, then the sign - never `₪80` |
| dates in Hebrew | the weekday and month are Hebrew, with no Latin letters |
| no English reaches the customer | wrong password, invalid sign-up and a taken slot all answer in Hebrew only |
| a booking is confirmed in a popup | green, modal, says the day, time and price, and puts the focus on its close button |
| the popup closes with its button and with Escape | both close it |
| nothing behind the popup can be pressed | it is `:modal`, and a click on a time behind it does not land |
| a refusal that is not a taken time | red "לא הצלחנו לקבוע את התור", with the reason - not the taken-time wording |

**Waiting is on the page's own signal.** The page holds `aria-busy="true"` while it fetches
and `"false"` once the screen is current; the page object waits for that. It replaced
`wait_for_load_state("networkidle")`, which returns at once on a page that has already
loaded — a test read the list before it refreshed, passed once by luck, failed the next run.

**Mutation check on the page.** Fifteen behaviours of the page were broken one at a time:
hidden panels left on screen, a name written as HTML, times shown on the browser's clock, a
double click sending twice, refusals shown as raw codes, a failed booking not refreshing
the times, outcomes not announced, the late-cancellation reason lost - and for Hebrew: the
layout left to right, names not isolated, prices the American way, dates in English, the
server's English shown for an unmapped code, times following the page's direction, labels
wrapped around their fields - and for the popup: no popup, a popup that is not modal, a
refusal shown as a success, a taken time worded like any other refusal, a close button that
does nothing, a success that leaves out the price. **21 of 21 caught.**

`BookingPage.book()` reads the popup, keeps what it said in `last_popup`, and closes it:
the popup is modal, so a test that went on to press anything behind it would wait for a
click that can never land. A test about the popup itself passes `keep_popup=True`.

```bash
make ui-barber-watch        # watch in a visible browser
make ui-barber-record       # video and trace of every test in reports/ui-barber
```

### The owner's screen (test_owner_screen.py, 20 tests with parameters)

Every change the owner makes is checked from the other side too: not "the hours saved", but
"the customer is now offered 12:00 to 13:30 on Monday and nothing on Tuesday".

| Test | What it proves |
|---|---|
| the owner gets the management screen | and no booking form |
| a customer and a barber never get it | the screen is the owner's only |
| new hours change what customers are offered | Monday 12-14 only: 12:00 first, 13:30 last, Tuesday empty |
| closing before opening is refused | a Hebrew reason, and the stored hours unchanged |
| a time off the quarter hour is refused | 10:10, 9:00, 25:00, abc - each refused, nothing saved |
| a day off takes the barber out that day | listed, no times offered, and undone |
| the same day off twice | explained in Hebrew, still listed once |
| a new barber is bookable at once | selected, on the shop's hours, bookable on Sunday at 10:00 |
| a new service is priced exactly | 92.55 is stored as 9255 agorot - not the float's 9254 |
| a price that is not shekels and agorot | 80.555, abc, -5, 80,50 - each refused, nothing created |
| the same service name twice | explained in Hebrew |
| a price change reaches new bookings only | the earlier booking keeps 80.00, the next one costs 99.90 |
| withdrawing a service | gone from what customers are offered |
| the owner cancels inside the cutoff | where a customer could not |

Mutation check on the owner's screen: prices through a float, both hours checks removed, an
unticked day not sent as off, a day off on the wrong barber, a new barber not selected, a
withdrawal not saved, customers given the screen, the owner unable to cancel, two Hebrew
explanations lost. **11 of 11 caught.**

## Under load (perf/barber/booking_race.js)

The booking race, kept alive for the whole run: every user aims at the same fresh time
in each 200ms window. Gates - all correctness, all kept under `stress`: no unexpected
status, no 5xx, no 201 that cannot be read back, no two overlapping bookings for one barber
in the database at the end, and no barber left unbooked. Mutation check: against a server
with its booking lock broken, 144 server errors and exit 99; against the fixed server, 101
races with 101 winners and no 5xx. CI runs it on every push in the barbershop job.

## Test data prerequisites

The product's three seeded accounts (`owner`, `barber`, `customer`) with the passwords from
its `.env.example`. Everything else each run creates for itself.

## Running

```bash
# in barber-booking-api
cp .env.example .env && make install && make run-test    # the test copy, port 8101

# here
make env-check ENV=barber
ENV=barber pytest
```
