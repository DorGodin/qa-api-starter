# Pitfalls

One dated entry per process mistake: what happened, then the rule that prevents it.

## 2026-09-29 — An autouse reset fixture broke ordered flows

The state reset was `@pytest.fixture(autouse=True)` at function scope, so the order created
by the first test in a flow was deleted before the second test ran, and the failure looked
like a product 404 rather than a fixture bug.

**Rule:** state resets are module scoped. Function scope isolates tests from each other but
also destroys the shared state an ordered flow depends on. If a test needs a pristine
environment, it says so explicitly.

## 2026-09-29 — An absolute assertion on a shared resource

`test_order_over_budget_is_rejected` asserted `budget == 500.0`, which only held when that
test ran first. Earlier tests in the module had already spent from the same budget.

**Rule:** when a resource is shared across a module, assert the *delta*, not the absolute
value. Capture the value before the action and compare against it.

## 2026-09-29 — A dry run that looked like it did nothing

`pytest --file-bugs-dry-run` appeared to print no report. The hook had run correctly; the
report was simply scrolled off because the command was piped through `tail -6` and pytest
prints the failure traceback after it.

**Rule:** before concluding a feature does not work, check how you are reading its output.
Re-run without the filter first.

## 2026-09-29 — UI tests picked the wrong row

Three browser tests failed because they targeted `.first` while new orders render last, and
because state from earlier tests in the module was still on screen. The failures looked like
product bugs; both were test bugs.

**Rule:** UI tests reset state per test, not per module, and never select a row by position
unless the order is part of the assertion. Target the row by its content or its id.

## 2026-09-29 — A mutation survived because a branch was never exercised

The assistant picks its wording from `len(question) % 2`. All three parametrised questions
happened to be odd length, so one of the two phrasings was never produced by any test.
Breaking that branch on purpose did not fail the suite — the tests looked thorough and were
blind to half the feature.

**Rule:** when a feature can emit more than one variant, enumerate the variants and cover
each one. Then break each on purpose and confirm the suite goes red. A suite that stays
green under a deliberate defect is not covering that code.

## 2026-09-29 — "Fails every time" meant the server was not running

`flake_check.sh` reported 3 failures out of 3 on a stable test. The test was fine; the demo
API had been stopped earlier and nothing in the output said so.

**Rule:** before investigating a failing test, confirm the environment answers. This is the
first check in the `env-doctor` agent for exactly this reason, and it is why the health
check in `tests/conftest.py` raises with a remediation instead of letting the failure
surface as an assertion.

## 2026-09-29 — Eight new tests failed on their first run, all for one reason

A pagination suite asserting "there are seven items" and a budget suite asserting "the
budget is 500" were both written under the module scoped reset, so each test inherited
whatever its siblings had created or spent. The failures read as product bugs.

**Rule:** decide the isolation scope when you write the first assertion, not when the suite
goes red. A module whose tests assert absolute values declares
`pytestmark = pytest.mark.usefixtures("fresh_state")`. A module that continues a flow keeps
the module scoped reset.

## 2026-09-29 — Two names for the same field, depending on the branch

An LLM isolation test failed with a `KeyError`. The assistant returned `order_count` when
the user had orders and `orders` when they had none, so any consumer reading the response
broke on the empty case only — the case nobody demos.

**Rule:** a response contract is the same on every branch, including the empty one. When a
test fails because a field is named differently in one path, fix the API, not the test.

## 2026-09-29 — A scenario file found a refusal nobody meant to ship

Moving the assistant's intents into `data/scenarios/assistant_intents.json` immediately
failed on "how much do I have left". The endpoint matched the literal word "budget", so a
perfectly ordinary way of asking was refused. Nothing in the hand-written tests had used
that phrasing.

**Rule:** scenario files are worth adding precisely because the cases nobody would think to
type in Python are the ones that find gaps. When one fails on its first run, check the
product before assuming the file is wrong.

## 2026-09-29 — A unit test that only passed because its input was tidy

`first_line` was supposed to show the assertion that failed. Its unit test fed it
`"E   AssertionError: ..."` and passed. On a real run the report printed `def test_x():`,
because pytest's longrepr starts with the source line and the error is further down, marked
with `E`.

**Rule:** when a helper parses output from another tool, test it with that tool's real
output, pasted verbatim, not with a cleaned-up version of what you assume it looks like.

## 2026-09-29 — A dashboard showing UTC to people who do not work in UTC

