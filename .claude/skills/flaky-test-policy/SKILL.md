---
name: flaky-test-policy
description: Use when a test fails intermittently, or when deciding what to do with one. Sets what is allowed (fix, skip with a ticket), what is banned (xfail, retries, silent deletion) and how to tell a flaky test from a flaky product.
---

# Flaky tests

A suite people re-run until it passes is not a suite. It is a slot machine.

## First: is the test flaky, or is the product?

Reproduce before deciding. `scripts/flake_check.sh <nodeid> 30` alone, then with its module.

- green alone, red in the module → **order dependence**, a test problem
- red both ways → **the test itself**: timing, shared resource, absolute assertion
- red only occasionally, in both → likely **the product**: a race, a cache, an eventually
  consistent read

The third case is a finding, not a maintenance chore. File it. A product that is
occasionally wrong is occasionally wrong for users too.

## What you may do

1. **Fix it.** Assert a delta instead of an absolute. Wait for a condition instead of a
   duration. Create your own data.
2. **Skip it with a ticket**, when the cause is a confirmed product bug:
   `@pytest.mark.skip(reason="TICKET-n: <one line>")`, filed in the same change, and say
   plainly that coverage is now missing.

## What you may not do

- **`xfail`.** It turns a bug into a green tick, and `strict=True` turns the eventual fix
  into a red pipeline. Banned in this repo, with or without a reason string.
- **Retries.** A retry on a test that catches a real race deletes the evidence.
- **Deleting it because it is annoying.** If the rule it asserts is not a real requirement,
  delete it and say that is why. If it is, the deletion is a coverage loss in disguise.
- **Asserting the bug.** Never write a test that passes because the product is still wrong.

## Quarantine, if you must have one

A quarantined test is skipped, ticketed, and **has an owner and a date**. A quarantine
without those is a graveyard. Review it every sprint; a test that has been quarantined for
two months is either a product bug nobody intends to fix or a test nobody needs.
