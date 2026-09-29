---
description: Scaffold a new test suite for one API resource, following the repo conventions.
---

Create a suite for the resource named in $ARGUMENTS.

1. Read `CLAUDE.md` and one existing module under `tests/suites/` for the house style.
2. If `obj/resources/<resource>.py` does not exist, create it: extend `Base`, set
   `resource`, add a `build_*_payload` builder and a `create_fake_*` action method that
   asserts the status and returns the body.
3. Register the class in `obj/__init__.py` (import, `__all__`) and add a session fixture
   in `tests/conftest.py`.
4. Write `tests/suites/test_<resource>.py` with the happy path AND the real-world edge
   cases: wrong role, missing fields, boundary values, repeated action.
5. Assert the arithmetic wherever money or quantities appear.
6. Run `pytest -q` and paste the real output. Do not report success without it.
