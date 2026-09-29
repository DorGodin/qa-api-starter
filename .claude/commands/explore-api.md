---
description: Read the product's API source and report exactly what the tests must send.
---

Explore the area named in $ARGUMENTS, read-only.

Produce: every endpoint with method, path, auth and role requirements; the exact request
shape; every validation rule and the status code it returns; state transitions; anything
touching money or permissions. Then list what is already covered under `tests/` and what
is not, and give ready-to-run `requests` snippets for the gaps.

Never modify product code. Save the report under `docs/api-coverage/`.
