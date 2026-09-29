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
