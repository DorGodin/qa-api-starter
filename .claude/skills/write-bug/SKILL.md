---
name: write-bug
description: Use when writing a bug report or a ticket comment that reports test results. Produces a report that a product manager, a support agent and a developer can all act on, with the defect named in the title and the evidence in a table.
---

# Write a bug

A bug ticket is read by product and support, not only by engineers. Write it for that
audience and the developer still gets everything they need.

## The title names the defect, not the area

> Shipping fee override has no preview, and asking for a preview performs the change

not

> Problem in shipping fees

A reader should know what is broken without opening the ticket.

## Structure

1. **TL;DR for product** — two lines, understandable by someone who has never seen the
   endpoint. Plain words. No jargon where a normal word exists.
2. **Evidence** — a table or a code block, never prose. A column of `sent -> got` rows is
   read at a glance; the same facts in a paragraph are not.
3. **Expected** — one sentence, stated as the rule that should hold.
4. **Notes** — only what a developer needs to locate the cause: the endpoint, the field,
   the reason the current behaviour is plausible. Everything already verified as working
   goes in a short bullet list, not a narrative.

`docs/templates/bug-report.md` has the skeleton.

## Rules

- **One idea per sentence.** If a sentence needs a comma splice to carry a second fact,
  split it.
- **Record what was observed, never what you assume.** "The response omitted `total`" is a
  fact. "The serialiser drops it" is a guess unless you read the code, and then it is a
  note, not the report.
- **Every claim reproducible.** Steps, request, status code, response body. A report
  nobody can reproduce will be closed as cannot reproduce, and it will be right.
- **Do not set priority.** Describe the impact and let the people who own the roadmap
  decide. Impact is a fact; priority is a decision.
- **Link the failing test.** If an automated test caught it, name the nodeid. The run level
  filer embeds it automatically, so a re-run comments instead of filing a duplicate.

## Before filing

- Search for an existing open ticket for the same behaviour. A duplicate costs someone an
  hour of triage.
- Confirm it reproduces on a clean state. A bug that only appears after your own earlier
  steps is a different bug, and worth saying so.
- Confirm the environment. A defect that exists only on one environment is a deployment
  finding, and the title should say so.

## Boundaries

Drafting a ticket is not filing one. Show the draft and let a human send it, unless the
run was explicitly started with the filing flag.
