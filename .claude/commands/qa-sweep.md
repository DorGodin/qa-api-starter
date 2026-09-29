---
description: Sweep the tickets waiting for QA and report where coverage is missing. Read only by default.
---

Sweep the QA queue for $ARGUMENTS (default: tickets assigned to me in a QA status).

## Guards, checked before anything else

1. Abort if `ENV` is `prod`.
2. Warn if the working tree is dirty or the branch is the default branch.
3. Skip any ticket already swept today; say which ones you skipped and why.

## For each ticket

Dispatch the `ticket-verifier` agent once per ticket. Run at most three at a time so the
output stays readable and the API is not hammered.

## Then

Write a digest under `docs/qa-sweeps/<date>.md` containing, per ticket: the criteria, the
coverage before and after, the tests added, and the open findings.

Finish with a table in the chat: ticket, criteria count, gaps found, tests added, result.

## Boundaries

- **Read only against the tracker.** Never comment, transition, assign or create.
- Comments are drafted and shown for a human to send.
- Never commit or push. Leave every file for review.
