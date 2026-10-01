# qa-api-starter

[![ci](https://github.com/DorGodin/qa-api-starter/actions/workflows/ci.yml/badge.svg)](https://github.com/DorGodin/qa-api-starter/actions/workflows/ci.yml)

A ready-to-use API test framework in Python and pytest.
Clone it, run it, then point it at your own product.

![Two customers go for the same free time; the first is booked, the second is told it has just gone](docs/media/race.gif)

*Two customers, one free 10:00. The first gets the green popup; the second is told the time
has just gone, and it leaves their screen. Recorded from the UI suite against the barbershop —
`make ui-barber-watch K="looking"` runs it in front of you.*

**558 tests, in CI on every push** — 411 against the demo API that ships in this repository,
in six groups, and 147 against a second product in its own repository,
[barber-booking-api](https://github.com/DorGodin/barber-booking-api), reached only through its
URL, its page tests on a desktop, an iPhone (WebKit, Safari's engine) and an Android phone. On top
of them: load tests whose thresholds fail the pipeline, and **100 mutants** — rules
of the product broken on purpose, each of which a named suite must catch, run every night
(`make mutate`).

The point: arrive at a new job and not rebuild what takes weeks — the object layer,
environments, personas, suite gating, the production guard, bug filing and CI.

---

## Start

```bash
make install     # virtualenv + dependencies
make api         # terminal 1 — demo API on http://127.0.0.1:8000
make test        # terminal 2 — run the tests
```

No Python on your machine? `docker compose run --rm tests` runs every group except the
browser suite in a container. `docker compose run --rm ui` runs that one.

---

## The six groups

| Command | What it checks | Tests |
|---|---|---|
| `make test` | the product behaves | 64 |
| `make unit` | the framework itself is correct. No API, no network | 130 |
| `make edge` | what happens on bad input | 20 |
| `make security` | nobody reaches what is not theirs | 22 |
| `make ui` | what the user sees in a browser | 20 |
| `make llm` | the AI feature does not invent data | 41 |

Only `make test` runs by default. The rest need a flag.

After a run:

| Command | Shows |
|---|---|
| `make report` | the run that just finished: counts per group, failures, skips, slowest tests |
| `make dashboard` | every run so far, and every object the runs created, as one HTML page |
| `make trends` | what regressed against earlier runs: a shrunken group, a new skip, a new failure |
| `make cleanup ENV=qa` | what the runs left on an environment. `YES=1` deletes it |
| `make notify-dry` | the summary that would be posted to a channel |
| `make env-check ENV=qa` | whether an environment is usable: config, health, a login per persona |
| `make perf-smoke` | one user, seconds: does the API work at all |
| `make perf-load` | the read path under concurrency |
| `make perf-write` | the write path under concurrency, with the money math asserted |
| `make perf-spike` / `perf-soak` / `perf-stress` | a sudden 5x, a long hold, a ramp past capacity |
| `make perf-trends` | whether p95 has crept up against earlier load runs of the same shape |
| `make perf-barber` | the barbershop booking race under load: no double booking, no 5xx, every 201 stored |

**Why they are separate.** A developer checking one change should not wait for a browser to
start. When everything always runs, people stop running anything.

---

## What is in each folder

| Folder | What it holds |
|---|---|
| `obj/` | one class per API resource, over a shared CRUD base. Payloads and URLs live here, never in a test |
| `tests/suites/` | ordering, CRUD, auth, paging, budget rules, response shape, concurrency, contract |
| `tests/unit/` | the framework's own tests |
| `tests/edge-cases/` | broken payloads on purpose, and the error contract |
| `tests/security/` | access control, credential handling, exposure |
| `tests/ui/` | Playwright: the flow, resilience when the API fails, accessibility |
| `tests/llm/` | DeepEval: grounded facts, prompt injection, data isolation |
| `perf/` | k6: read path, write path, and four load shapes. Thresholds fail the pipeline |
| `config/` | one block per environment |
| `data/scenarios/` | cases as CSV and JSON, so a non-engineer can add one |
| `.claude/` | the AI workflow: agents, skills, commands |

---

## The AI workflow

### Five agents

| Agent | What it does |
|---|---|
| `test-reviewer` | reads your diff and asks: if the product broke, would this test fail? |
| `ticket-verifier` | takes a ticket, checks what is covered, writes and runs what is missing |
| `flake-hunter` | reruns an intermittent test and tells a flaky test from a flaky product |
| `coverage-mapper` | marks every endpoint proven, touched or untested, and ranks gaps by risk |
| `env-doctor` | finds why a suite will not start, layer by layer |

### Eleven skills

| Skill | Covers |
|---|---|
| `write-tests` | which group a test belongs in, and what to assert |
| `verify-before-claiming` | never report a result you did not observe |
| `verify-story` | how a ticket gets verified, with a verdict per criterion |
| `write-bug` | how a bug is written for product, support and engineering |
| `test-data-strategy` | test data, idempotency and the production guard |
| `flaky-test-policy` | what to do with a flaky test, and what is banned |
| `release-readiness` | what blocks a release |
| `plan-test-work` | a plan written to a file, so it survives the conversation |
| `commit-and-pr` | messages that say what changed and what was verified |
| `run-report` | turns the last run into a verdict, not a wall of output |
| `monitoring` | run history, and what each run left behind |

### Seven commands

`/new-suite` · `/explore-api` · `/qa-sweep` · `/file-bugs` · `/flake-check` ·
`/coverage-gap` · `/env-doctor`

**Agents never write to the tracker.** They draft; a person sends.

---

## What happens after the tests run

Three files land in `reports/` after every run. No server, no database, nothing to keep
alive — just files.

**`last-run.md`** — a summary of the run that just finished: how many passed and failed in
each group, which tests failed and what exactly broke in each, which were skipped and why,
and which were slowest.

```bash
make report
```

**`history.jsonl`** — one line per run: when it ran, on which environment, and the results.
This is what makes comparing runs possible.

```bash
make trends
```

That compares the last run to earlier ones and flags three things that are easy to miss: a
**group that shrank** (fewer tests ran than last time — usually a forgotten flag or a
renamed folder), a **test that became skipped**, and a **new failure**. It also says when a
run got slower, but that never blocks.

**`perf.jsonl`** — one line per load run: which script, which load shape, how many
users, p95 and p99, and the three correctness counts (wrong totals, budget rejections,
5xx). Every `make perf-*` target writes it, including runs that crossed a threshold.

```bash
make perf-trends
```

This catches what a single load run cannot: **p95 creeping up**. A climb from 2ms to 9ms
still passes a 400ms threshold, so k6 calls it a pass. The history does not. It only
compares runs of the same script, shape and number of users, because a bigger run is
slower by design and that is not a regression.

**`artifacts.jsonl`** — every object the tests created: what it was, its id, on which
environment, and which test made it.

The line is written automatically on every create, because every API call goes through one
place in the code. **No test opts in, and nothing can be forgotten.**

That answers the two questions a shared environment always raises:

```bash
make cleanup ENV=qa          # what the tests left on qa
make cleanup ENV=qa YES=1    # remove it
```

And when somebody asks where a record came from, you search its id in the file and see
which test made it.

**`make dashboard`** turns all of it into one HTML page, with no network calls and nothing
to install:

| Panel | Answers |
|---|---|
| Regression | did anything get worse since the comparable earlier runs |
| Pass rate | the shape over time, on an axis that makes a one-test dip visible |
| The last run, by group | which group carried the failures |
| Tests that fail most often | the ones nobody has pinned down |
| What is left on each environment | how much test data is there, and the command that clears it |
| Runs, and objects created | the full detail behind all of the above |

---

## Filing bugs from a failed run

When a test fails you can open a ticket from it — but **never from inside the test**. A
test asserts; the decision to file belongs to the run, and it is off by default.

```bash
pytest --file-bugs-dry-run   # shows the exact ticket it would open, without opening it
pytest --file-bugs           # one ticket per failed test
```

The ticket follows the team's bug template — ENV, Precondition, Steps to reproduce, Actual
result, Expected result, Notes — filled with what the run actually knows. **Steps to
reproduce are the calls the test really made**, not an instruction to run the suite. The BE
or FE prefix comes from where the test lives.

**No duplicates:** every ticket carries the test's id. If the same test fails again
tomorrow, the filer finds the open ticket and comments on it instead of opening a second.

The tracker URL and token come from environment variables, never from the repo.

---

## Notifications

```bash
make notify-dry              # print the message without sending
pytest --notify              # send it to NOTIFY_WEBHOOK
```

The message carries the environment, the counts, the failing tests with each assertion, and
any regression finding. Slack and Teams both accept it.

---

## Using it without Claude Code

Everything outside `.claude/` is plain Python and pytest. The framework, the suites, the
bug filer, the dashboard, cleanup, trends, notifications and CI all work with no AI
involved at all.

`.claude/` holds two things, and neither of them runs anything:

| What | Without Claude Code |
|---|---|
| `CLAUDE.md` | read it as the contributing guide. It is the repo's rules, written for a person |
| skills | read them as the team's QA handbook: how a ticket gets verified, how a bug is written, what to do with a flaky test |
| agents and commands | read them as checklists. `/new-suite` describes exactly what to create, in order |

**Using another assistant.** Point it at the same file. Cursor reads `.cursorrules`,
Copilot reads `.github/copilot-instructions.md`, and most others take a path you configure.
Symlink or copy `CLAUDE.md` and the rules apply unchanged:

```bash
ln -s CLAUDE.md .cursorrules
```

**Not using an assistant at all.** Delete `.claude/` and nothing breaks. Keep `CLAUDE.md`
anyway — a new contributor reading it learns where payloads live and why `xfail` is banned,
which is the same reason it exists for an agent.

---

## A second product: the barbershop

The demo lives in this repository, so passing against it proves less than it seems — a
framework can quietly lean on a product it grew up next to. So there is a second one:
[barber-booking-api](https://github.com/DorGodin/barber-booking-api), a real appointment
booking API in its own repository. It shares no code with this one and has **no test hooks**
— no reset, no back door. The suites in `tests/barber/` know it only through its URL.

```bash
# in barber-booking-api:   cp .env.example .env && make install && make run-test
make env-check ENV=barber
ENV=barber pytest
```

With `ENV=barber` only the barbershop's suites are collected, and the demo's are not. They
run against the barbershop's **test copy** on port 8101 (`make run-test`), which has its own
database - never the copy on 8100 that a person clicks through, which they would bury in
test barbers and services.

What they cover: many customers racing for one slot (exactly one 201, every other a 409,
zero 5xx), overlaps and back-to-back, closing time to the quarter hour, a customer in two
chairs, the booking window, days off, late cancellation, a double tap with an
`Idempotency-Key`, a price change that must not reach back into bookings, who can see and do
what — and daylight saving, on whichever transition falls inside the booking window.

**And the booking page, in a real browser.** The barbershop serves a booking page at `/` —
in Hebrew, right to left — and `tests/barber_ui/` drives it the way a customer and the
owner do. 89 tests: twenty on the owner's management screen (hours, days off, a new barber,
prices in shekels, withdrawing a service — each checked from the customer's side), four on
the popup every booking answers in (green when booked, red "השעה כבר
תפוסה" when someone was faster, and modal: nothing behind it can be pressed), six are about
Hebrew itself (the layout mirrored, times still read left to right, a
Latin name isolated inside a Hebrew sentence, the price the Israeli way round, and never a
word of the server's English on screen), and among the rest are two
customers looking at the same free time where the second is told plainly it has just gone,
a browser set to New York that must still show the shop's own clock, a double click that
must send one request, and a name that looks like HTML that must never run. To watch them:

```bash
make ui-barber-watch                    # a visible browser, at human speed
make ui-barber-watch K="looking"        # just the two-customer race
make ui-barber-record                   # a video and a step-by-step trace of every test
make ui-barber-mobile                   # every page test on an iPhone (WebKit) and an Android phone
make ui-barber-journeys                 # the end-to-end journeys only
```

**And end to end, in one piece.** Every other page test builds its barbers, services and
bookings through the API — fast, and one thing at a time — so nothing there proves the pieces
join up. `test_journeys.py` prepares nothing. The owner adds a barber, types his hours and a
service with its price, on the screen; a customer signs up on the screen, is offered exactly the
times those hours allow, and books the last one of the day; the barber signs in and finds it in
his diary; the customer cancels, and a second customer is offered that time and books it. Each
person is a browser of their own. The API is used once, at the end, to check that what the
screens showed is what was stored. The other journeys:

- **a shared device** — one customer signs out and the next signs in on the same open page, and
  finds nothing of the one before: no bookings, no name, and no username or password left in a
  form. Writing it found that signing out only hid the screen, and the sign-up form still held
  the password the last customer had signed up with. A refresh keeps the sign-in; signing out
  is not undone by one;
- **what the owner changes, seen by each customer** — a new price reaches the next booking and
  not the one already made, a withdrawn service is no longer offered but its bookings stay, and
  a booking the owner cancels shows as cancelled to its customer and its time is offered again;
- **a day off** closes a day and taking it back reopens it;
- **a redeploy** — in CI the journeys run against the barbershop's Docker image, what would be
  deployed. One books, replaces the container with a new one on the same volume, and checks that
  the account, the booking and the sign-in all survived. Proven both ways: against a redeploy that
  loses the database, it fails.

**And against guessing and injected scripts.** The barbershop had no limit on password guesses,
and its page — which keeps the sign-in where any script in it can read it — had no
Content-Security-Policy. `tests/barber/test_login_limits.py` checks the limits it has now: five
wrong passwords lock an account from that address, with the right password too; twenty from one
address lock it for any account; the real person is never locked out from somewhere else; an
unknown username is refused exactly like a real one. Every test that fails a sign-in on purpose
comes from an address of its own (`fresh_address`, sent as `X-Forwarded-For`), or a few runs in a
row would lock the machine the suites run on. `test_page_policy.py` checks the policy allows
exactly the script and style the page serves, by hash; in the browser, a whole booking and the
owner's screen run with no violation, and a script slipped past the escaping does not run. Each
rule has a mutant — thirteen, all caught. `test_sign_out.py` checks that signing out ends the
sign-in on the server: a token copied before the sign-out is refused at once, not in twelve
hours, and the person's other sign-ins stay. A customer holds at most two bookings ahead
(`test_booking_cap.py`, five sent at once with room for one included), and one address makes
at most five accounts an hour (`test_signup_limits.py`), since more accounts are the way around
the first. Every customer the suites make, and every browser they open, comes from an address
of its own, as different people's phones would.

**And the dependencies themselves.** pip-audit had never been run on either repository. Its
first run found seven advisories against the barbershop's starlette — Host-header URL
reconstruction among them — and others against pytest and requests. All are fixed by upgrades,
and a `dependencies` workflow now runs pip-audit on every push and every night, because an
advisory can be published against a lock nobody changed. Dependabot opens a pull request for
every newer release, and the pull request runs the whole pipeline.

**And for people who do not use a mouse.** `test_booking_page_accessibility.py` runs axe-core
against WCAG 2.2 AA on every screen — sign-in, a time chosen, the popup, the owner's screen — and
then does what axe cannot: a whole booking and its cancellation from the keyboard alone, checking
where the focus lands after every step, and that every stop on the way shows a ring. Writing it
found that getting from the chosen time to the book button took a Tab for every time of the day —
95 of them — and that closing the popup or cancelling dropped the focus to the top of the page.
The times are now a radio group (one Tab stop, the arrows to move — the left arrow is the next
time, the page reads right to left), and the focus goes to the new booking. The keyboard tests
skip WebKit, with the reason: Safari's Tab skips buttons unless the user turns on keyboard
navigation in macOS, a setting the page cannot change. The same file checks the accessibility
statement Israeli law asks for — one link from every screen, the level, what was checked, the
known limits, the premises and a contact — and the page at 200% zoom. What no test can check —
what a screen reader actually says — is a checklist for a person:
[`docs/screen-reader-checklist.md`](docs/screen-reader-checklist.md), VoiceOver on an iPhone.

**And on a phone.** CI runs every page test three times: on a desktop, on an iPhone in WebKit —
Safari's engine — and on an Android phone. `test_booking_page_mobile.py` also opens three phones of
its own, the 320px iPhone SE among them, and checks what only a phone gets wrong: nothing reaches
past the edge of the screen, everything pressable is big enough for a finger (44px), no field is
small enough for Safari to zoom the page, the popup fits, a booking made by touch, and the owner's
menu that jumps between sections. WebKit found two defects Chromium never shows — Safari drew the
dropdowns itself, 23px tall whatever the CSS said, and let a long service name widen the page
past the screen — so the mutation catalogue has a `ui-webkit` suite: those two mutants survive
every Chromium run.

**A flaky test that was a real bug.** One page test failed once in CI and passed on the retry.
The cause: changing the barber, service or day asks the server again, and the answers can come
back out of order. A late answer for an earlier choice replaced the current one — the date field
said the 8th while the times were today's, and the owner could save one barber's hours onto
another. The page now drops any answer older than the latest request, and
`test_booking_page_late_answers.py` holds the earlier answer back on purpose and releases it
after the current one, so the race happens on every run instead of once in a while.

**Every rule was broken on purpose in the product, one at a time, and each break was
caught.** Two were not the first time: one assertion compared `…00Z` with `…00.000Z` and so
passed whatever the product did, and nothing checked that the listing offers the slot right
after a booking. Both are fixed, and the result is 11 of 11. CI starts the barbershop and
runs these suites on every push.

## Do the tests actually catch anything? — mutation testing

A green suite proves the product passes it. It does not prove the suite would fail if the
product broke: a test can assert nothing and stay green. So `mutants/barber-booking.yml` holds
100 rules of the barbershop broken on purpose — the booking lock, back-to-back slots, closing
time, daylight saving, the 24 hour cutoff, the Hebrew, the popup, the owner's screen, the phone
layout, answers that arrive late — and
for each one, the suite that must notice.

```bash
make mutate          # every mutant, about 25 minutes; prints each one caught or SURVIVED
make mutate ONLY=lock
make mutate-check    # every anchor still matches the product, in seconds
```

`scripts/mutate.py` never edits the product's checkout — running servers read its page from
disk — but exports its last commit to a temporary directory and breaks that copy, on its own
port and database. It runs the unmodified product first and refuses to report if anything is
already red. Nothing it runs reaches the history or the dashboard. CI checks the anchors on
every push and runs the whole catalogue every night. A full run takes about 25 minutes, so it
never holds up a push: new rules get their mutants in the same change, and the nightly run
proves them. A pytest exit code other than pass or fail — a test that could not be collected —
is reported as an error, never counted as a catch.

Building the catalogue found four weaknesses that every green run had hidden: an assertion
that compared `…00Z` with `…00.000Z` and so could never fail, a load test whose race was over
in the first second, an assertion that the server's own wording also satisfied, and a rule —
the slot right after a booking must still be offered — that no test checked at all. Each is in
`docs/pitfalls.md`.

## Adoption, step by step

A realistic schedule for putting this on a real product. Each step ends with something that
works, so you can stop at any point and still be ahead.

### Day 1 — make it run against something real

1. `make install`, then `make api` and `make test`. If the demo passes, your machine is fine
   and any later failure is the product or the config, not the setup.
2. Read `CLAUDE.md` once. It is fifteen minutes and it is the whole contract.
3. Add a block for one real environment in `config/config.json`. Every key is required —
   nothing is guessed:

   ```json
   "qa": {
     "url": "https://qa.yourproduct.com/api",
     "product": "yourproduct",
     "personas": { "owner": "qa-owner", "customer": "qa-customer" },
     "admin_persona": "owner",
     "auth": { "type": "password_token", "path": "/auth/login" },
     "health_path": "/health",
     "test_hooks": false
   }
   ```

   - **`product`** — which suites belong to this environment. Suites are grouped by product
     (`PRODUCT_FOLDERS` in `tests/conftest.py`); another product's suites are not collected.
   - **`personas`** — the roles your tests act as, and the username for each. Name them
     after the product's roles, not the demo's.
   - **`admin_persona`** — the persona with full rights, used for housekeeping (cleanup).
   - **`auth`** — how they log in. Three types are built in: `password_token` (JSON login,
     bearer token), `oauth_password` (Keycloak, Auth0) and `cookie_token` (a session
     cookie). The options for each are at the top of its function in `obj/auth.py`. A
     fourth is one function there.
   - **`health_path`** — any path that answers 2xx when the product is up, or `null`.
   - **`test_hooks`** — **`false` for a real product.** `true` means the product has
     `/_test/reset`, which only the demo does.

4. **Passwords do not go in that file.** Put them in `config/config.local.json`, which git
   ignores, or in environment variables — which is also what CI uses:

   ```bash
   export QA_OWNER_PASSWORD=...
   export QA_CUSTOMER_PASSWORD=...
   ```

   The loader refuses a password in `config/config.json` for anything but this machine.

5. Prove it before writing a single test:

   ```bash
   make env-check ENV=qa
   ```

   It checks the config, the health path and a login for every persona, and says where
   each password came from without printing it. When it says `ready`, the client, the
   config and the credentials work. It logs in and creates nothing, so it is safe anywhere.

### Day 2 — the first real suite

6. Pick the smallest resource in the product. Not the most important one.
7. Copy `obj/resources/items.py`, rename it, set `resource`, keep the builder and the
   action method:

   ```python
   class Customers(Base):
       resource = "customers"

       def create_fake_customer(self, **kwargs):
           return self.create(self.build_customer_payload(**kwargs), persona="admin").assert_ok(201).as_dict
   ```

   `/new-suite customers` writes the class, the fixture and the suite for you.
8. Register it in `obj/__init__.py` and add a fixture in `tests/conftest.py`.
9. Write one happy path and one unhappy path. Assert values, not status codes.
10. Delete `tests/suites/test_order_flow.py`, `test_items_crud.py` and the other demo suites
    now that yours exists.

### Week 1 — make it protect something

11. Wire CI. Add one repository secret per persona, named exactly as the loader looks for
    them — `QA_OWNER_PASSWORD`, `QA_CUSTOMER_PASSWORD` — and set `ENV` on the job:

    ```yaml
    env:
      ENV: qa
      QA_OWNER_PASSWORD: ${{ secrets.QA_OWNER_PASSWORD }}
    ```

    Run `make env-check` as the job's first step, so a wrong secret fails in one line
    instead of as a wall of errors.
12. Check that `tests/unit` still passes. It tests the framework, not the product, so it
    should be green from the first minute and stay that way.
13. Point the bug filer at your tracker: `TRACKER_URL`, `TRACKER_EMAIL`, `TRACKER_TOKEN`,
    `TRACKER_PROJECT`. Run `pytest --file-bugs-dry-run` and read what it would file before
    letting it file anything.
14. Set `NOTIFY_WEBHOOK` if the team wants a channel summary.

### Week 2 — remove the scaffolding

15. Delete `demo_api/`, and the demo UI and LLM suites if the product has no equivalent.
16. Drop `fastapi`, `uvicorn`, and anything else you are not using, from
    `requirements.txt`, then run `scripts/maintenance/relock.sh`.
17. Rename the repo and update the first paragraph of this file.
18. Add the environments you actually deploy to, and confirm `prod` is in the config only
    so the guard can recognise and refuse it.

### What to keep, always

`tests/unit/`, the suite gating, the production guard, the bug filer, the ledgers, the
Makefile and CI. None of it is product-specific, and it is the part that takes weeks to get
right a second time.

## Rules

`CLAUDE.md` holds what this repo enforces: where payloads live, when to assert the maths
instead of a status code, which group a test belongs to, why `xfail` is banned, and why
every helper that writes data must guard production. Claude Code reads it automatically.

---
---

# בעברית

## מה זה

תשתית מוכנה לבדיקות API בפייתון ו-pytest. היא מגיעה עם API קטן לדוגמה, אז הבדיקות רצות
מהרגע שמשכפלים את הריפו. **558 בדיקות, ב-CI בכל push** — 411 על ה-API לדוגמה שבתוך הריפו, בשש
קבוצות, ו-147 על מוצר שני בריפו משלו, [barber-booking-api](https://github.com/DorGodin/barber-booking-api),
שהן מכירות רק דרך הכתובת שלו, ובדיקות המסך שלו רצות על מחשב, על אייפון (WebKit, המנוע של Safari) ועל
אנדרואיד. מעל זה: בדיקות עומס שהספים שלהן מפילים את הפייפליין, ו-**100 מוטציות** —
חוקים של המוצר שנשברים בכוונה, וכל אחד מהם חייב להיתפס על ידי סוויטה מסוימת, בהרצה לילית (`make mutate`).

המטרה: להגיע למקום עבודה חדש ולא לבנות מאפס את מה שלוקח שבועות — שכבת האובייקטים, ניהול
הסביבות, הפרסונות, הגידור של הסוויטות, ההגנה על פרודקשן, פתיחת הבאגים וה-CI.

## איך מתחילים

```bash
make install     # התקנת סביבה
make api         # טרמינל 1 — ה-API על פורט 8000
make test        # טרמינל 2 — הרצת הבדיקות
```

אם אין פייתון על המחשב: `docker compose run --rm tests` מריץ בקונטיינר את כל הקבוצות חוץ
מסוויטת הדפדפן, ו-`docker compose run --rm ui` מריץ אותה.

## שש הקבוצות

| פקודה | מה היא בודקת | כמות |
|---|---|---|
| `make test` | שהמוצר מתנהג נכון | 64 |
| `make unit` | שהתשתית עצמה תקינה. בלי API ובלי רשת | 130 |
| `make edge` | מה קורה כשהקלט שבור | 20 |
| `make security` | שאי אפשר להגיע למה שלא שלך | 22 |
| `make ui` | מה המשתמש רואה בדפדפן | 20 |
| `make llm` | שפיצ׳ר ה-AI לא ממציא נתונים | 41 |

רק `make test` רצה כברירת מחדל. השאר דורשות דגל.

אחרי ריצה:

| פקודה | מה היא מציגה |
|---|---|
| `make report` | הריצה שהסתיימה: ספירה לכל קבוצה, כשלים, דילוגים והבדיקות האיטיות |
| `make dashboard` | כל הריצות וכל האובייקטים שנוצרו, בדף HTML אחד |
| `make trends` | מה נסוג מול ריצות קודמות: קבוצה שהתכווצה, דילוג חדש, כשל חדש |
| `make cleanup ENV=qa` | מה הריצות השאירו על הסביבה. `YES=1` מוחק |
| `make notify-dry` | ההודעה שהייתה נשלחת לערוץ |
| `make env-check ENV=qa` | האם סביבה מוכנה: קונפיג, health, והתחברות של כל תפקיד |
| `make perf-smoke` | משתמש אחד, שניות: האם ה-API עובד בכלל |
| `make perf-load` | מסלול הקריאה תחת עומס מקבילי |
| `make perf-write` | מסלול הכתיבה תחת עומס, כולל בדיקת חישוב הכספים |
| `make perf-spike` / `perf-soak` / `perf-stress` | זינוק פתאומי, החזקה ארוכה, ועלייה מעל הקיבולת |
| `make perf-trends` | האם p95 זחל למעלה מול הרצות עומס קודמות באותה צורה |
| `make perf-barber` | מרוץ ההזמנות של המספרה תחת עומס: אין הזמנה כפולה, אין 5xx, וכל 201 נשמר |

**למה מפרידים.** מפתח שבודק שינוי קטן לא צריך לחכות שדפדפן יעלה. כשהכל רץ תמיד, אנשים
מפסיקים להריץ בכלל.

## מה יש בתיקיות

**`obj/`** — מחלקה אחת לכל משאב ב-API, מעל בסיס CRUD משותף. בניית הפיילואד וה-URL נמצאת
שם, לא בתוך הטסט. זה מה שמקצר כתיבת סוויטה חדשה לדקות.

**`config/`** — בלוק אחד לכל סביבה. בוחרים עם `ENV=qa pytest`. שם סביבה שלא קיים נכשל מיד
ומדפיס אילו סביבות כן קיימות.

**`utils/`** — עזרים לתאריכים, זריעת נתונים, ופתיחת באגים. כל עזר שכותב נתונים חייב לקרוא
ל-`assert_not_prod` בשורה הראשונה, ויש בדיקה שסורקת את הקוד ונכשלת אם שכחת.

**`perf/`** — סקריפטים של k6. הספים שם הם שער שחרור: חריגה מפילה את הפייפליין.

שני דברים שכדאי להכיר. ראשית, יש סקריפט נפרד למסלול הכתיבה, לא רק לקריאה — קריאות אין מה
לקלקל בהן, ולכן בדיקת עומס שרק קוראת לא תמצא את הבאגים שכן כואבים. הסקריפט הזה בודק שוב את
אותו חישוב כספים שהטסטים הרגילים בודקים, בכל איטרציה ובכל רמת עומס: זמן תגובה טוב בזמן
שהסכומים חוזרים שגויים הוא לא הצלחה. שנית, `PROFILE` קובע את צורת העומס — `load`, `spike`,
`soak`, `stress` — כך שאותו סקריפט עונה על ארבע שאלות שונות בלי לגעת בו.

**`data/scenarios/`** — מקרי בדיקה בקבצי CSV ו-JSON. אפשר להוסיף מקרה בלי לכתוב קוד.

## שכבת ה-AI

**חמישה סוכנים**

| סוכן | מה הוא עושה |
|---|---|
| `test-reviewer` | עובר על השינויים ושואל: אם המוצר היה נשבר, הטסט הזה היה נופל? |
| `ticket-verifier` | לוקח כרטיס, בודק מה כבר מכוסה, כותב את מה שחסר ומריץ |
| `flake-hunter` | מריץ טסט מתחלף שוב ושוב ומבדיל בין טסט לא יציב למוצר לא יציב |
| `coverage-mapper` | מסמן כל אנדפוינט כמוכח, נגוע או לא נבדק, ומדרג לפי סיכון |
| `env-doctor` | מאתר למה הסוויטה לא עולה, שכבה אחרי שכבה |

**אחד עשר סקילים**

`write-tests` (לאיזו קבוצה שייך הטסט ומה לבדוק) · `verify-before-claiming` (לא מדווחים על
תוצאה שלא ראית) · `verify-story` (איך מאמתים כרטיס) · `write-bug` (איך כותבים באג) ·
`test-data-strategy` (נתוני בדיקה והגנת prod) · `flaky-test-policy` (מה עושים עם טסט
מתחלף) · `release-readiness` (מה חוסם שחרור) · `plan-test-work` (תכנון שנשמר בקובץ) ·
`commit-and-pr` (הודעות קומיט ותיאורי MR) · `run-report` (קריאת הדוח של הריצה האחרונה) ·
`monitoring` (היסטוריית ריצות ומה כל ריצה יצרה)

**שבע פקודות**

`/new-suite` · `/explore-api` · `/qa-sweep` · `/file-bugs` · `/flake-check` ·
`/coverage-gap` · `/env-doctor`

**הסוכנים לא כותבים לכרטיס בג׳ירה.** הם מנסחים ומציגים, ואדם שולח.

## מה קורה אחרי שהבדיקות רצות

אחרי כל הרצה נשמרים שלושה קבצים בתיקיית `reports/`. אין שרת, אין מסד נתונים, ואין מה
להחזיק חי — פשוט קבצים.

**`last-run.md`** — סיכום ההרצה שהרגע הסתיימה: כמה עברו וכמה נכשלו בכל קבוצה, אילו בדיקות
נכשלו ומה בדיוק נשבר בכל אחת, אילו דולגו ולמה, ואילו היו הכי איטיות.

```bash
make report
```

**`history.jsonl`** — שורה אחת לכל הרצה: מתי היא רצה, על איזו סביבה, ומה היו התוצאות.
הקובץ הזה הוא מה שמאפשר להשוות בין הרצות.

```bash
make trends
```

הפקודה משווה את ההרצה האחרונה לקודמות ומתריעה על שלושה דברים שקל לפספס: **קבוצה שהתכווצה**
(פחות בדיקות רצו מאשר בפעם שעברה — בדרך כלל דגל שנשכח או תיקייה ששונתה), **בדיקה שהפכה
למדולגת**, ו**כשל חדש**. היא גם אומרת אם ההרצה האטה, אבל זה לא חוסם.

**`perf.jsonl`** — שורה אחת לכל הרצת עומס: איזה סקריפט, איזו צורת עומס, כמה משתמשים,
p95 ו-p99, ושלוש ספירות של נכונות (סכומים שגויים, דחיות תקציב, שגיאות 5xx). כל פקודת
`make perf-*` כותבת אליו, גם כשהריצה חצתה סף.

```bash
make perf-trends
```

זה תופס מה שהרצת עומס אחת לא יכולה: **p95 שזוחל למעלה**. עלייה מ-2ms ל-9ms עדיין עוברת
סף של 400ms, אז k6 אומר שהכל תקין. ההיסטוריה לא. היא משווה רק הרצות של אותו סקריפט, אותה
צורת עומס ואותו מספר משתמשים — הרצה גדולה יותר איטית יותר מטבעה, וזו לא נסיגה.

**`artifacts.jsonl`** — כל אובייקט שהבדיקות יצרו: מה נוצר, מה ה-id שלו, על איזו סביבה,
ואיזה טסט יצר אותו.

השורה הזו נרשמת אוטומטית בכל יצירה, כי כל הקריאות ל-API עוברות דרך מקום אחד בקוד. **אף
טסט לא צריך לעשות כלום, ואי אפשר לשכוח.**

זה עונה על שתי שאלות שתמיד עולות כשעובדים על סביבה משותפת:

```bash
make cleanup ENV=qa          # מה הבדיקות השאירו על qa
make cleanup ENV=qa YES=1    # למחוק את זה
```

ואם מישהו שואל "מאיפה הגיעה ההזמנה הזאת" — מחפשים את ה-id בקובץ ורואים איזה טסט יצר אותה.

**`make dashboard`** מרכז את הכל לדף HTML אחד, בלי שום קריאת רשת ובלי להתקין כלום:

| חלק | על מה הוא עונה |
|---|---|
| רגרסיה | האם משהו הורע מול הריצות הדומות הקודמות |
| Pass rate | המגמה לאורך זמן, על סקאלה שמראה גם צניחה של בדיקה אחת |
| הריצה האחרונה לפי קבוצה | איזו קבוצה נשאה את הכשלים |
| הבדיקות שנכשלות הכי הרבה | אלה שאף אחד עוד לא סגר |
| מה נשאר על כל סביבה | כמה נתוני בדיקה יושבים שם, והפקודה שמנקה |
| ריצות ואובייקטים | כל הפירוט שמאחורי הנ״ל |

## פתיחת באגים אוטומטית

כשבדיקה נכשלת, אפשר לפתוח ממנה כרטיס באג — אבל **לא מתוך קוד הבדיקה**. הבדיקה רק בודקת;
ההחלטה לפתוח כרטיס שייכת להרצה, והיא כבויה כברירת מחדל.

```bash
pytest --file-bugs-dry-run   # מראה בדיוק איזה כרטיס היה נפתח, בלי לפתוח
pytest --file-bugs           # פותח כרטיס לכל בדיקה שנכשלה
```

הכרטיס נבנה לפי תבנית הבאג של הצוות — ENV, Precondition, Steps to reproduce, Actual result,
Expected result, Notes — ומתמלא ממה שההרצה באמת יודעת. **צעדי השחזור הם רצף הקריאות שהטסט
עשה בפועל**, לא הוראה להריץ את הסוויטה. הקידומת BE או FE נגזרת ממיקום הטסט.

**אין כפילויות:** כל כרטיס נושא את מזהה הבדיקה. אם אותה בדיקה תיכשל שוב מחר, המערכת תזהה
שכבר קיים כרטיס פתוח ותוסיף לו תגובה במקום לפתוח שני.

הכתובת של ה-tracker והטוקן מגיעים ממשתני סביבה בלבד, אף פעם לא מהריפו.

## התראות לערוץ

```bash
make notify-dry              # מראה את ההודעה בלי לשלוח
pytest --notify              # שולח ל-NOTIFY_WEBHOOK
```

ההודעה כוללת את הסביבה, הספירות, הבדיקות שנכשלו עם השגיאה של כל אחת, וכל ממצא רגרסיה.
עובד מול Slack ו-Teams.

## שימוש בלי Claude Code

כל מה שמחוץ ל-`.claude/` הוא פייתון ו-pytest רגילים. התשתית, הסוויטות, פותח הבאגים,
הדשבורד, הניקוי, הרגרסיה, ההתראות וה-CI — הכל עובד בלי שום AI.

בתיקיית `.claude/` יש שני דברים, ואף אחד מהם לא מריץ כלום:

| מה | בלי Claude Code |
|---|---|
| `CLAUDE.md` | קוראים אותו כמדריך לתורמים. אלה חוקי הריפו, כתובים לבן אדם |
| הסקילים | ספר הנהלים של הצוות: איך מאמתים כרטיס, איך כותבים באג, מה עושים עם טסט מתחלף |
| הסוכנים והפקודות | צ׳קליסטים. `/new-suite` מתאר בדיוק מה ליצור ובאיזה סדר |

**עם עוזר אחר.** מפנים אותו לאותו קובץ. Cursor קורא `.cursorrules`, Copilot קורא
`.github/copilot-instructions.md`, ורובם מקבלים נתיב שמגדירים:

```bash
ln -s CLAUDE.md .cursorrules
```

**בלי עוזר בכלל.** מוחקים את `.claude/` ושום דבר לא נשבר. את `CLAUDE.md` כדאי להשאיר —
מי שמצטרף לצוות וקורא אותו לומד איפה יושבים הפיילואדים ולמה `xfail` אסור, וזו בדיוק הסיבה
שהוא קיים גם בשביל סוכן.

---

## מוצר שני: המספרה

הדמו נמצא בתוך הריפו הזה, ולכן זה שהבדיקות עוברות מולו מוכיח פחות ממה שנראה. תשתית יכולה
להישען בשקט על מוצר שגדל לידה. לכן יש מוצר שני:
[barber-booking-api](https://github.com/DorGodin/barber-booking-api), API אמיתי לקביעת תורים
בריפו נפרד. אין לו אף שורת קוד משותפת עם הריפו הזה, ו**אין בו שום "קיצור" לבדיקות**: אין
איפוס ואין דלת אחורית. הסוויטות ב-`tests/barber/` מכירות אותו רק דרך הכתובת שלו.

```bash
# ב-barber-booking-api:   cp .env.example .env && make install && make run-test
make env-check ENV=barber
ENV=barber pytest
```

עם `ENV=barber` נאספות רק הסוויטות של המספרה, ושל הדמו לא. הן רצות על **עותק הבדיקות** של
המספרה בפורט 8101 (`make run-test`), עם מסד נתונים משלו — אף פעם לא על העותק בפורט 8100 שאדם
לוחץ בו, שהן היו קוברות בספרים ושירותים של בדיקות.

מה הן בודקות: הרבה לקוחות שמתחרים על אותו תור (בדיוק 201 אחד, כל השאר 409, אפס 5xx), חפיפות
ותורים צמודים, שעת סגירה ברמת רבע השעה, לקוח בשני כיסאות, חלון ההזמנה, ימי חופש, ביטול מאוחר,
לחיצה כפולה עם `Idempotency-Key`, שינוי מחיר שאסור לו לשנות הזמנות קיימות, מי רואה ומי מורשה
לעשות מה — ושעון קיץ, על המעבר שנופל בתוך חלון ההזמנה, יהיה אשר יהיה.

**וגם מסך ההזמנה, בדפדפן אמיתי.** המספרה מגישה מסך הזמנה בכתובת `/` — בעברית, מימין
לשמאל — והבדיקות ב-`tests/barber_ui/` מפעילות אותו כמו לקוח וכמו בעל המספרה. 89 בדיקות: עשרים על
מסך הניהול (שעות, ימי חופש, ספר חדש, מחירים בשקלים, הסתרת שירות — כל אחת נבדקת גם מהצד של הלקוח),
ארבע על החלון הקופץ
שכל הזמנה עונה בו (ירוק כשהתור נקבע, אדום "השעה כבר תפוסה" כשמישהו הקדים, והוא חוסם את הדף
שמאחוריו), שש על העברית
עצמה (הפריסה מתהפכת, שעות נשארות משמאל לימין, שם באנגלית מבודד בתוך משפט עברי, מחיר בסדר
הישראלי, ואף מילה באנגלית מהשרת על המסך), ובין השאר שני לקוחות שמסתכלים על אותו
תור פנוי והשני מקבל הודעה ברורה שהתור בדיוק נתפס, דפדפן שמכוון לשעון של ניו יורק ועדיין חייב
להציג את השעון של המספרה, לחיצה כפולה שחייבת לשלוח בקשה אחת, ושם שנראה כמו HTML ואסור לו
לרוץ. כדי לראות אותן רצות:

```bash
make ui-barber-watch                    # דפדפן פתוח, במהירות של בן אדם
make ui-barber-watch K="looking"        # רק המרוץ בין שני הלקוחות
make ui-barber-record                   # סרטון ומעקב צעד-אחרי-צעד לכל בדיקה
make ui-barber-mobile                   # כל בדיקות המסך על אייפון (WebKit) ועל אנדרואיד
make ui-barber-journeys                 # רק המסעות מקצה לקצה
```

**וגם מקצה לקצה, ברצף אחד.** כל שאר בדיקות המסך מכינות ספרים, שירותים ותורים דרך ה-API — מהר,
ודבר אחד בכל פעם — ולכן שום דבר שם לא מוכיח שהחלקים מתחברים. `test_journeys.py` לא מכין כלום.
בעל המספרה מוסיף ספר, מקליד לו שעות ושירות עם מחיר, במסך; לקוח נרשם במסך, מקבל בדיוק את השעות
שהשעות האלה מאפשרות, וקובע את האחרונה ביום; הספר מתחבר ומוצא את התור ביומן שלו; הלקוח מבטל,
ולקוח שני מקבל את השעה הזו וקובע אותה. לכל אדם דפדפן משלו. ה-API משמש פעם אחת, בסוף, כדי לבדוק
שמה שהמסכים הראו הוא מה שנשמר. שאר המסעות:

- **מכשיר משותף** — לקוח אחד יוצא והבא נכנס באותו דף פתוח, ולא מוצא שום דבר של הקודם: לא תורים,
  לא שם, ולא שם משתמש או סיסמה שנשארו בטופס. כתיבת המסע גילתה שהיציאה רק הסתירה את המסך, וטופס
  ההרשמה עדיין החזיק את הסיסמה שהלקוח הקודם נרשם איתה. רענון שומר על החיבור, ויציאה לא מתבטלת
  ברענון;
- **מה שבעל המספרה משנה, כפי שכל לקוח רואה אותו** — מחיר חדש מגיע להזמנה הבאה ולא לזו שכבר נקבעה,
  שירות שהוסר כבר לא מוצע אבל התורים שלו נשארים, ותור שהבעלים ביטל מופיע כמבוטל אצל הלקוח והשעה
  שלו מוצעת שוב;
- **יום חופש** סוגר יום, וביטול החופש פותח אותו שוב;
- **פריסה מחדש** — ב-CI המסעות רצים מול ה-Docker image של המספרה, מה שבאמת היה עולה לאוויר. אחד
  מהם קובע תור, מחליף את הקונטיינר בחדש על אותו volume, ובודק שהחשבון, התור והחיבור שרדו. הוכח
  לשני הכיוונים: מול פריסה מחדש שמאבדת את מסד הנתונים, הוא נכשל.

**וגם נגד ניחוש סיסמאות ו-scripts מוזרקים.** במספרה לא הייתה שום הגבלה על ניחוש סיסמאות, ולדף —
ששומר את החיבור במקום שכל script בתוכו יכול לקרוא — לא היה Content-Security-Policy.
`tests/barber/test_login_limits.py` בודק את ההגבלות שיש לה עכשיו: חמש סיסמאות שגויות נועלות חשבון
מהכתובת הזו, גם עם הסיסמה הנכונה; עשרים מכתובת אחת נועלות אותה לכל חשבון; האדם האמיתי אף פעם לא ננעל
ממקום אחר; ושם משתמש שלא קיים נחסם בדיוק כמו שם אמיתי. כל בדיקה שנכשלת בכניסה בכוונה מגיעה מכתובת
משלה (`fresh_address`, נשלחת ב-`X-Forwarded-For`), אחרת כמה הרצות ברצף היו נועלות את המחשב שהבדיקות
רצות ממנו. `test_page_policy.py` בודק שהמדיניות מתירה בדיוק את ה-script וה-style שהדף מגיש, לפי hash;
ובדפדפן, הזמנה שלמה ומסך הבעלים רצים בלי אף הפרה, ו-script שעבר את ה-escaping לא רץ. לכל חוק יש
מוטציה — שלוש עשרה, וכולן נתפסו. `test_sign_out.py` בודק שיציאה מסיימת את החיבור גם בשרת: token
שהועתק לפני היציאה נדחה מיד, ולא בעוד שתים עשרה שעות, והחיבורים האחרים של אותו אדם נשארים. לקוח מחזיק
לכל היותר שני תורים קדימה (`test_booking_cap.py`, כולל חמש הזמנות שנשלחות בבת אחת כשיש מקום לאחת),
ומכתובת אחת נפתחים לכל היותר חמישה חשבונות בשעה (`test_signup_limits.py`), כי עוד חשבונות הם הדרך לעקוף
את הראשון. כל לקוח שהבדיקות יוצרות, וכל דפדפן שהן פותחות, מגיע מכתובת משלו, כמו טלפונים של אנשים שונים.

**וגם התלויות עצמן.** pip-audit לא הורץ אף פעם על אף אחד מהריפואים. ההרצה הראשונה מצאה שבע פגיעויות
ידועות ב-starlette של המספרה — ביניהן בניית כתובת לפי כותרת Host — ועוד ב-pytest וב-requests. כולן
תוקנו בשדרוג, ו-workflow בשם `dependencies` מריץ עכשיו pip-audit בכל push ובכל לילה, כי פגיעות
יכולה להתפרסם על נעילה שאף אחד לא שינה. Dependabot פותח pull request לכל גרסה חדשה, וה-pull request
מריץ את כל הפייפליין.

**וגם בשביל מי שלא משתמש בעכבר.** `test_booking_page_accessibility.py` מריץ axe-core מול WCAG 2.2 AA
על כל מסך — כניסה, שעה שנבחרה, החלון הקופץ ומסך הבעלים — ואז עושה את מה ש-axe לא יכול: הזמנה שלמה
וביטול שלה מהמקלדת בלבד, עם בדיקה לאן עובר המיקוד אחרי כל צעד, ושלכל עצירה בדרך יש מסגרת מיקוד
גלויה. כתיבת הבדיקות גילתה שכדי להגיע מהשעה שנבחרה לכפתור ההזמנה צריך היה Tab על כל שעה ביום —
95 כאלה — ושסגירת החלון הקופץ או ביטול הפילו את המיקוד לראש הדף. עכשיו השעות הן קבוצת radio (עצירת
Tab אחת, והחצים כדי לזוז — החץ השמאלי הוא השעה הבאה, כי הדף מימין לשמאל), והמיקוד עובר להזמנה
החדשה. בדיקות המקלדת מדלגות על WebKit, עם הסיבה: ה-Tab של Safari מדלג על כפתורים אלא אם המשתמש הפעיל
ניווט מקלדת בהגדרות של macOS, הגדרה שהדף לא יכול לשנות. אותו קובץ בודק את הצהרת הנגישות שהחוק
בישראל דורש — קישור אחד מכל מסך, רמת הנגישות, מה נבדק, המגבלות הידועות, נגישות המקום ופרטי קשר — ואת
הדף בהגדלה של 200%. את מה ששום בדיקה לא יכולה לבדוק — מה קורא מסך באמת משמיע — מכסה רשימת בדיקה לאדם:
[`docs/screen-reader-checklist.md`](docs/screen-reader-checklist.md), VoiceOver באייפון.

**וגם בטלפון.** ה-CI מריץ כל בדיקת מסך שלוש פעמים: על מחשב, על אייפון ב-WebKit — המנוע של Safari —
ועל אנדרואיד. בנוסף, `test_booking_page_mobile.py` פותח שלושה טלפונים משלו, ביניהם האייפון SE ברוחב
320px, ובודק את מה שרק טלפון מקלקל: ששום דבר לא חורג מקצה המסך, שכל מה שלוחצים עליו גדול מספיק
לאצבע (44px), ששום שדה לא קטן מספיק כדי ש-Safari יגדיל את הדף, שהחלון הקופץ נכנס במסך, קביעת תור
בנגיעה, ותפריט הקפיצה של הבעלים. WebKit מצא שני פגמים ש-Chromium לא מראה לעולם — Safari צייר את
הרשימות הנפתחות בעצמו, בגובה 23px בלי קשר ל-CSS, ונתן לשם שירות ארוך להרחיב את הדף מעבר למסך —
ולכן בקטלוג המוטציות יש סוויטה `ui-webkit`: שתי המוטציות האלה שורדות כל הרצה ב-Chromium.

**בדיקה מהבהבת שהייתה באג אמיתי.** בדיקת מסך אחת נכשלה פעם אחת ב-CI ועברה בהרצה הבאה. הסיבה:
כל החלפה של ספר, שירות או יום שואלת את השרת מחדש, והתשובות יכולות לחזור בסדר אחר. תשובה מאוחרת
לבחירה קודמת החליפה את הנוכחית — בשדה התאריך היה כתוב 8 בחודש והשעות היו של היום, ובעל המספרה
היה יכול לשמור שעות של ספר אחד על ספר אחר. עכשיו הדף זורק כל תשובה שישנה מהבקשה האחרונה, ו-
`test_booking_page_late_answers.py` מעכב בכוונה את התשובה הקודמת ומשחרר אותה אחרי הנוכחית, כך
שהמרוץ קורה בכל הרצה ולא רק מדי פעם.

**כל חוק נשבר בכוונה במוצר, אחד אחרי השני, וכל שבירה נתפסה.** שתיים לא נתפסו בפעם הראשונה:
בדיקה אחת השוותה `…00Z` ל-`…00.000Z` ולכן עברה בלי קשר למה שהמוצר עשה, ושום בדיקה לא וידאה
שהרשימה מציעה את התור שמיד אחרי הזמנה. שתיהן תוקנו, והתוצאה 11 מתוך 11. ה-CI מרים את המספרה
ומריץ את הסוויטות האלה בכל push.

## הבדיקות באמת תופסות משהו? — בדיקות מוטציה

סוויטה ירוקה מוכיחה שהמוצר עובר אותה. היא לא מוכיחה שהיא תיכשל אם המוצר יישבר: בדיקה יכולה לא
לבדוק כלום ולהישאר ירוקה. לכן `mutants/barber-booking.yml` מחזיק 100 חוקים של המספרה שנשברים בכוונה —
הנעילה של ההזמנה, תורים צמודים, שעת הסגירה, שעון קיץ, 24 השעות, העברית, החלון הקופץ, מסך הבעלים,
הפריסה בטלפון, תשובות שמגיעות באיחור —
ולכל אחד, הסוויטה שחייבת לשים לב.

```bash
make mutate          # כל המוטציות, כ-25 דקות; מדפיס כל אחת שנתפסה או שרדה
make mutate ONLY=lock
make mutate-check    # כל עוגן עדיין מתאים למוצר, בשניות
```

`scripts/mutate.py` אף פעם לא עורך את הקוד של המוצר — שרתים שרצים קוראים ממנו את הדף — אלא מייצא
את ה-commit האחרון לתיקייה זמנית ושובר את העותק, על פורט ומסד נתונים משלו. קודם הוא מריץ את המוצר
התקין, ומסרב לדווח אם משהו כבר אדום. שום דבר שהוא מריץ לא נרשם בהיסטוריה או בדשבורד. ה-CI בודק את
העוגנים בכל push ומריץ את כל הרשימה כל לילה. ריצה מלאה לוקחת כ-25 דקות, ולכן היא אף פעם לא מעכבת
push: לחוקים חדשים כותבים מוטציות באותו שינוי, והריצה הלילית מוכיחה אותן. קוד יציאה של pytest שאינו
הצלחה או כישלון — בדיקה שלא נאספה — מדווח כשגיאה, ואף פעם לא נספר כתפיסה.

בניית הרשימה מצאה ארבע חולשות שכל ריצה ירוקה הסתירה: השוואה בין `…00Z` ל-`…00.000Z` שלא הייתה
יכולה להיכשל אף פעם, בדיקת עומס שהמרוץ שלה נגמר בשנייה הראשונה, בדיקה שגם הניסוח של השרת עצמו
סיפק אותה, וחוק — התור שמיד אחרי הזמנה חייב להמשיך להיות מוצע — ששום בדיקה לא בדקה. כל אחת מהן
ב-`docs/pitfalls.md`.

## איך מטמיעים, שלב אחרי שלב

לוח זמנים מציאותי להטמעה על מוצר אמיתי. כל שלב נגמר במשהו שעובד, אז אפשר לעצור בכל נקודה
ועדיין להיות ברווח.

### יום 1 — שיירוץ מול משהו אמיתי

1. `make install`, ואז `make api` ו-`make test`. אם הדמו עובר, המחשב שלך תקין — וכל כשל
   מאוחר יותר הוא המוצר או הקונפיג, לא ההתקנה.
2. לקרוא את `CLAUDE.md` פעם אחת. רבע שעה, וזה כל החוזה.
3. להוסיף בלוק לסביבה אמיתית אחת ב-`config/config.json`. כל המפתחות חובה — שום דבר לא
   מנוחש:

   ```json
   "qa": {
     "url": "https://qa.yourproduct.com/api",
     "product": "yourproduct",
     "personas": { "owner": "qa-owner", "customer": "qa-customer" },
     "admin_persona": "owner",
     "auth": { "type": "password_token", "path": "/auth/login" },
     "health_path": "/health",
     "test_hooks": false
   }
   ```

   - **`product`** — אילו סוויטות שייכות לסביבה הזו. הסוויטות מחולקות לפי מוצר
     (`PRODUCT_FOLDERS` ב-`tests/conftest.py`), וסוויטות של מוצר אחר לא נאספות.
   - **`personas`** — התפקידים שהבדיקות פועלות בשמם, ושם המשתמש של כל אחד. לקרוא להם לפי
     התפקידים במוצר, לא לפי הדמו.
   - **`admin_persona`** — התפקיד עם ההרשאות המלאות, שמשמש לתחזוקה (ניקוי).
   - **`auth`** — איך הם מתחברים. יש שלושה סוגים מובנים: `password_token` (התחברות ב-JSON
     וטוקן), `oauth_password` (Keycloak, Auth0) ו-`cookie_token` (עוגיית סשן). האפשרויות של
     כל סוג כתובות בראש הפונקציה שלו ב-`obj/auth.py`. סוג רביעי זו פונקציה אחת שם.
   - **`health_path`** — כתובת שעונה 2xx כשהמוצר למעלה, או `null`.
   - **`test_hooks`** — **`false` במוצר אמיתי.** `true` אומר שיש למוצר `/_test/reset`,
     ורק לדמו יש.

4. **סיסמאות לא נכנסות לקובץ הזה.** שמים אותן ב-`config/config.local.json`, ש-git מתעלם
   ממנו, או במשתני סביבה — וזה גם מה שה-CI משתמש בו:

   ```bash
   export QA_OWNER_PASSWORD=...
   export QA_CUSTOMER_PASSWORD=...
   ```

   הטוען מסרב לסיסמה ב-`config/config.json` לכל כתובת שהיא לא המחשב הזה.

5. להוכיח שזה עובד, לפני שכותבים טסט אחד:

   ```bash
   make env-check ENV=qa
   ```

   הפקודה בודקת את הקונפיג, את כתובת ה-health, והתחברות של כל תפקיד — ואומרת מאיפה כל
   סיסמה הגיעה, בלי להדפיס אותה. כשהיא אומרת `ready`, הקליינט, הקונפיג והאישורים עובדים.
   היא רק מתחברת ולא יוצרת כלום, אז אפשר להריץ אותה בכל סביבה.

### יום 2 — הסוויטה האמיתית הראשונה

6. לבחור את המשאב **הכי קטן** במוצר. לא את הכי חשוב.
7. להעתיק את `obj/resources/items.py`, לשנות שם, להגדיר `resource`, ולשמור על הבנאי ועל
   מתודת הפעולה:

   ```python
   class Customers(Base):
       resource = "customers"

       def create_fake_customer(self, **kwargs):
           return self.create(self.build_customer_payload(**kwargs), persona="admin").assert_ok(201).as_dict
   ```

   הפקודה `/new-suite customers` כותבת את המחלקה, את ה-fixture ואת הסוויטה.
8. לרשום אותו ב-`obj/__init__.py` ולהוסיף fixture ב-`tests/conftest.py`.
9. לכתוב מסלול מוצלח אחד ומסלול כושל אחד. לבדוק ערכים, לא קודי סטטוס.
10. למחוק את סוויטות הדמו ברגע שיש לך משלך.

### שבוע 1 — שהתשתית תתחיל להגן

11. לחבר CI. להוסיף secret אחד לכל תפקיד, בשם המדויק שהטוען מחפש — `QA_OWNER_PASSWORD`,
    `QA_CUSTOMER_PASSWORD` — ולהגדיר `ENV` ב-job:

    ```yaml
    env:
      ENV: qa
      QA_OWNER_PASSWORD: ${{ secrets.QA_OWNER_PASSWORD }}
    ```

    להריץ `make env-check` כצעד הראשון ב-job, כדי ש-secret שגוי ייכשל בשורה אחת ולא בקיר
    של שגיאות.
12. לוודא ש-`tests/unit` עדיין עובר. הוא בודק את התשתית ולא את המוצר, אז הוא אמור להיות
    ירוק מהדקה הראשונה ולהישאר כזה.
13. לחבר את פותח הבאגים ל-tracker: `TRACKER_URL`, `TRACKER_EMAIL`, `TRACKER_TOKEN`,
    `TRACKER_PROJECT`. **להריץ `pytest --file-bugs-dry-run` ולקרוא מה הוא היה פותח** לפני
    שנותנים לו לפתוח משהו.
14. להגדיר `NOTIFY_WEBHOOK` אם הצוות רוצה סיכום בערוץ.

### שבוע 2 — להוריד את הפיגומים

15. למחוק את `demo_api/`, ואת סוויטות ה-UI וה-LLM אם אין להן מקבילה במוצר.
16. להוריד מ-`requirements.txt` את `fastapi`, `uvicorn` וכל מה שלא בשימוש, ואז להריץ
    `scripts/maintenance/relock.sh`.
17. לשנות את שם הריפו ואת הפסקה הראשונה בקובץ הזה.
18. להוסיף את הסביבות האמיתיות, ולוודא ש-`prod` נמצא בקונפיג **רק** כדי שההגנה תזהה אותו
    ותסרב.

### מה שומרים תמיד

`tests/unit/`, גידור הסוויטות, הגנת ה-prod, פותח הבאגים, הלדג׳רים, ה-Makefile וה-CI. שום
דבר מזה לא תלוי במוצר, וזה החלק שלוקח שבועות לבנות נכון בפעם השנייה.

## הכללים

`CLAUDE.md` מרכז את מה שהריפו אוכף: איפה נמצאים הפיילואדים, מתי בודקים את החשבון ולא רק את
קוד הסטטוס, לאיזו קבוצה שייך כל טסט, למה `xfail` אסור, ולמה כל עזר שכותב נתונים חייב הגנת
prod. Claude Code קורא את הקובץ הזה אוטומטית.
