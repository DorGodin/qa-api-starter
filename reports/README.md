Every run overwrites `last-run.md` here: counts per group, failures, skips with their
reasons, and the slowest tests. The reports themselves are gitignored — this file is not.

| File | Written by | Holds |
|---|---|---|
| `history.jsonl` | every pytest run | one line per run |
| `artifacts.jsonl` | every create through `Base.create` | what the tests made, and on which env |
| `perf.jsonl` | every `make perf-*`, via `scripts/perf_run.py` | one line per load run |
| `dashboard.html` | `make dashboard` | all three, as one page |
