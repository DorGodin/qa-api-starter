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
| `pytest --ui` | + `tests/ui/` — Playwright browser suite |

Default `pytest` is product verification. `tests/unit/` must never need the network, so
the environment check lives in the session fixture and not in `pytest_configure`.

## Bug Filing

Bug filing is a **run level opt-in**, never an inline call in a test. A test asserts; the
run reports.

| Command | Effect |
|---|---|
| `pytest` | files nothing |
| `pytest --file-bugs-dry-run` | prints the exact payload it would send, creates nothing |
| `pytest --file-bugs` | one ticket per failed test |

The filer lives in `utils/bug_filing.py`. It deduplicates on the test nodeid embedded in
the description, so a re-run comments on the open ticket instead of opening a second one,
and it routes by the test's folder. Credentials come from `TRACKER_URL`, `TRACKER_EMAIL`,
`TRACKER_TOKEN` and `TRACKER_PROJECT` — never from a tracked file.

Do not add per-assertion filing calls back into test files.

## Agents and commands

`.claude/` carries the workflow, not just the conventions:

| | |
|---|---|
| `test-reviewer` agent | reviews a diff against this file and asks whether each test would fail if the product broke |
| `ticket-verifier` agent | verifies one ticket: distills the criteria, maps them to coverage, writes and runs the missing tests, drafts a report |
| `/qa-sweep` | sweeps the tickets waiting for QA and reports where coverage is missing |
| `/new-suite` | scaffolds an obj class, fixture and suite for one resource |
| `/explore-api` | reads the product source and reports exactly what the tests must send |
| `/file-bugs` | dry run first, then file, after an explicit yes |
| `verify-story` skill | derives criteria, verifies each one with evidence, assigns PASS / FAIL / UNCERTAIN |
| `write-bug` skill | how a bug report is written so product, support and engineering can all act on it |

Every agent is read-only against the tracker. A comment is drafted and shown; a human
sends it.

## UI tests

`tests/ui/` drives a real browser with Playwright and is gated behind `--ui`.

- **Sign in through the form.** A UI suite that injects a token stops covering the login.
- **Reset state per test.** A browser test reads whatever is on screen, so a leftover row
  from an earlier test changes what `.first` and `.last` point at. This is a function
  scoped fixture here, unlike the module scoped reset the API suites use.
- **Select by `data-testid`.** Never by CSS class or visible text that a copy change breaks.
- **Assert what the user sees**, including the error message. A 402 the user never sees is
  a different defect from a 402 shown as "Not enough budget".

## Performance

`perf/` holds k6 scripts. `smoke.js` answers "does it work under one user" in seconds and
gates every merge; `load.js` puts concurrency on the read path.

Thresholds in `options.thresholds` are the release gate: a breach exits non-zero and fails
the pipeline. They are not numbers somebody eyeballs in a dashboard. When a threshold
moves, say why in the commit message.

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
