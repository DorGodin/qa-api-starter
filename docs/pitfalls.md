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
