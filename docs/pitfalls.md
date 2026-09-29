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
