# Claude Code Instructions — qa-api-starter

A starter framework for API test automation. Adopt it by replacing `demo_api/`
and `obj/resources/` with the real product; everything else stays.

## Test Development Guidelines

1. **Business logic and payloads belong in obj classes, not in tests.** Tests call obj
   action methods and assert. Payload construction, URL building and API quirks live in
   the obj class. The only exception is a **validation test** that deliberately sends a
   broken payload — those use `obj.create(data={...})` directly.
2. **No comments or docstrings in test code.** Names carry the meaning. A short
   module-level comment is allowed when the file's purpose is not obvious from its path.
3. **Always verify the numbers.** When a test touches money, quantities or totals, assert
   the arithmetic (`line_total == unit_price * quantity`, `total == sum(lines)`), not just
   the status code. Use the `assert_summary_math()` pattern.
4. **Cover the happy path and the real-world edge cases.** Insufficient budget, double
   submit, wrong role, missing fields, boundary values. Ask what a user can actually do
   in the product, then test that.
5. **No duplicated flows across test files.** A flow used by two suites moves to `utils/`.
6. **Every obj class extends `Base` and sets `resource`**, even when it mostly uses custom
   endpoints.
7. **Relation fields need `expand`.** A GET without it returns empty lists; re-read with
   the right expand before asserting relation state.
8. **Fixtures that hit the API fail fast.** Check the status immediately, raise
   `RuntimeError` (API failure) or `AssertionError` (precondition), name the environment
   and give a remediation. Never return an error body as if it were data.
9. **Data-creating helpers under `utils/functions/` call `assert_not_prod("<name>")` as
   their first statement.** This is enforced by `tests/unit/test_prod_guard.py`, which
   walks the AST of every module in that folder. A genuinely read-only helper goes in
   `READ_ONLY_HELPERS` with a reason in the MR.
10. **`@pytest.mark.xfail` is banned.** A known bug gets `@pytest.mark.skip(reason="TICKET-n: ...")`
    and a test that asserts the *correct* behaviour. Never assert that a bug still exists.

## Suite Groups

| Command | Collects |
|---|---|
| `pytest` | product behaviour suites only |
| `pytest --unit` | + `tests/unit/` — the framework's own tests, mocks only, no API |
| `pytest --edge-cases` | + `tests/edge-cases/` — validation edge cases |

Default `pytest` is product verification. `tests/unit/` must never need the network, so
the environment check lives in the session fixture and not in `pytest_configure`.

## Environments

Every environment is one block in `config/config.json` carrying `url`, `admin_user` and
`member_user`. `config/loader.py` reads all of them — there is no if/elif ladder and no
computed default. An unknown `ENV` raises and names the known environments; a block
missing a key raises and names the key. To add an environment, add a block.
`config/config.local.json` is gitignored and overrides blocks locally.

## DateTime

All datetimes are UTC-aware. Never `datetime.now()`. Use `now_utc()`, `to_iso()`,
`future_date()`, `past_date()`, `date_range()` from `utils/helpers.py`. API payloads are
always serialised with `to_iso()` so they end in `Z`, not `+00:00`.

## Dependencies

`requirements.txt` holds direct dependencies pinned with `==`. `requirements.lock.txt` is
the full resolved set and is what CI installs. To change one: edit `requirements.txt`, run
`scripts/maintenance/relock.sh`, commit both in the same MR. Never edit the lock by hand.

## Naming

Names describe what something does, not the case that triggered it.
`purge_stale_orders.py`, not `fix_bug_1234.py`. Never bake a config value into a name.

## Project Structure

```
obj/            API object layer
  client.py     session, base url, persona tokens, Response wrapper
  base.py       standard CRUD every resource inherits
  resources/    one module per resource  <- replace these
tests/
  conftest.py   env config, session client, personas, gated collection
  suites/       product behaviour tests
  unit/         framework's own tests (--unit)
  edge-cases/   validation edge cases (--edge-cases)
utils/          helpers.py, functions/ (prod-guarded data seeding)
config/         config.json per environment + loader
demo_api/       the FastAPI target this repo tests  <- replace with the real product
docs/           api-endpoints.md, test-plans/, pitfalls.md
scripts/        maintenance jobs
```

A new top-level folder must be added to this tree in the same commit that creates it.

## Pitfalls Log

`docs/pitfalls.md` is the running log of process mistakes and the rule that prevents each
one. When you or a teammate hit a confusing terminology issue, a wrong assumption or a
repeated misread, add a dated entry in the same MR as the fix. Repo learnings belong in
the repo, never in per-user AI memory, so every contributor and every fresh session reads
them by default.