Every time on the dashboard was UTC, three hours behind the readers. The instinct is to add
three hours; that breaks twice a year when daylight saving changes.

**Rule:** store UTC, display local, and name the zone on screen. Conversion comes from the
timezone database, never from a hardcoded offset. `DASHBOARD_TZ` pins one shared clock when
a distributed team needs to agree on what "14:20" meant.

## 2026-09-29 — "Steps to reproduce" that told a developer to run the test suite

The filer put the pytest command in Steps to reproduce. That is not a step: it asks a
developer to install and run the suite before they can look at the defect, and it says
nothing about what the product was asked to do.

**Rule:** steps describe what a person does, in order. For an API defect that is the
sequence of calls, which is already passing through `ApiClient.request` and can be recorded
there. The command to rerun the test belongs at the end, as a convenience, not as the steps.

## 2026-09-29 — The gating hook silently disabled --ignore and --deselect

`pytest_ignore_collect` returned `False` for every path outside a gated folder. The hook is
firstresult, so answering False means "definitely collect this" and stops pytest's own
handling of `--ignore`, `--deselect` and `norecursedirs`. It surfaced only because a
regression check failed to notice twelve tests disappearing — the tests had not disappeared,
the flag had been swallowed.

**Rule:** a firstresult hook returns `None` when it has no opinion. Answering with a value
is an instruction, not a shrug, and it overrides everything downstream.

## 2026-09-29 — A regression check that cried wolf on its first run

The first version compared any run against the previous one, so running a single group on
purpose was reported as "a group disappeared". A check that fires on normal behaviour is a
check people learn to ignore.

**Rule:** compare like with like. The baseline is the previous run on the same environment
with the same groups, and a run with no comparable history says so instead of inventing a
finding.

## 2026-09-29 — Every --collect-only run was recorded as a run that found nothing

The dashboard showed six rows of NO TESTS RAN in a row. Nothing had broken: they were the
`--collect-only` commands used while auditing the README. Collecting is not running, so the
report had no outcomes and the verdict was, correctly, that nothing ran — and every one of
those rows then polluted the trend the history feeds.

**Rule:** a session that did not execute tests does not belong in the run history. Check
`config.getoption("collectonly")` before recording anything.

## 2026-09-30 — The load test only read, so it could not have found a money bug

`load.js` hammered `GET /items` and `GET /orders` and nothing else, and it was described as
"does the API hold up under concurrency". It could not answer that question. Reads have no
state to corrupt; everything that actually breaks under concurrent traffic — server side
money math, a status transition, a balance being decremented — lives on the write path,
which no load script touched.

**Rule:** a load test on a product that takes money exercises the write path, and asserts
correctness there, not only latency. `write_path.js` re-checks the same arithmetic the
functional suites check, on every iteration, at every load level. A p95 that looks fine
while totals come back wrong is not a pass. Proven by inflating `line_total` by 1% in the
demo API: the run went red on `wrong_totals=12688` and exited 99.

## 2026-09-30 — The perf smoke test passed because CI always starts with an empty catalogue

`smoke.js` created an item priced 10.0, then ordered whatever `GET /items?limit=1` returned
and asserted the total was 10.0. Those are two different items the moment anything else has
written to the catalogue. It passed in CI only because the API there is fresh, and it failed
the first time it ran locally after another perf script had left items behind — a leftover
priced 2.5 turned "the server computes totals correctly" into "the first row in the
catalogue happens to cost 10".

**Rule:** a perf script is a test and the same state rules apply. Assert against the id you
just created, never against whatever a list endpoint returns first, and check a new script
against a dirty environment before believing it.

## 2026-09-30 — Stress thresholds that are red by design train people to ignore the run

Reusing the load gates (`http_req_failed < 1%`, `p95 < 400ms`) for a stress profile makes
every stress run fail, because the whole point of the profile is to push past capacity.
Queueing and 429s are the correct answer to too much traffic, not defects.

**Rule:** the profile decides which thresholds apply. Under `stress` the only gates left are
the correctness ones — no 5xx, no wrong totals, no unexpected budget rejections. What is a
defect at any load level stays a gate; what is expected at overload does not.

## 2026-09-30 — A load test on a money path has to provision its own balance

The first write-path run reported 3,275 budget rejections and failed. Nothing was broken:
the member balance is 500.0, each order cost 0.06, and this API answers about 1,100 orders a
second, so the balance was spent seven seconds in. Every later submit was a correct 402, and
the run looked like a product failure.

