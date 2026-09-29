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
| `pytest --llm` | + `tests/llm/` — LLM evaluation with DeepEval |
| `pytest --security` | + `tests/security/` — access control and exposure |

Default `pytest` is product verification. `tests/unit/` must never need the network, so
the environment check lives in the session fixture and not in `pytest_configure`.

## Contract testing

`tests/suites/test_openapi_contract.py` validates responses against the product's own
OpenAPI document. Asserting field by field covers the fields a test cares about; the spec
covers the rest, so a type that quietly changes elsewhere is still caught.

Validate the response you already have rather than adding a separate call. If an operation
is not in the document, that is the finding — do not work around it.

## Security

`tests/security/` is gated behind `--security` and stays close to what actually happens:

- an id guessed from a URL must not return another account's record
- a valid token for the wrong role is still refused
- **every malformed credential fails identically**, so nothing can be enumerated
- a failed login must not reveal which half was wrong
- hostile strings are stored as data and matched as data, never interpreted
- error bodies name no internal machinery, and responses carry the baseline headers

## Scenario files

`data/scenarios/` holds cases as CSV and JSON so someone who does not write Python can add
one. The test stays a single parametrised function. Any suite loading a file asserts the
file is not empty — a scenario file that shrinks to nothing otherwise reports success while
testing nothing.

## Test isolation

Two resets, and the choice is deliberate.

- `_clean_state` is **module scoped** and autouse. An ordered flow keeps its state across
  the tests that make it up, and one module never inherits another's leftovers.
- `fresh_state` is **function scoped** and opt in. A module whose tests each assert an
  absolute value declares `pytestmark = pytest.mark.usefixtures("fresh_state")`.

A test that asserts "there are seven items" or "the budget is 500" needs the second. A test
that continues a flow the previous test started needs the first. Picking the wrong one
produces failures that look like product bugs, which is why both are named and documented
rather than left to habit.

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

| Agents | |
|---|---|
| `test-reviewer` | reviews a diff and asks whether each test would fail if the product broke |
| `ticket-verifier` | maps a ticket's criteria to coverage, writes and runs what is missing |
| `flake-hunter` | reproduces an intermittent failure and separates a flaky test from a flaky product |
| `coverage-mapper` | classifies the API surface as proven, touched or untested and ranks gaps by risk |
| `env-doctor` | finds why a suite will not run, outside in, and stops at the first real failure |

| Skills | |
|---|---|
| `write-tests` | which group a test belongs in, what to assert, what makes it worthless |
| `verify-before-claiming` | never report a result you did not observe |
| `verify-story` | evidence per criterion, and a verdict of PASS, FAIL or UNCERTAIN |
| `write-bug` | how a report is written so product, support and engineering can all act on it |
| `test-data-strategy` | resolve-or-seed, idempotency, isolation scope, the production guard |
| `flaky-test-policy` | what is allowed with a flaky test, and what is banned |
| `release-readiness` | which suites block a release, and why a skip is not a pass |
| `plan-test-work` | a plan written to a file so it survives losing the conversation |
| `commit-and-pr` | messages that say what changed, why, and what was verified |

| Commands | |
|---|---|
| `/new-suite` | scaffolds a resource, its fixture and its suite |
| `/explore-api` | reads the product source and reports what the tests must send |
| `/qa-sweep` | sweeps the tickets waiting for QA |
| `/file-bugs` | dry run, then file, after an explicit yes |
| `/flake-check` | investigates an intermittent test |
| `/coverage-gap` | maps coverage and ranks what is missing |
| `/env-doctor` | diagnoses a suite that will not start |

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

## LLM features

`tests/llm/` evaluates an assistant style feature with DeepEval, gated behind `--llm`.

- **Grade deterministically by default.** A judge model costs money, needs a key and is
  itself non-deterministic, which makes it a poor gate for every merge. The metrics in
  `utils/llm_metrics.py` check that every grounded fact survived into the answer, that no
  figure was invented, and that the feature refused what it has no data for. They run
  offline in milliseconds.
- **Cover every phrasing the feature can emit.** A defect in a wording no test happens to
  trigger survives the whole suite. If the feature varies its output, parametrise until
  every variant is exercised.
- **Assert the fact, not the sentence.** The wording may change; the number may not.
- Judged metrics are opt-in, live in their own test so a missing key skips only that test,
  and never stand alone between a wrong number and a user.

## Assistant features are an access control surface

An assistant with access to a user's data is not only a quality question. Cover, for every
such feature:

- **Injection.** A sentence in the input must not widen what the answer covers. Test the
  direct attempt, the role-play, the appended request and the fake system turn.
- **Isolation.** Each persona is answered from its own data. Assert the grounding record,
  not only the sentence.
- **Authentication.** The endpoint refuses an anonymous caller like any other.
- **Refusals carry no figures.** A refusal that names a number has already leaked.

## Performance

`perf/` holds k6 scripts. `smoke.js` answers "does it work under one user" in seconds and
gates every merge; `load.js` puts concurrency on the read path.

Thresholds in `options.thresholds` are the release gate: a breach exits non-zero and fails
the pipeline. They are not numbers somebody eyeballs in a dashboard. When a threshold
moves, say why in the commit message.

## Docker

`docker compose run --rm tests` runs the suites in containers with no local Python. The
`docker` environment block points at `http://api:8000`, the service name, not localhost.

The `tests` service waits on the API's healthcheck rather than sleeping, and the `ui`
service uses the official Playwright image so browsers are already installed. CI builds
the image and runs the compose suite on every push, so the Dockerfile cannot rot quietly.

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
