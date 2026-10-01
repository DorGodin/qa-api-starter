# Claude Code Instructions — qa-api-starter

A starter framework for API test automation. Adopt it by replacing `demo_api/`
and `obj/resources/` with the real product; everything else stays.

## Test Development Guidelines

1. **Business logic and payloads belong in obj classes, not in tests.** Tests call obj
   action methods and assert. Payload construction, URL building and API quirks live in
   the obj class. The only exception is a **validation test** that deliberately sends a
   broken payload — those use `obj.create(data={...})` directly.
2. **No comments or docstrings in test code.** Names carry the meaning. A short
   module-level comment is allowed when the file's purpose is not obvious from its path.
3. **Always verify the numbers.** When a test touches money, quantities or totals, assert
   the arithmetic (`line_total == unit_price * quantity`, `total == sum(lines)`), not just
   the status code. Use the `assert_summary_math()` pattern.
4. **Cover the happy path and the real-world edge cases.** Insufficient budget, double
   submit, wrong role, missing fields, boundary values. Ask what a user can actually do
   in the product, then test that.
5. **No duplicated flows across test files.** A flow used by two suites moves to `utils/`.
6. **Every obj class extends `Base` and sets `resource`**, even when it mostly uses custom
   endpoints.
7. **Relation fields need `expand`.** A GET without it returns empty lists; re-read with
   the right expand before asserting relation state.
8. **Fixtures that hit the API fail fast.** Check the status immediately, raise
   `RuntimeError` (API failure) or `AssertionError` (precondition), name the environment
   and give a remediation. Never return an error body as if it were data.
9. **Data-creating helpers under `utils/functions/` call `assert_not_prod("<name>")` as
   their first statement.** This is enforced by `tests/unit/test_prod_guard.py`, which
   walks the AST of every module in that folder. A genuinely read-only helper goes in
   `READ_ONLY_HELPERS` with a reason in the MR.
10. **`@pytest.mark.xfail` is banned.** A known bug gets `@pytest.mark.skip(reason="TICKET-n: ...")`
    and a test that asserts the *correct* behaviour. Never assert that a bug still exists.

## Suite Groups

| Command | Collects |
|---|---|
| `pytest` | product behaviour suites only |
| `pytest --unit` | + `tests/unit/` — the framework's own tests, mocks only, no API |
| `pytest --edge-cases` | + `tests/edge-cases/` — validation edge cases |
| `pytest --ui` | + `tests/ui/` — Playwright browser suite |
| `pytest --llm` | + `tests/llm/` — LLM evaluation with DeepEval |
| `pytest --security` | + `tests/security/` — access control and exposure |

Default `pytest` is product verification. `tests/unit/` must never need the network, so
the environment check lives in the session fixture and not in `pytest_configure`.

## Contract testing

`tests/suites/test_openapi_contract.py` validates responses against the product's own
OpenAPI document. Asserting field by field covers the fields a test cares about; the spec
covers the rest, so a type that quietly changes elsewhere is still caught.

Validate the response you already have rather than adding a separate call. If an operation
is not in the document, that is the finding — do not work around it.

## Security

`tests/security/` is gated behind `--security` and stays close to what actually happens:

- an id guessed from a URL must not return another account's record
- a valid token for the wrong role is still refused
- **every malformed credential fails identically**, so nothing can be enumerated
- a failed login must not reveal which half was wrong
- hostile strings are stored as data and matched as data, never interpreted
- error bodies name no internal machinery, and responses carry the baseline headers

## Scenario files

`data/scenarios/` holds cases as CSV and JSON so someone who does not write Python can add
one. The test stays a single parametrised function. Any suite loading a file asserts the
file is not empty — a scenario file that shrinks to nothing otherwise reports success while
testing nothing.

## Test isolation

Two resets, and the choice is deliberate.

- `_clean_state` is **module scoped** and autouse. An ordered flow keeps its state across
  the tests that make it up, and one module never inherits another's leftovers.
- `fresh_state` is **function scoped** and opt in. A module whose tests each assert an
  absolute value declares `pytestmark = pytest.mark.usefixtures("fresh_state")`.

