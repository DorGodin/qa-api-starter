---
name: plan-test-work
description: Use before writing tests for anything non-trivial — a new area, a multi-step flow, a ticket with several acceptance criteria — or when asked to "plan the testing for X". Produces a written plan that survives losing the conversation.
---

# Plan test work

A plan that only exists in the conversation is gone the moment the session ends. Write it
to a file.

## Where it goes

`docs/plans/<date>-<topic>.md`, committed with the work.

## What it contains

1. **What we are proving.** One sentence. If you cannot write it, the scope is not clear
   enough to test.
2. **The cases**, as a table: scenario, group (`suites` / `edge-cases` / `ui` / `llm` /
   `security`), what it asserts. Include the unhappy paths — wrong role, missing field,
   boundary value, repeated action.
3. **What already covers some of this.** Search first. Duplicated coverage is worse than
   none, because it doubles the maintenance and hides which test actually guards the rule.
4. **Prerequisites.** Data that must exist, a persona, a feature flag. If a prerequisite
   cannot be created, that is a finding before a line is written.
5. **What we are deliberately not covering**, and why. The most useful section six months
   later.

## Then check the plan

- Does every case assert an outcome rather than a status code?
- Is each one in the right group?
- Would any of them pass if the product were broken?

## Rules

- Plan before code for anything beyond a single obvious test.
- Keep the plan updated as reality changes; a stale plan is misleading in a way no plan is
  not.
- Do not plan in the abstract. Read the product first — `/explore-api` exists for this.
