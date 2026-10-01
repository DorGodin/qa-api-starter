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

## The barbershop: `barber/booking_race.js`

Each folder of scripts belongs to one product (`SCRIPT_PRODUCTS` in `scripts/perf_run.py`);
`perf/barber/` is the barbershop's, and running it against another product is refused.

It is a race, kept alive. Every user aims at the same fresh time during a 200ms window,
and the target moves on every window - so the race for a time is run again and again, at
full concurrency, for the whole run. It creates its own barbers, service and customers in
`setup()` and touches nothing else, and it leaves that data behind - which is why `ENV=barber`
is the barbershop's test copy on 8101 (`make run-test`), not the copy anyone uses.

| Gate | Fails the run when |
|---|---|
| `unexpected_status` | anything but a 201 or a clean 409 |
| `server_errors` | any 5xx - on SQLite, that is what an unlocked race looks like |
| `lost_bookings` | a 201 whose booking cannot be read back |
| `double_bookings` | two overlapping confirmed bookings for one barber, checked in the database at the end |
| `barbers_never_booked` | a barber got no booking at all - the run did not test what it claims |

All five are correctness, so they hold under every profile, `stress` included.

**Why the race is kept alive.** The first version drew targets at random from a small
pool. The pool filled in the first second, during the ramp, and every later request was a
refusal - which writes nothing, needs no lock, and cannot race. Against a server with its
booking lock deliberately broken, it **passed**. The rewritten script, against the same
broken server: 144 server errors and 287 unexpected statuses, exit 99. Against the fixed
one: 101 races, 101 winners, 17,270 clean refusals, p95 62ms, no 5xx.

```bash
make perf-barber                       # ENV=barber
make perf-barber PROFILE=stress VUS=50
```

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
run red by design, which trains everyone to ignore it. A script passes its gates to
`thresholds(latency, correctness)` in two groups: under `stress` the latency group is
dropped and the correctness group is kept. Check it with `k6 inspect -e PROFILE=stress`.
The first version returned only `server_errors` under stress and quietly dropped every
correctness gate along with the latency ones.

## Running

```bash
make perf-smoke                          # one user, seconds
make perf-load                           # read path
make perf-write                          # write path, money math asserted
make perf-spike                          # sudden 5x on the write path
make perf-soak                           # 10 minute hold; HOLD=30m for longer
make perf-stress VUS=50                  # find the ceiling
make perf                                # smoke + load + write, the pre-release set

make perf-write VUS=25 HOLD=60s          # heavier, longer
ENV=staging PERF_REMOTE_OK=1 make perf-smoke   # your own remote environment
```

Knobs: `VUS`, `RAMP`, `HOLD`, `PROFILE`, and for the write path `LINES`,
`QUANTITY`, `ITEM_PRICE`, `BUDGET`.

## History and the dashboard

Every `make perf-*` target runs through `scripts/perf_run.py`. The output you see is k6's own,
unchanged. What the wrapper adds is one line in `reports/perf.jsonl` per run, which is what
makes a trend possible:

```bash
make perf-trends     # the last run against earlier runs of the same shape
make dashboard       # the load panels sit next to the test panels
```

A single run tells you whether it is fast enough right now. It cannot tell you that p95 has
gone from 2ms to 9ms over a month, because 9ms still passes a 400ms threshold. The history
can, and `make perf-trends` says so.

How it decides what to compare, and why:

| Rule | Why |
|---|---|
| Only runs of the same scenario, profile, environment **and VU count** | p95 at 25 users against 4 users is the load level, not a regression. The first version left VUs out and reported a 31% "rise" that was only a bigger run |
| A run that crossed a threshold is never a baseline | the write path returns early when a total is wrong, so a broken run looks fast and makes the next healthy one look slow |
| The baseline is the median of the last five, and a rise under 25% is not reported | latency is noisy, and a check that fires on noise is one nobody reads |
| A p95 rise is reported, never blocking | what blocks is what k6 already judged: a crossed threshold |

Two things the wrapper does on purpose:

- **A run that crosses a threshold is still recorded**, and then the wrapper exits with k6's
  own code (99), so the pipeline still fails. Those are the runs worth having in the history.
- **k6's summary export includes `setup_data`**, and on the write path that holds a bearer
  token. The export goes to a temporary file, only the numbers are kept, and the file is
  deleted even when k6 fails.

`k6 run perf/write_path.js` directly still works, but it records nothing. Use the `make`
target, or `python scripts/perf_run.py perf/write_path.js --profile spike -e VUS=25`.

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

## Where they point

The target, the personas and their passwords come from the same config the pytest suites
use, resolved by `scripts/perf_run.py` and handed to k6 through its environment — never as
`-e` flags, which anyone who can list processes can read. The scripts hold no URL and no
password.

Three refusals, each before k6 starts:

| Refused | Why |
|---|---|
| `ENV=prod`, or a URL that names prod | a load test creates thousands of real orders |
| any host that is not this machine, unless `PERF_REMOTE_OK=1` | thousands of requests a second against somebody else's server is an attack. A public practice API is somebody else's server |
| an `auth.type` other than `password_token` | `lib/session.js` implements that one login; add yours there first |

`write_path.js` also stops in `setup()` on an environment with `test_hooks: false`: it
provisions the balance through the demo's test hooks, and a real product needs its own way
to do that before its write path can be load tested.