**Rule:** provision the test data for the whole duration in `setup()` — here a
`POST /_test/budget` hook sized for the run. Once provisioning is explicit,
`budget_rejections > 0` stops meaning "we ran out" and starts meaning "the product charged
more than it should have", which is worth failing on. Also: name the constraint in its own
metric. Had budget exhaustion only shown up inside `http_req_failed`, it would have read as
a mysterious 14% error rate instead of pointing straight at the cause.

## 2026-09-30 — Only the Makefile could run the tests

`pytest.ini` had no `pythonpath`, and every Makefile target exported `PYTHONPATH=.` by hand.
So `make test` worked and a bare `pytest` — what anyone does in a fresh clone, and what an
IDE's test runner does — died on `ModuleNotFoundError: No module named 'config'`.

**Rule:** the plain tool has to work. `pythonpath = .` belongs in `pytest.ini`, where pytest,
the IDE and CI all read it, not in a wrapper that only one entry point goes through.

## 2026-09-30 — k6's threshold booleans mean the opposite of what they look like

In `--summary-export`, a threshold reads `{"p(95)<400": false}` on a run where p95 was
1.67ms. `false` means the threshold was **not crossed** — the run passed. Reading it the
intuitive way inverts every verdict. Confirmed against a real breach, not assumed:
`wrong_totals` at 12,034 recorded `{"count==0": true}`.

**Rule:** normalise the polarity once, in `utils/perf_history.py::_breached`, and read the
raw export nowhere else. The unit test builds its fixture with k6's real booleans and a
mutant that flips the polarity fails seven of them.

## 2026-09-30 — k6's summary export writes the setup() return value to disk

`--summary-export` includes `setup_data`. `write_path.js` returns the member's bearer token
from `setup()`, so dumping the export into `reports/` would have written a live credential
into a file that gets attached to messages and uploaded as a CI artifact.

**Rule:** never persist a raw k6 export. The wrapper writes it to a temp file, keeps only
named numeric fields, and deletes the temp file in a `finally`, including when k6 fails.
A unit test asserts the token string never reaches `perf.jsonl`.

## 2026-09-30 — The first perf trend reported a 31% regression that was a bigger run

The dashboard's most prominent line said write-path p95 had risen 31%. The baseline mixed
runs at 2, 3 and 4 VUs, and included a deliberately broken run that returned before calling
submit, so of course it looked fast. Neither is a regression. This is the same "compare like
with like" mistake already logged for the pytest trends on 2026-09-29, repeated one layer
over.

**Rule:** `shape()` — scenario, profile, environment **and VUs** — is the only definition of
"comparable", and the dashboard lines use the same function as the trend check so they can
never disagree. A run that crossed a threshold is never a baseline. Verified the other
direction too: a real 5ms sleep in the API produced a 330% rise that k6 itself called a pass.

## 2026-09-30 — make perf-soak held for 20 seconds, not 10 minutes

The soak profile read `__ENV.HOLD || "10m"`, but every Makefile target passed `HOLD=20s` by
default, so the fallback never fired. The README promised a 10 minute soak; `make -n` showed
`-e HOLD=20s -e PROFILE=soak`. A 20 second soak cannot find a leak.

**Rule:** a default that lives in two places is a default one of them overrides. Each target
now names its own HOLD. Check a make target with `make -n`, not by reading the recipe.

## 2026-09-30 — A dashboard finding that could never go away

Showing the trend check for the latest run of *every* shape meant a one-off local run at an
odd VU count kept its breach on the panel forever, because no later run of that exact shape
would ever replace it. A panel that is permanently red teaches everyone to stop reading it.

**Rule:** the dashboard gives the same answer as `make perf-trends` — the latest run against
its shape. Every shape's last verdict is still on the page, dated, in its own table.

## 2026-09-30 — "pre-commit run --all-files" passed, and the commit was then blocked

`--all-files` means all *tracked* files. Five new files had not been `git add`-ed yet, so
the run that reported every hook green had never looked at them, and the real commit then
failed on four ruff findings and four reformatted files.

**Rule:** `git add` new files before running the hooks as a pre-flight check, or run them on
the staged set the commit will actually contain. A green hook run means nothing about a file
it never saw.

## 2026-09-30 — The adoption guide had never been run against anything but the demo

