# qa-api-starter

A production-shaped starter for API test automation in Python and pytest.

It ships with a small FastAPI target so the suites actually run the moment you clone it.
Point it at a real product by replacing two folders and you keep everything that takes
weeks to get right: the object layer, the environment handling, the personas, the suite
gating, the production guard and the CI wiring.

## Run it in two minutes

```bash
make install          # venv + locked dependencies
make api              # terminal 1: the demo API on :8000
make test             # terminal 2: product suites
make unit             # the framework's own tests - no API, no network
make all              # everything, including validation edge cases
```

## What is in here

| Layer | What it gives you |
|---|---|
| `obj/client.py` | one session, one base url, personas registered once and selected per call |
| `obj/base.py` | CRUD every resource inherits: `create`, `get_by_id`, `find`, `find_first`, `update_by_id`, `delete_by_id` |
| `obj/resources/` | one class per resource; payload builders and action methods live here, never in a test |
| `tests/conftest.py` | environment config, health check that fails with a remediation, personas, gated collection |
| `tests/unit/` | tests for the framework itself, including an AST check that every data-creating helper guards production |
| `utils/helpers.py` | UTC-aware datetimes, `cached_lookup`, `assert_not_prod` |
| `config/` | one block per environment, no if/elif ladder, local overrides gitignored |
| `.claude/` | conventions, a test reviewer agent and commands that scaffold suites and explore an API |

## Adopting it on a new product

1. Delete `demo_api/` and drop `fastapi` and `uvicorn` from `requirements.txt`.
2. Put the real base urls in `config/config.json`, one block per environment.
3. Adjust `ApiClient.register_persona` to the product's auth (bearer, basic, OAuth, api key).
4. Replace `obj/resources/` with the product's resources, one class each.
5. Keep `tests/unit/`, `utils/`, the suite gating, the prod guard and CI as they are.

The first suite should take a day, not a sprint. That is the whole point.

## Conventions

`CLAUDE.md` holds the rules the repo enforces: where payloads live, when to assert
arithmetic, which suite group a test belongs to, why `xfail` is banned, and how
environments and dependencies are managed. Read it before adding a suite.
