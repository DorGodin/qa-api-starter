# qa-api-starter

A ready-to-use test automation framework for APIs, in Python and pytest.

Clone it and the tests run immediately — it ships with a small demo API so nothing is
theoretical. Point it at a real product and you keep the parts that normally take weeks to
get right: the object layer, environments, personas, suite gating, the production guard,
bug filing, CI, and a set of AI agents that do QA work with you.

---

## Run it in two minutes

```bash
make install     # virtualenv + locked dependencies
make api         # terminal 1 — the demo API on http://127.0.0.1:8000
make test        # terminal 2 — the product suites
```

| Command | What it runs | Needs the API? |
|---|---|---|
| `make test` | product suites (20 tests) | yes |
| `make unit` | the framework's own tests (31) | no |
| `make edge` | validation edge cases (11) | yes |
| `make ui` | browser suite with Playwright (7) | yes |
| `make llm` | LLM evaluation with DeepEval (10) | yes |
| `make all` | everything except the browser suite | yes |
| `make perf-smoke` | k6 smoke test | yes |
| `make perf-load` | k6 load test | yes |

**79 tests in total.** All of them run on GitHub Actions on every push.

---

## The four test groups, and why they are separate

Running everything all the time sounds tidy and is actually the reason nobody runs
anything. Each group answers a different question and has a different cost, so each has its
own flag.

### `tests/suites/` — does the product behave? *(default, 20 tests)*

The only group that runs with a plain `pytest`. This is what a developer runs before
merging.

| File | Covers |
|---|---|
| `test_order_flow.py` | the full ordering flow: draft → submit → approve, budget drawdown, totals arithmetic, double submit, over-budget rejection, expand behaviour, what a member may see |
| `test_items_crud.py` | create, read, update, delete, filtering, pagination, and that the seeding helper is idempotent |
| `test_auth_and_roles.py` | token issuance, three kinds of bad credentials, garbage and malformed tokens, role boundaries, persona switching |

### `tests/unit/` — is the framework itself correct? *(`--unit`, 31 tests)*

Mocks only. No API, no network, milliseconds. These are off by default because a developer
running the product pipeline has no business running the test framework's own tests.

| File | Covers |
|---|---|
| `test_client_and_base.py` | the response wrapper, the quality of the failure message, `find_first` naming the environment it searched |
| `test_bug_filing.py` | titles, descriptions, routing, deduplication, dry run creating nothing |
| `test_helpers.py` | UTC-aware datetimes, ISO formatting, the lookup cache, the production guard |
| `test_config_loader.py` | a known environment returns its keys, an unknown one names the known ones |
| `test_prod_guard.py` | walks the AST of every data-creating helper and fails if one does not guard production |

### `tests/edge-cases/` — what happens when the input is wrong? *(`--edge-cases`, 11 tests)*

Deliberately broken payloads: empty names, zero and negative prices, missing fields,
quantities out of bounds, unknown and inactive items, requests with no token. These are the
only tests allowed to bypass the object layer and post raw payloads.

### `tests/ui/` — does the user actually see it? *(`--ui`, 7 tests)*

Playwright against a real browser. Signs in through the form rather than injecting a token,
resets state per test, selects by `data-testid`, and asserts what appears on screen —
including that going over budget produces a sentence a person understands, not a silent 402.

### `tests/llm/` — is the assistant telling the truth? *(`--llm`, 10 tests)*

DeepEval against an assistant style endpoint, with metrics that need no judge model and no
API key: every number it was grounded in must survive into the answer, it may not state a
figure that exists nowhere in its data, and it must refuse what it has no data for. It also
covers every phrasing the feature can emit, because a defect in an untriggered wording
survives the whole suite. Judged metrics are documented in `tests/llm/README.md` and are
opt-in.

### `perf/` — does it hold up? *(k6)*

`smoke.js` answers "does it work under one user" in seconds and gates every merge.
`load.js` puts concurrency on the read path. The thresholds in each script are the release
gate: a breach exits non-zero and fails the pipeline.

---

## The AI layer

`.claude/` carries the workflow, not just the conventions. Two agents, two skills, four
commands.

### Agents

**`test-reviewer`** — reviews a diff before you open a merge request. It checks the repo
conventions, then asks the harder question: *if the product broke, would this test fail?*
It mentally flips a boolean, drops a field, returns a wrong total. A test that survives
every mutation is decoration, and it says so.