A test that asserts "there are seven items" or "the budget is 500" needs the second. A test
that continues a flow the previous test started needs the first. Picking the wrong one
produces failures that look like product bugs, which is why both are named and documented
rather than left to habit.

## Run reports

Every run writes `reports/last-run.md`: counts per group, failures with the assertion that
caused them, skips with their reasons, and the slowest tests. The directory is gitignored.

Two things the report is built to make visible, because both hide easily in terminal
output: **a skip is a question the run did not answer**, and **fewer failures because fewer
tests ran is not an improvement**. Read it with the `run-report` skill.

## What a run leaves behind

Every create goes through `Base.create`, which records the resource, the id, the
environment, the persona and the test into `reports/artifacts.jsonl`. A test does nothing
to opt in, and nothing can forget.

`reports/history.jsonl` gets one line per run, including which tests failed and which were
skipped, so instability can be ranked across runs rather than guessed at. A `--collect-only`
run records nothing — collecting is not running, and recording it would poison every trend
it feeds. `make dashboard` turns both into a single
self-contained HTML page: recent runs with their environment and verdict, and every object
created with its id and the test that made it.

`reports/perf.jsonl` gets one line per load run, written by `scripts/perf_run.py` — every
`make perf-*` target goes through it, and so does CI. Two rules hold it together. A run that
crosses a threshold is still recorded, then the wrapper exits with k6's own code. And
nothing from k6's `setup_data` is ever kept, because on the write path it holds a bearer
token. k6's threshold booleans are TRUE when a threshold was CROSSED; `utils/perf_history.py`
normalises that once, and nothing else should read the raw export. Runs are compared only
by `shape()` — scenario, profile, environment and VUs — and a breached run is never a
baseline.

The ledger records what was **created**, not what still exists. Check the API before
calling something leftover data.

**Store UTC, display local.** Both ledgers hold UTC timestamps. The dashboard converts them
to a local clock and names the zone, so daylight saving comes from the zone database rather
than a hardcoded offset. `DASHBOARD_TZ` pins it when a team wants one shared clock.

## Cleaning up after a run

`make cleanup ENV=qa` lists what the runs created there; `YES=1` deletes it. Nothing is
removed without that, production is refused before anything else happens, and an object
that is already gone is counted rather than treated as an error, so re-running is safe.

## Regression between runs

`make trends` compares the last run against earlier ones **on the same environment with the
same groups** — a targeted run is not a regression against a full one, and a check that
cries wolf gets ignored. It reports a group that shrank, a test that newly became skipped,
a new failure, and a duration that grew. `scripts/trends.py --check` exits non-zero on a
blocking finding, which turns the history from a record into a gate.

Speed is reported but never blocks. It is a conversation, not a gate.

## Notifications

`pytest --notify-dry-run` prints the summary it would post; `--notify` sends it to
`NOTIFY_WEBHOOK`. Both are off by default. The message names the environment, the counts,
the failing tests with their assertions, and any regression finding.

## Secrets

`gitleaks` runs in CI on every push and in the pre-commit hook (`make hooks`). Nothing
secret belongs in the repo: credentials come from the environment, and
`config/config.local.json` is gitignored.

## Bug Filing

Bug filing is a **run level opt-in**, never an inline call in a test. A test asserts; the
run reports.

| Command | Effect |
|---|---|
| `pytest` | files nothing |
| `pytest --file-bugs-dry-run` | prints the exact payload it would send, creates nothing |
| `pytest --file-bugs` | one ticket per failed test |

Steps to reproduce are the calls the failing test actually made, in order, recorded in
`ApiClient.request` and filtered so the harness's own calls — signing a persona in,
resetting the environment — stay out of a report a developer is meant to follow. A suite
that does its work in a browser records nothing there, and the section says so rather than
looking empty.

The description follows the team's bug template — ENV, Precondition, Steps to reproduce,
Actual result, Expected result, Notes — filled with what the run actually knows. The prefix
is derived (`tests/ui` is FE, everything else BE), the steps are the exact command that
reproduces the one failure, and the expected result comes from the test name and is
**labelled as derived**, because a machine's guess must never read as if a person wrote it.

