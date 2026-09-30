---
name: monitoring
description: Use when asked what the runs have been doing, what a run left behind, which environment something ran against, or "show me the dashboard", "what did we create on QA", "clean up the test data". Reads the run history and the artifact ledger.
---

# Monitoring runs and what they leave behind

Four files, appended by every run, no service to keep alive:

| File | Holds |
|---|---|
| `reports/last-run.md` | the run that just finished |
| `reports/history.jsonl` | one line per run: when, environment, verdict, counts |
| `reports/artifacts.jsonl` | every entity a run created, with its id and the test that made it |
| `reports/perf.jsonl` | one line per load run: scenario, profile, VUs, p95/p99, and the correctness counts |

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

## What the dashboard shows

| Panel | Answers |
|---|---|
| Regression | did anything get worse since the comparable earlier runs |
| Pass rate | the shape over time. The axis covers the observed range, so a one-test dip is visible |
| The last run, by group | which group carried the failures |
| Tests that fail most often | the ones nobody has pinned down — the reason people re-run a pipeline |
| What is left on each environment | how much test data is sitting there, and the command that removes it |
| Load: the latest run of each shape | the last verdict per scenario, profile and VU count, with the correctness counts |
| Load: p95 over time | one line per shape. A climb that never crosses a threshold shows up here first |
| Load: slowest endpoints | where the time goes, from the latest run of each shape |

**A test failing in three runs out of twenty matters more than one failing in twenty of
twenty.** The second is broken and somebody knows; the first is why people stop trusting
the suite.

## Reading the load history

- **Compare like with like.** p95 at 25 users against p95 at 4 users is the load level, not
  a regression. `shape()` in `utils/perf_history.py` is the definition; use it.
- **A fast broken run is not a good run.** The write path returns early when a total is
  wrong, so a run that crossed `wrong_totals` looks quick. Breached runs are never a
  baseline.
- **A p95 rise is a finding, never a gate.** Latency on a shared runner is noisy. What
  blocks is what k6 already judged: a crossed threshold.
- **The correctness counts outrank latency.** `wrong_totals` or `budget_rejections` above
  zero is a product bug found under load, whatever the p95 says.

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
