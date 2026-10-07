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
| `test_month_calendar.py` | test every day counts what its list offers, a booking and a day off included |
| `test_month_calendar.py` | test months outside the booking window are refused with the reason |
| `test_booking_rules.py` | test a new barber starts on the shop hours, friday until two |
| `test_cancellation.py` | test a customer cannot cancel inside the cutoff but the owner can |
| `test_cancellation.py` | test cancelling twice is assert refused |
| `test_cancellation.py` | test a barber cannot cancel even their own booking |
| `test_cancellation.py` | test another customer can neither see nor cancel it |
| `test_sign_in_with_code.py` | test the first sign-in opens the account and shows only the last four digits |
| `test_sign_in_with_code.py` | test the same phone however it is typed is the same account |
| `test_sign_in_with_code.py` | test wrong codes count down and the third uses the code up |
| `test_sign_in_with_code.py` | test a code signs in once |
| `test_sign_in_with_code.py` | test the same code sent six times at once signs in exactly once |
| `test_sign_in_with_code.py` | test one address gets only so many codes an hour |
| `test_sign_in_with_code.py` | test only a mobile number gets a code |
| `test_barbers_leaving.py` | test a barber who left is offered to no one and the owner still sees them |
| `test_barbers_leaving.py` | test nobody books a barber who left |
| `test_barbers_leaving.py` | test their bookings stay, say who, and wait for the owner |
| `test_barbers_leaving.py` | test a barber who left is signed out and cannot sign in |
| `test_barbers_leaving.py` | test a barber who comes back is bookable again |
| `test_barbers_leaving.py` | test only the owner decides who has left |
| `test_guest_bookings.py` | test a guest booking takes the time from everyone else |
| `test_guest_bookings.py` | test a guest booking cannot take a customer's time |
| `test_guest_bookings.py` | test the owner is not held to the customers' limit |
| `test_guest_bookings.py` | test a guest needs a real name[empty, spaces, too-long] |
| `test_guest_bookings.py` | test only the owner books guests and a customer never sees them |
| `test_guest_bookings.py` | test the owner moves a guest booking past another barber's customer |
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
| a customer books a time and sees it | the card in the panel, no repeat of it under the list, the list, the price, the time gone from the grid, and the stored start |
| the barbers | a pill each by full name, exactly the ones the customer can book, one chosen and one Tab stop; pressing one offers that barber's times; the arrows move to the next barber and choose them; locked while a booking's time is changed; a barber off the day chosen moves the calendar to a free day |
| the month's calendar | a free day named with the number of times its list then shows; a day off and a full day marked unavailable and grey alike, a tap on one changing nothing; arrows (left is the next day), Enter and Page Down; the month turning only inside the booking window; the screen opening on a free day; every day at least 24px wide and 44px tall on three phones |
| a day already over | not choosable, named as such, the day chosen unchanged; no turning back to a past month |
| the tabs on a phone | a customer moves between booking and their bookings, one shown at a time; a new booking opens the bookings with the focus on it; a change of time goes back to booking; a tab pressed while the list still loads is not undone (the list held back to make the race); the page ends above the tabs; the owner has none; a computer shows both side by side |
| the times on a phone | pills, five to a row, 36px tall, ends fully round, on three phones |
| the greeting | a customer greeted `שלום` and their first name, the full name kept on the account; the staff see their name and role instead |
| the booking card | a tick, the title, the day and time, the service with the barber and the price, and two buttons - the list and another booking |
| cancelling gives the time back | the list shows cancelled and the grid offers the time again; the line after it is red |
| a cancelled booking leaves the list | one the customer cancelled is gone once they leave the app (a reload) and after twelve hours; one the shop cancelled stays twelve hours, a return included, and is then gone |
| a cancelled booking says who cancelled it | `cancelled_by` is `customer` or `staff`, and `null` while confirmed (API) |
| the afternoon hours wait for the barber | a customer's booking from 14:00 up to (not including) 16:00 is `approval: pending` with `decide_by` two hours out; 13:45 and 16:00 are not; it holds the chair; the guest booking by the owner never waits (API) |
| the barber answers | the barber approves or declines their own booking, the owner any; a no cancels it (`cancelled_by: staff`), frees the time and no longer counts toward the limit; another barber gets 404, a customer 403; an answer cannot be reversed; nothing to answer outside the hours (API) |
| a move meets the same rule | a customer's move into the hours waits again, out of them ends the wait; the owner's move decides it (API) |
| a request is not a booking | the card says `הבקשה נשלחה`, with an amber mark in place of the tick, and nothing else; the list says `ממתין לאישור של <barber>`; outside the hours it is `התור נקבע` |
| the customer is told in the page | an answer that came while the page was closed is told on opening - once; the page looks again while a booking waits; a no offers `בחירת שעה אחרת` and the list says so |
| the card is in view under a tall header | with the shop's cover and profile picture the header is tall; the card, and both its buttons, are brought onto the screen of the smallest phone |
| the owner sets when it asks | a switch and, per day, the hours from and up to; turned off, or on another day or hour, a booking is booked at once; saved rules are read back; a customer is refused; rules that make no sense (a day missing, backwards, off the quarter hour, no switch) are refused and change nothing; a booking already waiting keeps waiting (API) |
| the owner's panel | the switch and seven rows read from the rules, the same rows as the working hours; unticking a day disables its hours; backwards hours and hours off the quarter hour are explained and nothing is saved; a customer sees no panel |
| courses | the owner adds, changes and withdraws them (title, a short line, a date, a price - each may be empty but the title); a customer reads the active ones, by date with the undated last; only the owner writes; a bad title, line, price or date is refused (API) |
| a course's picture | accepted by its bytes (JPEG, PNG, WebP up to 3 MB), never by a name; a gif, a script and a large file are refused and the course keeps none; a new picture replaces the old, removal takes it off the server; the media route serves no other file (API) |
| the courses card | a picture over the title and one line (what, when it starts, the price - `3,200` and not `3,200.00`, `חינם` for 0); a title that looks like a tag is text; the button opens WhatsApp in a new tab with `noopener`; a withdrawn course is not shown; with none the tab says so |
| the owner keeps the courses | the panel adds a course (a name is required, a price that is not a number is explained), edits and withdraws one, uploads a picture and removes it; a file that is not a picture is refused in words; the owner has no customers' panel |
| the courses tab on a phone | the third tab, no sideways overflow, the card's button a finger tall, axe clean |
| a review comes after the appointment | stars 1 to 5 (anything else is 422), refused before the booking is over (`not_over_yet`), after it was cancelled (`not_reviewable`), by anyone but its own customer; the finished-booking path is in the product's suite, since a booking cannot be made in the past (API) |
| the review card | a booking the page is told is over shows a card with the barber's name and five named stars; a tap sends that many and thanks; the words follow and the card goes; `לא עכשיו` stays hidden after a reload; no card for a booking not over; a refusal is said in Hebrew; the barber and the owner see the stars and words in the row; on a phone it fits and the stars are a finger wide, axe clean |
| a customer who cancels or moves too often | three cancellations or three moves of their own make the next booking and the next move wait for the barber at every hour, with no time after which silence is a yes; two do not; other customers, the shop's cancellations and the owner's moves do not count; the barber answers as usual; the page shows an ordinary request. The 90 days are in the product's suite (API, page) |
| a service that needs the barber | a service says so; only the owner sets it; a booking of it waits at every hour with no time limit; the same hour with an ordinary service does not; the barber answers as usual; the customer's move waits again, the owner's decides; the owner's guest booking never waits; the owner's list has a tick for each service, and one when adding (API, page) |
| the barber and the owner answer from the diary | `אישור` and `דחייה` on a waiting row, and no cancel for a barber |
| a booking too close to cancel or move | the customer is not offered the button that is past its cutoff (12 hours for both), and the row says why in those numbers, with a WhatsApp link that names the booking (new tab, `noopener`); none without a number; the owner keeps the cancel button; on a phone it fits and the link is a finger tall |
| a late cancellation explains why | the reason, what to do next ("call the shop"), and the booking still there |
| the shop's header | the brand and the tab title from the shop's settings, a named button for each contact link set and none for the rest, the poles and scissors hidden from screen readers and still for reduced motion |
| the privacy policy | one step from the sign-in screen, every placeholder filled, WCAG 2.2 AA |
| the contact buttons | at the foot of the page, after the sign-in |
| the legal links on a phone | a signed-in customer sees neither the accessibility statement nor the privacy policy on either tab, and no foot with nothing in it - the contact buttons stay at the foot of booking when the shop sets any; the sign-in screen keeps both links, and so does a computer |
| the page ends above the tabs | scrolled to the bottom, the end of the signed-in screen is not hidden under the tab bar |
| a signed-in phone screen | opens at its top, not where the sign-in form had been |
| the slim bar on a phone | scrolled with the keyboard open, the brand shrinks to a slim bar at the very top and leaves when scrolled back; a field reached by the keyboard is not under it; the owner's menu sticks under it, not behind it; hidden from screen readers and without a slide for reduced motion |
| a first sign-in by code | name and phone, the code screen showing only the last four digits, the code, the greeting by first name, and the account named in full as given |
| a wrong code | the tries left, the boxes marked invalid, and לכיסא locked until a digit changes |
| the third wrong code | locked for good until a new code |
| a new code | offered only after the countdown |
| changing the number | back to the first step with what was typed |
| a landline number | explained in Hebrew, no code sent |
| the code field | one-time-code and numeric, so a phone fills it from the SMS |
| the code screen | WCAG 2.2 AA, a wrong code included |
| the owner takes a barber out | the diary kept, the barber marked in the list, no times offered and no error, the button turned round |
| a barber brought back | offered times again |
| a customer whose barber left | not offered that barber, and still sees who the booking is with |
| the owner books a caller by name | the name in the popup and the diary, the field cleared, the time gone, and stored with no customer |
| the owner presses book with no name | nothing booked, the reason shown, the focus on the name field |
| a guest's name that looks like HTML | shown as text in the diary, never run |
| a withdrawn service | not offered for booking, and the screen not left showing an error |
| changing a booking's time (`שינוי מועד`) from the list | the approved wording on the row, the panel, its buttons and the card; the same booking id at the new time, barber and service locked while choosing, its own quarter-hour offered, the panel back to booking after |
| a time taken while moving | told it has just gone, and the booking still at its old time |
| a late move explains why | the 12-hour rule in Hebrew, and the booking unmoved |
| stopping a move | the panel back as it was, nothing changed |
| a double click books once | counted on the wire: one POST, and "Booked" rather than a refusal |
| an account made through the API signs in on the page | the page has no sign-up form; an account made through `POST /customers` signs in with its password and is greeted by first name |
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
| no English reaches the customer | a wrong password and a taken slot both answer in Hebrew only |
| a booking is confirmed by a card | it stands where the form was, says the day, time, service and price, and takes the focus on its heading |
| the card leads on | `התורים שלי` goes to the list with the focus on the new booking, `קביעת תור נוסף` brings the form back, and the booking tab pressed again shows the form |
| a refusal for too many bookings | offers `התורים שלי`, which closes it and shows the list |
| a refusal for a taken time | closes with a button that says `בחירת שעה אחרת`, and the list of times is there |
| a refusal is a modal popup | a white card with a red mark, `:modal`, a click on a time behind it does not land, and it closes with its button and with Escape |
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
wrapped around their fields - and for the answers: a popup in the card's place, a card that does not take the focus, a list button that does
nothing before the list is drawn, a booking tab that leaves the card in place, a refusal shown as a success, a taken
time worded like any other refusal, a close button that does nothing, a card that leaves out the price. **21 of 21 caught.**

`BookingPage.book()` reads what answers - the card, or the popup of a refusal or of the owner's booking for a
caller - keeps it in `last_answer`, and leaves it: the popup closed, the card's `התורים שלי` pressed. A popup is
modal, so a test that went on to press anything behind it would wait for a click that can never land. A test
about the answer itself passes `keep_answer=True`.

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

## Sign-in codes: the fake SMS provider

The barbershop sends its codes to `SMS_URL`. Every copy the suites start - `make run-test`,
the CI action, the mutation runner, the image - points it at `utils/fake_sms.py` on 8109, and
the `sms_inbox` fixture starts that provider for the run when nothing answers there, and stops
it after. A test reads a code from the inbox the way a person reads their phone; the product
has no hook for it. A customer is made by `customers.sign_in_by_code`, and a page opens signed
in through the product's own remembered sign-in (`sign_in_as`) - one code per phone, since a
phone gets a new code only once a minute. The code sign-in itself is driven end to end by
`sign_in_by_code` and `test_sign_in_by_code.py`. Staff still sign in with a password until they
have phones.

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