The filer lives in `utils/bug_filing.py`. It deduplicates on the test nodeid embedded in
the description, so a re-run comments on the open ticket instead of opening a second one,
and it routes by the test's folder. Credentials come from `TRACKER_URL`, `TRACKER_EMAIL`,
`TRACKER_TOKEN` and `TRACKER_PROJECT` — never from a tracked file.

Do not add per-assertion filing calls back into test files.

## Agents and commands

`.claude/` carries the workflow, not just the conventions:

| Agents | |
|---|---|
| `test-reviewer` | reviews a diff and asks whether each test would fail if the product broke |
| `ticket-verifier` | maps a ticket's criteria to coverage, writes and runs what is missing |
| `flake-hunter` | reproduces an intermittent failure and separates a flaky test from a flaky product |
| `coverage-mapper` | classifies the API surface as proven, touched or untested and ranks gaps by risk |
| `env-doctor` | finds why a suite will not run, outside in, and stops at the first real failure |

| Skills | |
|---|---|
| `write-tests` | which group a test belongs in, what to assert, what makes it worthless |
| `verify-before-claiming` | never report a result you did not observe |
| `verify-story` | evidence per criterion, and a verdict of PASS, FAIL or UNCERTAIN |
| `write-bug` | how a report is written so product, support and engineering can all act on it |
| `test-data-strategy` | resolve-or-seed, idempotency, isolation scope, the production guard |
| `flaky-test-policy` | what is allowed with a flaky test, and what is banned |
| `release-readiness` | which suites block a release, and why a skip is not a pass |
| `plan-test-work` | a plan written to a file so it survives losing the conversation |
| `commit-and-pr` | messages that say what changed, why, and what was verified |
| `run-report` | turns `reports/last-run.md` into a verdict a person can act on |
| `monitoring` | reads the run history and the ledger of objects the runs created |

| Commands | |
|---|---|
| `/new-suite` | scaffolds a resource, its fixture and its suite |
| `/explore-api` | reads the product source and reports what the tests must send |
| `/qa-sweep` | sweeps the tickets waiting for QA |
| `/file-bugs` | dry run, then file, after an explicit yes |
| `/flake-check` | investigates an intermittent test |
| `/coverage-gap` | maps coverage and ranks what is missing |
| `/env-doctor` | diagnoses a suite that will not start |

Every agent is read-only against the tracker. A comment is drafted and shown; a human
sends it.

## UI tests

`tests/ui/` drives a real browser with Playwright and is gated behind `--ui`.

- **Sign in through the form.** A UI suite that injects a token stops covering the login.
- **Reset state per test.** A browser test reads whatever is on screen, so a leftover row
  from an earlier test changes what `.first` and `.last` point at. This is a function
  scoped fixture here, unlike the module scoped reset the API suites use.
- **Select by `data-testid`.** Never by CSS class or visible text that a copy change breaks.
- **Assert what the user sees**, including the error message. A 402 the user never sees is
  a different defect from a 402 shown as "Not enough budget".
- **Wait on the page's own signal, never on the network.** The barbershop page holds
  `aria-busy` until its screen is current; `BookingPage.settled()` waits for it.
  `wait_for_load_state("networkidle")` returns at once on a page already loaded.
- **Look labels up exactly** (`exact=True`). A substring match forgives a label that wraps
  its field and swallows every option of a select into the field's name.
- **Compare Hebrew text through `plain()`.** The page puts direction isolates around names
  and Intl puts marks inside prices; they are invisible and break a plain comparison.
- **A message for `expect()` goes inside it:** `expect(locator, "why").to_...`. Written
  after it with a comma, it is a tuple whose second half is silently thrown away.

## Mutation testing

`mutants/barber-booking.yml` is the proof that the barbershop suites catch what they claim:
each entry breaks one rule and names the suite (`api`, `ui`, `ui-webkit`, `load`) that must go red.
`ui-webkit` is the phone tests on Safari's engine: a defect only one engine shows gets a mutant on
that engine's suite, or it survives every run and proves nothing.

- **A new rule in a suite gets a mutant in the same change.** A test nobody has seen fail
  has not been shown to test anything.
- **A product change that moves code under an anchor updates the catalogue in the same
  change.** `make mutate-check` (and CI, on every push) fails when an anchor matches zero or
  two places.
