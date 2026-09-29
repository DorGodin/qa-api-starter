---
name: write-bug
description: Use when writing a bug report, filing a defect, or drafting a ticket comment that reports test results — including "write this up as a bug", "report this", "draft the ticket". Produces a report that a product manager, a support agent and a developer can all act on.
---

# Write a bug

A bug ticket is read by product and support, not only by engineers.

## The title names the defect

> Shipping fee override has no preview, and asking for a preview performs the change

not *"Problem in shipping fees"*. A reader should know what is broken without opening it.

## Structure

1. **TL;DR for product** — two lines, plain words, no jargon where a normal word exists.
2. **Evidence** — a table or a code block, never prose. `sent -> got` rows are read at a
   glance; the same facts in a paragraph are not.
3. **Expected** — one sentence, stated as the rule that should hold.
4. **Notes** — only what a developer needs to locate the cause.

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