**`ticket-verifier`** — takes one ticket, distills the acceptance criteria, maps each one to
existing coverage as covered / partly / not covered, writes the missing tests, runs them,
pastes the real output, and drafts a report. It never posts to the tracker and never files a
bug on its own.

### Skills

**`verify-story`** — how a ticket gets verified. Derive the criteria, pick an API, UI or
mixed mode, prove each criterion with evidence on a test environment, and assign
**PASS / FAIL / UNCERTAIN**. UNCERTAIN is a real outcome and is never rounded up to PASS.

**`write-bug`** — how a bug report is written so product, support and engineering can all act
on it. The title names the defect. Plain language first, evidence in a table, one idea per
sentence, no invented priority.

### Commands

| Command | Does |
|---|---|
| `/new-suite <resource>` | scaffolds the object class, the fixture and the suite, then runs it |
| `/explore-api <area>` | reads the product source and reports exactly what the tests must send |
| `/qa-sweep` | sweeps the tickets waiting for QA and reports where coverage is missing |
| `/file-bugs` | dry run first, then file, only after an explicit yes |

Every agent is read-only against the tracker. A comment is drafted and shown; a human sends
it.

---

## Filing bugs from a run

A test asserts. The run reports. Nothing is filed unless you ask for it.

```bash
pytest --file-bugs-dry-run    # prints the exact payloads, creates nothing
pytest --file-bugs            # one ticket per failed test
```

Each ticket embeds the test's id, so re-running a known failure **comments on the open
ticket instead of opening a duplicate**. Tickets route to an owner by the folder the test
lives in. Credentials come from the environment (`TRACKER_URL`, `TRACKER_EMAIL`,
`TRACKER_TOKEN`, `TRACKER_PROJECT`), never from a file in the repo.

---

## Connecting it to your next product

Five steps. The first suite should take a day, not a sprint.

### 1. Remove the demo

```bash
rm -rf demo_api tests/ui
```

Then drop `fastapi`, `uvicorn` and `pytest-playwright` from `requirements.txt` if you are
not testing a UI yet, and run `scripts/maintenance/relock.sh`.

### 2. Point it at the real environments

`config/config.json`, one block per environment:

```json
{
  "staging": { "url": "https://staging.yourproduct.com/api", "admin_user": "...", "member_user": "..." },
  "qa":      { "url": "https://qa.yourproduct.com/api",      "admin_user": "...", "member_user": "..." }
}
```

Select one with `ENV=staging pytest`. An unknown `ENV` fails immediately and lists the ones
that exist. Anything secret goes in `config/config.local.json`, which is gitignored.

### 3. Teach the client how the product authenticates

One method in `obj/client.py`. The demo posts a username and password and keeps a bearer
token; change it to whatever the product does — OAuth, an API key, a session cookie:

```python
def register_persona(self, name, username, password):
    resp = self.request("POST", "/auth/token", persona=None,
                        json={"username": username, "password": password})
    self._tokens[name] = resp.assert_ok(200).as_dict["access_token"]
```

Personas are registered once per run and selected per call, so a test never handles headers.

### 4. Add one resource at a time

Copy `obj/resources/items.py` as the shape. Each class sets `resource`, inherits CRUD from
`Base`, and adds a payload builder plus an action method:

```python
class Customers(Base):
    resource = "customers"

    def build_customer_payload(self, name=None, tier="basic"):
        return {"name": name or fake.company(), "tier": tier}

    def create_fake_customer(self, **kwargs):
        return self.create(self.build_customer_payload(**kwargs), persona="admin").assert_ok(201).as_dict
```

Register it in `obj/__init__.py`, add a fixture in `tests/conftest.py`, and write the suite.
`/new-suite customers` does all of this for you.

### 5. Keep everything else exactly as it is

The suite gating, the production guard, the unit tests, the bug filer, the CI workflow, the
agents and `CLAUDE.md` are product-agnostic on purpose. They are the part that took the
longest to get right and the part you never have to build again.

---

## Conventions

`CLAUDE.md` holds the rules this repo enforces: where payloads live, when to assert
arithmetic instead of a status code, which group a test belongs to, why `xfail` is banned,
how environments and dependencies are managed, and why every helper that writes data must
guard production. Read it before adding a suite. Claude Code reads it automatically.