- **A survivor is either a missing test or an equivalent mutant** - the rule is protected
  twice and one protection was removed. Prove which by breaking the other one too; never
  delete a survivor to make the report green.
- Runs never touch the product's checkout and never reach the history (`QA_NO_RECORD=1`).

## Page tests on phones

Every barbershop page test runs three ways in CI - desktop, `--browser webkit --device "iPhone 13"`
and `--device "Pixel 7"` (`make ui-barber-mobile`). A fixture that sets the viewport must leave a
`--device` viewport alone; one that does not turns the phone run back into a desktop run without a
single failure. Phone-only rules (a 44px finger, a 16px field, nothing past a 320px edge) live in
`tests/barber_ui/test_booking_page_mobile.py`, which opens its own phones so it runs in every run.

**A flaky page test is a bug report until it is proven otherwise.** Never answer one with a retry
or a longer timeout. Find the order of events that fails, and force it - hold a response back
with `page.route` and release it later (`test_booking_page_late_answers.py`) - so the test fails
on every run until the product is fixed.

## Verifying before committing

Gate a commit on the test command's own exit code - `pytest -q > out.txt; code=$?` - never
on a pipeline. `pytest | tail -1 && git commit` commits a red run: a pipeline's status is its
last command's. Direction characters (U+2066-2069, U+200E/F, U+202A-E) are never typed into
a command or a file: tooling here turns a typed escape into the invisible character itself.
Build them with `chr(0x2068)`; `tests/unit/test_source_hygiene.py` fails on any in source.

## LLM features

`tests/llm/` evaluates an assistant style feature with DeepEval, gated behind `--llm`.

- **Grade deterministically by default.** A judge model costs money, needs a key and is
  itself non-deterministic, which makes it a poor gate for every merge. The metrics in
  `utils/llm_metrics.py` check that every grounded fact survived into the answer, that no
  figure was invented, and that the feature refused what it has no data for. They run
  offline in milliseconds.
- **Cover every phrasing the feature can emit.** A defect in a wording no test happens to
  trigger survives the whole suite. If the feature varies its output, parametrise until
  every variant is exercised.
- **Assert the fact, not the sentence.** The wording may change; the number may not.
- Judged metrics are opt-in, live in their own test so a missing key skips only that test,
  and never stand alone between a wrong number and a user.

## Assistant features are an access control surface

An assistant with access to a user's data is not only a quality question. Cover, for every
such feature:

- **Injection.** A sentence in the input must not widen what the answer covers. Test the
  direct attempt, the role-play, the appended request and the fake system turn.
- **Isolation.** Each persona is answered from its own data. Assert the grounding record,
  not only the sentence.
- **Authentication.** The endpoint refuses an anonymous caller like any other.
- **Refusals carry no figures.** A refusal that names a number has already leaked.

## Performance

`perf/` holds k6 scripts. `smoke.js` answers "does it work under one user" in seconds and
gates every merge; `load.js` puts concurrency on the read path.

Thresholds in `options.thresholds` are the release gate: a breach exits non-zero and fails
the pipeline. They are not numbers somebody eyeballs in a dashboard. When a threshold
moves, say why in the commit message.

## Docker

`docker compose run --rm tests` runs the suites in containers with no local Python. The
`docker` environment block points at `http://api:8000`, the service name, not localhost.

The `tests` service waits on the API's healthcheck rather than sleeping, and the `ui`
service uses the official Playwright image so browsers are already installed. CI builds
the image and runs the compose suite on every push, so the Dockerfile cannot rot quietly.

## Environments

Every environment is one block in `config/config.json`, and every key is required:

| Key | What it declares |
|---|---|
| `url` | where the product is |
| `product` | which suites belong here. `PRODUCT_FOLDERS` in `tests/conftest.py` maps each suite folder to its product; the others are not collected |
| `personas` | persona name -> username. Tests name personas, never usernames |
| `admin_persona` | the persona with full rights - the reset and `make cleanup` act as it. Must be one of `personas` |
| `auth` | how a persona logs in: `{"type": ...}` plus that type's options, see `obj/auth.py` |
| `health_path` | a path that answers any 2xx when the product is up, or `null` for none |
| `test_hooks` | `true` only for a product with `/_test/reset` — the demo. A real product is `false` |

