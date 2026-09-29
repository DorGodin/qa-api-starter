---
name: test-data-strategy
description: Use when a test needs data to exist before it can run, or when a fixture creates records on a shared environment. Covers resolve-or-seed, idempotency, isolation, cleanup and the production guard.
---

# Test data

Most suites that become unreliable do not become unreliable in their assertions. They
become unreliable in their setup.

## Resolve, then seed

Never create blindly. Look for what you need first, create only the difference:

```python
def seed_catalogue(items_api, count=3):
    assert_not_prod("seed_catalogue")
    existing = items_api.find(params={"active": True, "limit": count}).content
    if len(existing) >= count:
        return existing[:count]
    ...
```

Two runs must leave the environment in the same state as one. A helper that adds three rows
every run turns a shared environment into a landfill, and a month later someone's filter
test fails because there are now four hundred matching rows.

## Guard production, and let a test prove it

Every public helper under `utils/functions/` calls `assert_not_prod("<name>")` as its
**first statement**. Not a convention — `tests/unit/test_prod_guard.py` walks the AST and
fails the unit suite if one is missing.

`assert`, never an `if` that skips quietly. A misconfigured pipeline that lands on
production must stop loudly, not do nothing and report success.

## Choose the isolation level deliberately

| Scope | Use when |
|---|---|
| per test | UI suites, and any test that reads "the first row" |
| per module | ordered flows that share state on purpose |
| never | read-only suites, where a reset only costs time |

A function scoped reset isolates tests and **destroys the shared state an ordered flow
depends on**. A module scoped reset preserves the flow and lets siblings interfere. Both
are right sometimes; pick on purpose and say why in the fixture's docstring.

## Make data unique, not clever

Use a faker or a run id, never a fixed name like `"test-item"`. Fixed names collide with the
previous run, with a colleague running the same suite, and with a parallel worker.

## Clean up what you can, tolerate what you cannot

Delete what you created when the API allows it. When it does not, make the test tolerate
leftovers instead of asserting an absolute count — assert *your* row is present, not that
there are exactly three.

## Never read another test's data

If a test needs an order, it creates one. Reusing a record another test made couples them
invisibly, and the coupling only shows up when someone runs them in a different order.
