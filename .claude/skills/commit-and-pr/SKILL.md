---
name: commit-and-pr
description: Use when writing a commit message, opening a merge request or pull request, or summarising a change for review — "commit this", "write the MR description", "what should the commit say". Encodes the style this repo uses.
---

# Commits and merge requests

## The subject line

One line, imperative, under 72 characters, naming what changed for a reader who was not
there:

> Add run-level bug filing, a ticket verifier agent and wider coverage

not *"updates"*, *"fixes"*, or *"WIP"*.

## The body answers three questions

1. **What changed**, in behaviour rather than file names. The diff already lists the files.
2. **Why**, when it is not obvious. A reader in six months has no memory of the discussion.
3. **What was verified**, with the real numbers. "61 passed, 1 skipped" beats "tests pass".

Mention anything that failed on the way and how it was resolved — that is usually the most
useful paragraph in the message.

## Merge request description

Same content, plus:

- **How to check it**: the exact command a reviewer runs.
- **Risk**: what could break, and what is deliberately not covered.
- **Follow-ups**, if any, as their own line so they are not lost.

## Rules

- **Never commit unrun code.** Run the affected suites first and put the output in the
  message.
- One logical change per commit. A commit that adds a suite and refactors the client is two
  commits.
- If a test was skipped or a threshold moved, say so in the message with the reason. A
  silent threshold change is the one thing reviewers cannot catch by reading the diff.
- Never commit secrets, tokens or a `config.local.json`.
