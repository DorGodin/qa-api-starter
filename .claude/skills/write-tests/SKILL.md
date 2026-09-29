---
name: write-tests
description: Use whenever adding or changing tests in this repo — "write tests for X", "add coverage", "test this endpoint", "we need a suite for". Decides which group the test belongs in, what to assert, and what would make it worthless.
---

# Write tests

## Pick the group first

| Question the test answers | Folder | Flag |
|---|---|---|
| does the product behave? | `tests/suites/` | default |
| what happens on bad input? | `tests/edge-cases/` | `--edge-cases` |
| is our own framework correct? | `tests/unit/` | `--unit` |
| what does the user see? | `tests/ui/` | `--ui` |
| is the AI feature truthful? | `tests/llm/` | `--llm` |
| can someone reach what is not theirs? | `tests/security/` | `--security` |

Putting a test in the wrong group is the most common mistake here: an automation-framework
test in the default run wastes every developer's time.

## Assert the thing that matters

- **Money and quantities: assert the arithmetic.** `line_total == unit_price * quantity`,
  `total == sum(lines)`. A status code proves the server answered, not that it was right.
- **State: assert the transition and the refusal.** Approved once, and the second attempt
  conflicts.
- **Permissions: assert both sides.** The allowed role succeeds *and* the other is refused.

## Then try to break it

Before you call it done, mutate the product in your head: flip a boolean, drop a field,
return the wrong total. **If the test still passes, it is decoration.** Where it matters,
actually make the change and watch it go red.

## Non-negotiable

Payloads and URLs live in the obj class, never in a test — except a validation test that
deliberately sends a broken payload. No docstrings or comments in test code. No `xfail`.
Decide the isolation scope when you write the first assertion: see `test-data-strategy`.
