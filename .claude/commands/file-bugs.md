---
description: Explain and run the run-level bug filer for the last failing run.
---

Bug filing is a property of the run, never a call inside a test.

1. First run `pytest --file-bugs-dry-run` (adding whatever suite flags apply) and show the
   payloads. Confirm with the user before anything is created.
2. Only after an explicit yes, run the same command with `--file-bugs`.
3. Report what was created and what was commented on. A ticket that already exists for the
   same test gets a comment, never a duplicate.

Required environment: `TRACKER_URL`, `TRACKER_EMAIL`, `TRACKER_TOKEN`, `TRACKER_PROJECT`.
Optional routing: `TRACKER_ASSIGNEE_SUITES`, `TRACKER_ASSIGNEE_EDGE`.

Never put a credential in a file that is tracked by git.
