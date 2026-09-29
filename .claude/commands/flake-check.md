---
description: Investigate a test that fails intermittently and name the cause.
---

Investigate $ARGUMENTS with the `flake-hunter` agent.

Reproduce first — alone and with its module — before proposing anything:

```bash
scripts/flake_check.sh <nodeid> 30
scripts/flake_check.sh <nodeid> 30 --module
```

Report the two numbers, the cause, and the fix. Never reach for `xfail` or a retry.
