---
name: verify-story
description: Use when a ticket reaches QA and someone asks to test, verify or QA it. Derives the acceptance criteria, picks a verification mode, proves each criterion against a test environment with real evidence, and produces a report with a verdict per criterion. Never posts to the tracker and never runs against production.
---

# Verify a story

You are verifying whether each requirement actually holds, not whether the code looks
right. Every verdict is anchored to something a reader can check.

## When not to use this

- The ticket is still in development. Verifying unfinished work is theatre.
- The request is for a manual test plan rather than a verdict.
- The ticket is a chore with no observable behaviour.

Say which of these applies and stop, rather than producing a report that proves nothing.

## Step 1 — Derive the criteria

Turn the ticket into a numbered list of testable statements. A criterion is testable when
you can say what you would do and what you would expect to see.

If the ticket has no explicit criteria, derive them and **label them as derived**. If two
readings of the ticket lead to different tests, stop and ask. Never test both readings and
present it as coverage.

## Step 2 — Pick a mode

| Mode | When | Evidence |
|---|---|---|
| API | the behaviour is observable at the API | request and response pairs |
| UI | the behaviour is visual, or only reachable through the interface | screenshots |
| Mixed | the UI action has a server side consequence | both, correlated |

Prefer API mode when either would do. It is faster, it is repeatable, and it proves the
state rather than the rendering of the state.

## Step 3 — Verify, with the environment named

Run against a test environment. **Check `ENV` before the first call and abort if it is
production.** Name the environment in the report; a verdict without an environment is
not a verdict.

Reuse the framework: call the `obj/` action methods rather than hand-rolling requests, so
the verification exercises the same paths the suite does.

## Step 4 — Assign a verdict per criterion

Exactly one of:

- **PASS** — the expected behaviour was observed, and the evidence shows it
- **FAIL** — the behaviour differs from the criterion; record what happened, not what you
  think caused it
- **UNCERTAIN** — you could not build the scenario, or the criterion is ambiguous

**UNCERTAIN is a legitimate outcome and must not be rounded up to PASS.** A criterion you
could not exercise is not a criterion that passed.

## Step 5 — Apply mutation thinking

For each PASS, ask: *if the product silently returned the wrong value here, would my check
have caught it?* If a criterion is about a total, a permission or a state, and your
evidence is a status code, the answer is no. Go back and assert the value.

## Step 6 — Report

Use `docs/templates/verification-report.md`. It leads with a table of criterion, verdict
and evidence, so the first screen answers "did it pass, and what is broken".

Write it for a product reader. Code paths, stack traces and engineering theories belong in
the bug ticket, not here.

## Boundaries

- Never post, comment, transition or assign. Draft it, show it, let a human send it.
- Never file a bug from here. Hand over the prepared payload; see the `write-bug` skill.
- Never claim a run you did not do. Paste the real output.
