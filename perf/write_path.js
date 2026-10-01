// Load on the WRITE path: create an order, then submit it, under concurrency.
//
// load.js only reads. A read-only load test cannot find the bugs that matter
// most, because the read path has no state to corrupt. Everything expensive
// lives here - server side money math, a status transition, and a balance
// being decremented - and those are exactly the things that break when two
// requests arrive at once. So this script does not just time the calls, it
// re-asserts the same arithmetic the functional suites assert, on every
// iteration, at every load level. A p95 that looks fine while totals come back
// wrong is not a pass.
import http from "k6/http";
import { check } from "k6";
import { Counter, Trend } from "k6/metrics";
import { BASE_URL, TEST_HOOKS, authHeaders, login } from "./lib/session.js";
import { runShape, stages, thresholds, track } from "./lib/profiles.js";

const LINES = Number(__ENV.LINES || 3);
const QUANTITY = Number(__ENV.QUANTITY || 2);

// Every submit decrements the member balance, so the write path is not
// infinitely repeatable: at the rate this API answers, the default 500.0 is
// spent in about seven seconds. setup() therefore provisions a balance sized
// for the run, exactly as a load test against a real product has to provision
// its own test data. With that done, budget_rejections stops meaning "we ran
// out" and starts meaning "the product charged more than it should have" -
// which is why it is a hard gate below.
//
// The balance is sized from the run's shape, not fixed. A fixed 1,000,000 paid
// for about 66,000 orders, and the nightly 3 minute soak in CI places more:
// every order after that was a correct refusal, counted as a defect, and the
// soak was red every night. The bound below assumes no iteration - two round
// trips - completes in under a millisecond, which no real server reaches.
//
// A balance that large cannot run out, so a refusal no longer catches a server
// that charges too much - it only ever did by accident. teardown() reconciles
// instead: what left the balance must equal ORDER_COST times the orders that
// reached submitted, to the cent. An overcharge, a lost update between two
// concurrent submits, or a submit that charged without moving the order all
// break that equation.
const ITEM_PRICE = Number(__ENV.ITEM_PRICE || 2.5);
const ORDER_COST = ITEM_PRICE * QUANTITY * LINES;
const MIN_ITERATION_SECONDS = 0.001;
const { seconds: RUN_SECONDS, peakVUs: PEAK_VUS } = runShape();
const BUDGET = Number(__ENV.BUDGET || Math.ceil((ORDER_COST * PEAK_VUS * RUN_SECONDS) / MIN_ITERATION_SECONDS));

const createLatency = new Trend("order_create_latency", true);
const submitLatency = new Trend("order_submit_latency", true);
const budgetRejections = new Counter("budget_rejections");
const wrongTotals = new Counter("wrong_totals");
const unreconciled = new Counter("unreconciled_balance");

export const options = {
  stages: stages(),
  thresholds: thresholds(
    {
      "http_req_duration{name:POST /orders}": ["p(95)<400", "p(99)<900"],
      "http_req_duration{name:POST /orders/:id/submit}": ["p(95)<500", "p(99)<1000"],
    },
    // Money math and the budget rule are correctness, not performance. They are
    // gates at every profile, including stress.
    { wrong_totals: ["count==0"], budget_rejections: ["count==0"], unreconciled_balance: ["count==0"] },
  ),
};

export function setup() {
  // Provisioning goes through the demo product's test hooks. A product without
  // them needs its own way to give the member a balance for the whole run -
  // running without one would end in a wall of 402s that look like a defect.
  if (!TEST_HOOKS) {
    throw new Error(
      "write_path.js provisions the member balance through /_test/reset and /_test/budget, and this " +
        "environment declares test_hooks=false. Give setup() the product's own way to provision a " +
        "balance before load testing its write path.",
    );
  }
  const admin = login("admin");
  http.post(`${BASE_URL}/_test/reset`, null, authHeaders(admin, "POST /_test/reset"));
  const provisioned = http.post(
    `${BASE_URL}/_test/budget`,
    JSON.stringify({ amount: BUDGET }),
    authHeaders(admin, "POST /_test/budget"),
  );
  if (provisioned.status !== 204) {
    throw new Error(`setup could not provision the member balance: ${provisioned.status} ${provisioned.body}`);
  }

  const item = http.post(
    `${BASE_URL}/items`,
    JSON.stringify({ name: "write-path-item", price: ITEM_PRICE, active: true }),
    authHeaders(admin, "POST /items"),
  );
  if (item.status !== 201) {
    throw new Error(`setup could not create the item against ${BASE_URL}: ${item.status} ${item.body}`);
  }
  return { token: login("member"), itemId: item.json("id") };
}

export function teardown(data) {
  const admin = login("admin");
  const submitted = http.get(`${BASE_URL}/orders?status=submitted&limit=1`, authHeaders(admin, "GET /orders")).json("total");
  const balance = http.get(`${BASE_URL}/me/budget`, authHeaders(data.token, "GET /me/budget")).json("budget");
  const spentCents = Math.round((BUDGET - balance) * 100);
  const chargedCents = Math.round(ORDER_COST * submitted * 100);
  if (spentCents !== chargedCents) {
    unreconciled.add(1);
    console.error(`the balance does not reconcile: ${spentCents / 100} left it, ${submitted} submitted orders at ${ORDER_COST} account for ${chargedCents / 100}`);
  }
}

export default function (data) {
  const lines = [];
  for (let i = 0; i < LINES; i++) {
    lines.push({ item_id: data.itemId, quantity: QUANTITY });
  }
  const expectedTotal = Number((ITEM_PRICE * QUANTITY * LINES).toFixed(2));

  const created = track(
    http.post(`${BASE_URL}/orders`, JSON.stringify({ lines }), authHeaders(data.token, "POST /orders")),
  );
  createLatency.add(created.timings.duration);
  const createdOk = check(created, {
    "order created": (r) => r.status === 201,
    "total computed server side": (r) => r.json("total_amount") === expectedTotal,
    "order starts as draft": (r) => r.json("status") === "draft",
  });
  if (!createdOk) {
    if (created.status === 201 && created.json("total_amount") !== expectedTotal) {
      wrongTotals.add(1);
    }
    return;
  }

  const orderId = created.json("id");
  const submitted = track(
    http.post(
      `${BASE_URL}/orders/${orderId}/submit`,
      null,
      authHeaders(data.token, "POST /orders/:id/submit"),
    ),
  );
  submitLatency.add(submitted.timings.duration);

  if (submitted.status === 402) {
    budgetRejections.add(1);
    return;
  }

  const submittedOk = check(submitted, {
    "order submitted": (r) => r.status === 200,
    "status moved to submitted": (r) => r.json("status") === "submitted",
    // The response must describe the order we just created, not a neighbour's.
    "submit answered about our order": (r) => r.json("id") === orderId,
    "total survived the transition": (r) => r.json("total_amount") === expectedTotal,
  });
  if (!submittedOk && submitted.status === 200 && submitted.json("total_amount") !== expectedTotal) {
    wrongTotals.add(1);
  }
}
