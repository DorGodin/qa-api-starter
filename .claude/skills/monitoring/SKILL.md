---
name: monitoring
description: Use when asked what the runs have been doing, what a run left behind, which environment something ran against, or "show me the dashboard", "what did we create on QA", "clean up the test data". Reads the run history and the artifact ledger.
---

# Monitoring runs and what they leave behind

Three files, appended by every run, no service to keep alive:

| File | Holds |
|---|---|
| `reports/last-run.md` | the run that just finished |
| `reports/history.jsonl` | one line per run: when, environment, verdict, counts |
| `reports/artifacts.jsonl` | every entity a run created, with its id and the test that made it |

```bash
make dashboard                              # this machine's clock
DASHBOARD_TZ=Asia/Jerusalem make dashboard  # a fixed zone
```

The ledgers store UTC, which is the only sane thing to store. The dashboard converts to a
local clock and names the zone, so a time on screen is never ambiguous and daylight saving
is handled by the zone database rather than by a hardcoded offset.

## Reading the history

- **A verdict without an environment means nothing.** The same suite passing on `local` and
  failing on `staging` is a deployment finding, not a flaky test.
- **Compare counts across runs of the same group.** A group that shrank silently is the
  quietest way coverage disappears. `NO TESTS RAN` is a failure, not a pass.
- **Watch the duration trend**, not one number. A suite that doubles is a problem long
  before it is a timeout.

## Reading the artifact ledger

Every create goes through `Base.create`, so the ledger records the resource, the id, the
environment, the persona and the test that made it — without a test doing anything.

Use it to answer:

- **What did this run leave on a shared environment?** Group by resource and environment.
- **Which test made this record?** Search the id. This turns "where did this order come
  from" from an hour into a grep.
- **What should be cleaned up?** The ids are there; delete through the obj layer, and only
  on an environment you confirmed is not production.

## Before you act on it

The ledger records what was **created**, not what still exists. A test that deleted its own
record still has a line here. Check the API before reporting something as leftover data.