Pointed at a stand-in product with a login and no test hooks, the framework errored in 62
of 62 modules: `_clean_state` called `/_test/reset` before every module, and only the demo
has that endpoint. Step 5 of the guide said this failure "proves the client, the config
and the credentials work". It proved nothing — the reset failed before any of them was
reached, and hid everything behind it.

**Rule:** an adoption path is verified by walking it against something that is not the
demo. Whether a product exposes test hooks is declared per environment (`test_hooks`,
required, a real boolean), and "it works" is proven by `make env-check`, which logs every
persona in and reports ready — not by reading a failure as a success.

## 2026-09-30 — Seven copies of the demo passwords, and none of them in the config

The config held usernames; the passwords were literals in `tests/conftest.py`,
`tests/ui/conftest.py`, two UI tests, `test_auth_and_roles.py`, `scripts/cleanup.py` and
`perf/lib/session.js`. Using the framework on a real product meant editing code to hold a
real password, one `git add` away from a leaked credential. The guide said "credentials as
secrets"; nothing read a secret.

**Rule:** one resolver — `password_for()` in `config/loader.py` — in a fixed order:
`QA_<PERSONA>_PASSWORD`, then the gitignored `config.local.json`, then `config.json` for
local hosts only, which the loader enforces. Passwords never travel in the config dict,
never become part of a test id, and reach k6 through its environment rather than its argv.

## 2026-09-30 — One requests.Session for every persona leaks cookies between them

A `requests.Session` stores every cookie a server sets and sends it on every later request.
All personas shared one. Demonstrated: after the owner's login set `session=...`, a request
made as the customer went out carrying the owner's cookie. On a cookie-session product that
makes a permission test pass for the wrong persona.

**Rule:** the shared session refuses all cookies, each login runs on a throwaway session,
and identity travels only in each persona's own headers. `test_client_isolation.py` proves
both layers; removing both makes it fail.

## 2026-09-30 — The health check accepted only 200

Restful-Booker's health endpoint answers `201 Created`. A check for exactly 200 declares a
healthy product down.

**Rule:** a health check accepts any 2xx, and a product with no health endpoint declares
`health_path: null` instead of being given a fake one.

## 2026-09-30 — zsh does not split a command held in a variable (again)

`PT=".venv/bin/pytest -c pytest.ini ..."; $PT` ran nothing: zsh treats `$PT` as one word, a
file by that whole name. Three probe runs printed nothing, and one of them was first
misread as a server that had not started yet. This is the fourth time this shell behaviour
has produced a false "nothing happened".

**Rule:** in zsh, never keep a command in a variable. Use a shell function, or write the
command inline. When a run prints nothing, look at the raw output before explaining it.

## 2026-09-30 — Every public commit carried the work email

Every push of this repo was preceded by a scan of the files for employer terms, and every
scan was clean. All 25 commits were still authored with the work email: the global git
identity was the work one, and the author is commit metadata, which a scan of file
contents never reads. The separation the scans existed to protect was broken in the one
place they did not look.

**Rule:** the pre-push scan includes `git log --format='%ae %ce' | sort -u`, not only the
files. Personal repositories take their identity from a conditional include in
`~/.gitconfig` keyed on a `github.com/DorGodin` remote, so a new one is right without
anyone remembering — provided the remote is added before the first commit, since until
then the repository matches nothing and falls back to the global identity. The history
was rewritten with only author and committer changed; content and dates were verified
identical before the force push.

## 2026-09-30 — An assertion that compared two date formats, and so could never fail

`assert build_booking_payload(...)["start"] not in offered` checked that a clashing slot was
not offered. The helper writes `…T09:15:00.000Z`; the product writes `…T09:15:00Z`. The two
strings never match, so the assertion held whatever the product did. It passed its first
run, and every run after — until the product was broken on purpose and this test did not
notice.

**Rule:** compare instants, never their spelling — parse both sides first. A "not in"
assertion also needs its positive twin: prove the value IS offered to someone for whom it
should be, or the negative check may be vacuous.

## 2026-09-30 — 38 of 38 passed on the first run, and two of them tested nothing useful

The barbershop suites were green the first time they ran. Breaking the product one rule at
a time showed two rules the suites could not see: the vacuous assertion above, and back-to-
back slots vanishing from the listing — which no test looked for, because every test checked
the booking and none checked what the listing offered next to one.

**Rule:** a suite's first green run is a hypothesis. Break the product, rule by rule, and
see each break go red before calling the suite done. A rule no mutant can break is a rule the
suite does not test.

