---
name: release-readiness
description: Use when deciding whether a build can ship. Defines which suites must be green, what a threshold breach means, what blocks a release and what merely gets noted.
---

# Release readiness

"All the tests passed" is not a release decision. It is one input.

## What must be green

| Group | Blocks a release? |
|---|---|
| `tests/suites` | **yes** — product behaviour is broken |
| `tests/edge-cases` | **yes** — validation is the contract |
| `tests/unit` | yes, but it blocks the merge, not the release: the framework is wrong |
| `tests/ui` | yes for anything user facing |
| `tests/llm` | yes when the AI feature is in the release |
| `perf/smoke` | **yes** — a breach means the thing is slower than promised |
| `perf/load` | note it; a breach is a conversation, not always a stop |

## Skips are not passes

Count them. A run reporting "120 passed, 14 skipped" has 14 unanswered questions. Before
shipping, know for each skip: which ticket, since when, and what is unproven if you ship
anyway. A skip older than two sprints is a decision nobody made on purpose.

## A threshold breach is a fact, not an opinion

`perf/smoke.js` exits non-zero when p95 crosses the line. That line is what the product
promised. Moving it to make a build pass is a product decision that needs a person's name on
it, said out loud, in the commit message.

## Questions worth asking before you sign off

1. Did anything become skipped or quarantined in this release?
2. Did any threshold move, and who decided?
3. Is there an area with product changes and no new tests? Run `coverage-mapper`.
4. Was anything verified only on a developer's machine?
5. Which of today's failures were re-run until they passed?

## What to write down

Ship or not, and the reason in one sentence. Then the risks you are knowingly accepting.
A release note that lists only what passed is a note nobody can use afterwards when
something breaks in production.
