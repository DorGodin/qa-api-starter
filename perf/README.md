# Performance

Three scripts, and four load shapes they can each be run under.

## The scripts — what is being exercised

| Script | Question it answers | When |
|---|---|---|
| `smoke.js` | does the API work at all under one user? | every merge, seconds |
| `load.js` | does the **read** path hold up under concurrency? | nightly, before a release |
| `write_path.js` | does the **write** path hold up — create an order, submit it, balance decremented? | nightly, before a release |

The write path is the one that matters. A read-only load test cannot find the bugs
that hurt, because reads have no state to corrupt. Server side money math, a status
transition and a balance being decremented are what break when two requests arrive
at once, and they all live in `write_path.js`.

So that script does not only time the calls. It re-asserts the same arithmetic the
functional suites assert, on every iteration, at every load level:

| Metric | Fails the run when | Meaning |
|---|---|---|
| `wrong_totals` | > 0 | the server computed a total it would not compute under no load |
| `budget_rejections` | > 0 | a submit was refused for balance, after setup provisioned enough |
| `server_errors` | > 0 | something returned 5xx — a defect at any load level |

**A p95 that looks fine while totals come back wrong is not a pass.**

## The profiles — what shape the load takes

`PROFILE` selects the ramp. The same script answers four different questions.

| Profile | Shape | Question |
|---|---|---|
| `load` (default) | ramp to `VUS`, hold | does it hold up at the traffic we expect? |
| `spike` | `VUS`, jump to 5x for 10s, back down | does it survive a sudden jump, and recover? |
| `soak` | `VUS` held for `HOLD` (default 10m) | does it leak — memory, connections, locks? |
| `stress` | `VUS` doubling to 8x | where does it break, and does it break *cleanly*? |

`stress` is gated differently on purpose: it deliberately pushes past capacity, so
latency and error *rate* stop being defects there — queueing and 429s are the
correct answer to too much traffic. Asserting them anyway would make every stress
run red by design, which trains everyone to ignore it. Under `stress` the only
gates left are the correctness ones above.

## Running

```bash
make perf-smoke                          # one user, seconds
make perf-load                           # read path
make perf-write                          # write path, money math asserted
make perf-spike                          # sudden 5x on the write path
make perf-soak HOLD=30m                  # long hold
make perf-stress VUS=50                  # find the ceiling
make perf                                # smoke + load + write, the pre-release set

make perf-write VUS=25 HOLD=60s          # heavier, longer
BASE_URL=https://staging.example make perf-smoke
```

Knobs: `VUS`, `RAMP`, `HOLD`, `PROFILE`, and for the write path `LINES`,
`QUANTITY`, `ITEM_PRICE`, `BUDGET`.

## Provisioning

`write_path.js` calls `POST /_test/budget` in `setup()` to give the member a balance
sized for the whole run. It has to: every submit decrements the balance, and this API
answers roughly 1,000 orders a second, so the default 500.0 is spent in about seven
seconds. Without provisioning, every later submit returns 402 and the run looks like
a product failure that it is not.

**This is the general lesson, not a quirk of the demo API.** A load test on a money
path has to provision its own test data for the duration. Once it does,
`budget_rejections > 0` stops meaning "we ran out" and starts meaning "the product
charged more than it should have" — which is why it is a hard gate.

## Thresholds

**Thresholds are the gate, not decoration.** A breached threshold exits non-zero
(k6 uses 99) and fails the pipeline. Put the numbers the product actually promises
in `options.thresholds`, and when a threshold moves, say why in the commit message.

The shared gates live in `lib/profiles.js`; per-endpoint latency gates live in each
script, next to the call they describe.

Never point these at production.