## 2026-09-30 — cleanup reported 2300 objects removed from a product that cannot delete

`make cleanup ENV=barber` answered "2300 already gone". Nothing was deleted: the barbershop
has no delete endpoints, `DELETE /customers/{id}` is an unknown path, and an unknown path is
a 404 — which cleanup counted as "already gone".

**Rule:** a 404 does not mean deleted. cleanup reads the product's OpenAPI document, reports
a resource with no `DELETE /{resource}/{id}` as `no delete endpoint` without calling it, and
without a document reports a 404 as `not found`, never as a deletion.

## 2026-09-30 — A unit test broken by an edit, unnoticed until the full run

Changing cleanup to act as `client.config["admin_persona"]` broke its unit test's fake
client, which had no `config`. Only the barbershop suites were being run after that edit, so
the break sat there until the full run surfaced it — along with seven loader tests whose fake
blocks predated the two new required keys.

**Rule:** after changing anything under `utils/`, `scripts/`, `obj/` or `config/`, run
`pytest --unit` before calling the change done — not only the suite the change was for.

## 2026-09-30 — wait_for_load_state("networkidle") on a loaded page waits for nothing

After booking, the page object waited with `wait_for_load_state("networkidle")` before
reading the list of free times. That call waits for a load state, and a page that has
already loaded has already reached it — so it returned at once and the test read the list
before the page refreshed it. It passed on its first run by luck and failed on the next.

**Rule:** wait for the page's own signal, never for a guess about the network. The booking
page holds `aria-busy="true"` while it fetches and `"false"` once what is on screen is
current (a counter, since refreshes overlap), and `BookingPage.settled()` waits for it.
A flaky test is run until it fails and its failure read, never re-run until it passes.

## 2026-09-30 — "The first free time today" races the clock

The late-cancellation tests booked the first free time. The first time can be seconds
away; if a quarter hour ticks over between listing it and booking it, the booking is
refused as in the past, and the test times out waiting for a Cancel button. One run in
fifteen failed with a 35 second duration — a 30 second wait — and it could not be
reproduced in forty more runs, which is exactly what a clock race looks like.

**Rule:** a test that needs "soon" takes the second free time, not the first — at least a
slot's length away, and still inside any cutoff being tested.

## 2026-09-30 — Two mutants survived for reasons that were not bugs, and both taught something

"A double click sends twice" survived when only the page's guard was removed: the button is
also disabled, and either protection alone holds. "The late-cancellation reason is lost"
survived because the test looked for "24 hours", which the API's own fallback text also
says. The first was an equivalent mutant — remove both protections and it is caught. The
second was a weak assertion: the requirement is to tell the customer what to do next, so
the test now looks for "call the shop".

**Rule:** a surviving mutant is either an equivalent one (prove it by breaking what else
protects the behaviour) or an assertion that checks something a second source also
provides. Count on the wire where the screen cannot tell — with one Idempotency-Key per
choice, a second request is answered as a success, so only the request count shows it.

## 2026-09-30 — expect(...).to_contain_text(...), "message" is a tuple

`expect(msg).to_contain_text("call the shop"), "say what to do next"` looked like an
assertion with a message. It is an expression statement: a tuple whose first half runs the
check and whose second half is discarded. The check still ran; the message would never
have been shown. ruff made it visible by wrapping the tuple in parentheses.

**Rule:** Playwright takes the message inside: `expect(locator, "why").to_contain_text(...)`.

## 2026-09-30 — Typed escapes became invisible characters, twice

Twice a `\u2068` typed into a file or a command landed as the real, invisible U+2068 - once
in the barbershop page, once in a test's own sample data. Both were caught by the
source-hygiene test written that same hour, which is the point of having it.

**Rule:** build direction characters with `chr(0x2068)`, never type their escapes into a
file or a command. `tests/unit/test_source_hygiene.py` scans every source file.

## 2026-09-30 — zsh expanded a grep pattern and the search found "nothing"

`grep -rlP '...' --include=*.py …` printed "none". zsh had expanded `*.py` itself, found no
match in the working directory, and grep never searched. A clean result that searched
nothing - the same class of false negative as the unsplit `$PT` earlier today.

**Rule:** quote every glob that belongs to the command, not the shell (`--include='*.py'`),
or do the search in Python. When a check comes back empty, prove it can come back full.
