---
description: Work out why the suite will not run, from the outside in.
---

Run the `env-doctor` agent.

Check in order and stop at the first real failure: which `ENV`, the config block, whether
the host answers, whether each persona can get a token, dependency conflicts, then the data
the fixtures expect.

If `ENV` is production, stop there and say so. Report the first broken layer and its fix,
and say plainly that everything below it is unknown rather than fine.
