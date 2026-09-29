---
name: write-bug
description: Use when writing a bug report, filing a defect, or drafting a ticket comment that reports test results — including "write this up as a bug", "report this", "draft the ticket". Produces a report that a product manager, a support agent and a developer can all act on.
---

# Write a bug

A bug ticket is read by product and support, not only by engineers.

## The title

`<BE|FE> - <what broke, in words>: <the mismatch>`

> BE - Submitting draws from budget: AssertionError: assert 425.0 == 400.0

The prefix routes the ticket and is derived from where the failure happened, not typed. A
reader should know what is broken without opening it.

## The sections, in this order

1. **ENV(+mobile type)** — the environment, and the device or browser when it matters.
2. **Precondition** — the state that must exist before the steps.
3. **Steps to reproduce** — what a person does, in order, not how to run the test. For an
   API defect that is the sequence of calls; the filer records these automatically and
   leaves out sign-in and environment resets.
4. **Actual result** — the one line that says what went wrong, then the full evidence in a
   code block. The line first, so a product reader sees the point before the trace.
5. **Expected result** — the rule that should hold, in one sentence.
6. **Notes** — attachments, then only what a developer needs to locate the cause.

Skeleton: `docs/templates/bug-report.md`

## Rules

- One idea per sentence.
- Record what was observed, never what you assume caused it.
- Every claim reproducible: steps, request, status, response.
- **Do not set priority.** Impact is a fact; priority is a decision someone else owns.
- Link the failing test by its nodeid.

Before filing, and what belongs where: [reference.md](reference.md)

## Boundary

Drafting is not filing. Show the draft and let a human send it, unless the run was started
with the filing flag.
