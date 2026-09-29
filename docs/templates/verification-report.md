# Verification — <TICKET KEY>: <title>

**Environment:** <env>  ·  **Mode:** API | UI | Mixed  ·  **Date:** <YYYY-MM-DD>

## Verdict

| # | Criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | <testable statement> | PASS | <request/response, screenshot, test name> |
| 2 | <testable statement> | FAIL | <what happened> |
| 3 | <testable statement> | UNCERTAIN | <why it could not be proven> |

Criteria marked *derived* were not written on the ticket.

## What is broken

<Plain language, two or three lines. What a user would experience. Link the bug ticket.>

## Coverage added

| Test | Suite group | Covers |
|---|---|---|
| `tests/suites/...::test_...` | product | criterion 1 |

## Run output

```
<the real pytest output, pasted>
```