`config/loader.py` reads the block — there is no if/elif ladder and no computed default,
because a default is a guess, and guessing `test_hooks` is how a suite ends up calling a
reset that does not exist. An unknown `ENV` raises and names the known environments; a
missing key raises and names the key; `test_hooks` must be a real boolean, since `"false"`
is truthy. To add an environment, add a block. `config/config.local.json` is gitignored
and overrides blocks locally.

**Passwords never live in code and never travel in the config dict.** `password_for()` in
`config/loader.py` is the only place one is resolved, in this order: `QA_<PERSONA>_PASSWORD`
(what CI sets from secrets), then `passwords` in `config.local.json`, then `passwords` in
`config.json` — and the loader refuses the last unless the URL is this machine or a dotless
container name. A test that must type a password itself uses the `credentials` fixture.

**Each persona logs in on a session of its own, and the shared session refuses cookies.**
A session keeps every cookie a server sets and sends it on every later request; the
personas share one, so a session cookie from the owner's login would ride along on the
customer's calls and a permission test would pass for the wrong persona. Identity travels
only in each persona's own headers. `tests/unit/test_client_isolation.py` proves it.

**Two products, one framework.** The demo lives in this repository; the barbershop lives in
its own and shares no code with this one — the barbershop suites know it only through its
URL and its documented contract (`obj/barber/__init__.py`). `ENV=barber` points at its
**test copy** on 8101 (`make run-test` in that repository), never at 8100, the copy a person
uses: every run leaves barbers, customers, services and bookings the product cannot delete. It
is the standing proof that the framework is portable: CI checks the barbershop out, starts
it, and runs its suites on every push.

**With `test_hooks: false` there is no reset.** Isolation comes from each test creating its
own data, and `make cleanup` removes what the run left. A test that needs a pristine
environment declares `fresh_state`, and on such an environment it is skipped with the
reason — it has nothing honest to assert on shared data.

## DateTime

All datetimes are UTC-aware. Never `datetime.now()`. Use `now_utc()`, `to_iso()`,
`future_date()`, `past_date()`, `date_range()` from `utils/helpers.py`. API payloads are
always serialised with `to_iso()` so they end in `Z`, not `+00:00`.

## Dependencies

`requirements.txt` holds direct dependencies pinned with `==`. `requirements.lock.txt` is
the full resolved set and is what CI installs. To change one: edit `requirements.txt`, run
`scripts/maintenance/relock.sh`, commit both in the same MR. Never edit the lock by hand.

## Naming

Names describe what something does, not the case that triggered it.
`purge_stale_orders.py`, not `fix_bug_1234.py`. Never bake a config value into a name.

## Project Structure

```
obj/            API object layer
  client.py     session, base url, persona credentials, Response wrapper
  auth.py       one login strategy per auth.type
  base.py       standard CRUD every resource inherits
  resources/    the demo product, one module per resource  <- replace these
  barber/       the barbershop product (github.com/DorGodin/barber-booking-api); booking_page.py is its page object
tests/
  conftest.py   env config, session client, personas, product- and flag-gated collection
  suites/       demo product behaviour tests
  barber/       barbershop product tests - collected only when ENV's product is barber-booking
  barber_ui/    the barbershop's booking page in a real browser - that product only, and only with --ui
  unit/         framework's own tests (--unit), whatever the product
  edge-cases/   validation edge cases (--edge-cases)
utils/          helpers.py, functions/ (prod-guarded data seeding), concurrency.py (at_once),
                local_time.py (a product's own clock, DST-safe), assertions.py
config/         config.json per environment + loader
demo_api/       the FastAPI target this repo tests  <- replace with the real product
docs/           api-endpoints.md, test-plans/, pitfalls.md
scripts/        maintenance jobs
```

A new top-level folder must be added to this tree in the same commit that creates it.

## Pitfalls Log

`docs/pitfalls.md` is the running log of process mistakes and the rule that prevents each
one. When you or a teammate hit a confusing terminology issue, a wrong assumption or a
repeated misread, add a dated entry in the same MR as the fix. Repo learnings belong in
the repo, never in per-user AI memory, so every contributor and every fresh session reads
them by default.
