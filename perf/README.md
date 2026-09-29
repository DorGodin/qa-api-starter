# Performance

Two scripts, two jobs.

| Script | Question it answers | When |
|---|---|---|
| `smoke.js` | does the API work at all under one user? | every merge, seconds |
| `load.js` | does the read path hold up under concurrency? | nightly, or before a release |

```bash
make perf-smoke                        # against http://127.0.0.1:8000
make perf-load VUS=25 HOLD=60s         # heavier, longer
BASE_URL=https://staging.example make perf-smoke
```

**Thresholds are the gate, not decoration.** A breached threshold exits non-zero and fails
the pipeline. Put the numbers the product actually promises in `options.thresholds`, and
when a threshold moves, say why in the commit message.

Never point these at production.
