---
name: run-report
description: Use after a test run, or when asked "what happened in that run", "summarise the results", "is this build good". Reads reports/last-run.md and turns it into a verdict a person can act on, instead of a wall of pytest output.
---

# Read the run report

Every run writes `reports/last-run.md`. Read that, not the scrollback.

## What to say, in this order

1. **The verdict and the environment.** "Failed on `qa`" is the headline. A verdict without
   an environment is not a verdict.
2. **What failed**, grouped by cause rather than listed one by one. Six failures from one
   broken fixture are one problem, and saying "six failures" hides that.
3. **What was skipped, and why.** Each skip is a question the run did not answer. Name the
   ticket for each. A skip with no reason recorded is itself a finding.
4. **What is getting slow.** Compare the slowest tests against the previous report. A suite
   that doubles in time is a problem before it is a timeout.

## Judging it

- **All green with skips is not all green.** Say how many questions went unanswered.
- **Fewer failures because fewer tests ran** is not improvement. Check the counts per group
  against what should have been collected.
- **A group missing entirely** usually means a flag was forgotten, not that it passed.

## What not to do

Do not paste the whole report back. Do not call a build good because the exit code was zero
while three groups never ran. Do not guess at a cause from a test name — open the failure.

If something failed, the next step is usually `/flake-check` for an intermittent one or
`env-doctor` when the failures cluster in setup.
