// Load on the barbershop's booking path: every user aims at the same fresh time
// at the same moment, and the target moves on every WINDOW_MS - so the race for
// a time is run again and again at full concurrency, for the whole run.
//
// The first version drew targets at random from a small pool. The pool filled
// in the first second, during the ramp, and for the rest of the run every
// request was a refusal - which writes nothing, needs no lock, and cannot race.
// Run against a server with its booking lock broken, it passed. A load test
// for a race has to keep the race alive.
//
// Speed is measured, but it is not the point. Under contention the defects that
// matter are a double booking, a 5xx where a refusal belonged, and a 201 for a
// booking that was never stored. Each has its own metric and each is a gate at
// every profile, stress included. The database is checked at the end, not only
// the responses: a server can answer every request plausibly and still store
// two bookings in one chair.
//
// Everything it books, it creates first - its own barbers, service and
// customers - so a run never touches anything else on the environment, and two
// runs never collide with each other.
import http from "k6/http";
import { check } from "k6";
import exec from "k6/execution";
import { Counter } from "k6/metrics";
import { BASE_URL, authHeaders, login } from "../lib/session.js";
import { stages, thresholds, track } from "../lib/profiles.js";

const BARBERS = Number(__ENV.BARBERS || 4);
// A customer may hold only two bookings ahead. One customer per user would reach
// it within seconds, and from then on every request would be refused - the race
// over again, as in the first version. So the pool is larger than the run can
// fill, and each iteration books as the next customer in it.
const CUSTOMERS = Number(__ENV.CUSTOMERS || 100);
const DAYS = Number(__ENV.DAYS || 3);
const WINDOW_MS = Number(__ENV.WINDOW_MS || 200);

// A clean 409 is the correct answer to a taken time. Without this, k6 counts
// every refusal in http_req_failed and a correct server fails the run.
http.setResponseCallback(http.expectedStatuses(200, 201, 204, 409));

const won = new Counter("bookings_won");
const refused = new Counter("bookings_refused");
const unexpected = new Counter("unexpected_status");
const lost = new Counter("lost_bookings");
const doubleBooked = new Counter("double_bookings");
const idleBarbers = new Counter("barbers_never_booked");

export const options = {
  stages: stages(),
  setupTimeout: "180s",
  teardownTimeout: "120s",
  thresholds: thresholds(
    { "http_req_duration{name:POST /bookings}": ["p(95)<1000"] },
    {
      unexpected_status: ["count==0"],
      lost_bookings: ["count==0"],
      double_bookings: ["count==0"],
      // A run in which some barber was never booked did not exercise what it
      // claims to - the pool, the customers or the setup went wrong.
      barbers_never_booked: ["count==0"],
    },
  ),
};

const json = (body) => JSON.stringify(body);
const runId = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`;
const OPEN_ALL_WEEK = { hours: Object.fromEntries(["mon", "tue", "wed", "thu", "fri", "sat", "sun"].map((d) => [d, ["10:00", "19:00"]])) };

function addDays(isoDate, days) {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

function created(res, what) {
  if (res.status !== 201 && res.status !== 200) {
    throw new Error(`setup could not create ${what} on ${BASE_URL}: ${res.status} ${res.body}`);
  }
  return res;
}

export function setup() {
  const owner = login("owner");
  const run = runId();
  const password = `load-${run}-password`;

  const service = created(
    http.post(`${BASE_URL}/services`, json({ name: `QA load ${run}`, duration_minutes: 30, price_minor: 8000 }), authHeaders(owner, "POST /services")),
    "a service",
  ).json("id");

  const barbers = [];
  for (let i = 0; i < BARBERS; i++) {
    const id = created(
      http.post(`${BASE_URL}/barbers`, json({ username: `qa-load-${run}-b${i}`, password, display_name: `Load ${i}` }), authHeaders(owner, "POST /barbers")),
      "a barber",
    ).json("id");
    created(http.put(`${BASE_URL}/barbers/${id}/hours`, json(OPEN_ALL_WEEK), authHeaders(owner, "PUT /barbers/:id/hours")), "hours");
    barbers.push(id);
  }

  // The targets come from the product's own availability, so the script never
  // computes a time zone or an opening hour. Only starts on the hour and the
  // half hour: with a 30 minute service those never overlap each other, so
  // every target is genuinely bookable and each window is a real race.
  const today = http.get(`${BASE_URL}/shop`).json("today");
  const pool = [];
  for (let d = 2; d < 2 + DAYS; d++) {
    const day = addDays(today, d);
    for (const id of barbers) {
      const slots = http.get(`${BASE_URL}/barbers/${id}/availability?date=${day}&service_id=${service}`, authHeaders(owner, "GET /barbers/:id/availability")).json("slots");
      for (const slot of slots) {
        if (slot.start_local.slice(14, 16) === "00" || slot.start_local.slice(14, 16) === "30") pool.push({ barber: id, start: slot.start });
      }
    }
  }
  if (pool.length === 0) throw new Error("no free times: the pool is empty and nothing would be tested");

  const hex = () => Math.floor(Math.random() * 65536).toString(16);
  const runPrefix = `${hex()}:${hex()}:${hex()}:${hex()}`;
  const customers = [];
  for (let i = 0; i < CUSTOMERS; i++) {
    const username = `qa-load-${run}-c${i}`;
    // Each from an address of its own, as different people's phones: one address
    // may make only a few accounts an hour. A new range every run - addresses
    // reused from run to run would use up their hour on a long-lived copy - in
    // IPv6's documentation range, 2001:db8::/32, which is never routed.
    const address = `2001:db8:${runPrefix}:${i.toString(16)}`;
    created(
      http.post(`${BASE_URL}/customers`, json({ username, password, display_name: `Load customer ${i}` }), { headers: { "Content-Type": "application/json", "X-Forwarded-For": address }, tags: { name: "POST /customers" } }),
      "a customer",
    );
    const token = http.post(`${BASE_URL}/auth/token`, json({ username, password }), { headers: { "Content-Type": "application/json" }, tags: { name: "POST /auth/token" } }).json("access_token");
    customers.push(token);
  }
  return { owner, service, barbers, pool, customers };
}

export default function (data) {
  const token = data.customers[exec.scenario.iterationInTest % data.customers.length];
  // Everyone aims at the same target during a window; the next window, the
  // next target. A pool too small for the run wraps, and the late windows
  // become refusals only - BARBERS and DAYS size it.
  const target = data.pool[Math.floor(Date.now() / WINDOW_MS) % data.pool.length];
  const res = track(http.post(`${BASE_URL}/bookings`, json({ barber_id: target.barber, service_id: data.service, start: target.start }), authHeaders(token, "POST /bookings")));

  if (res.status === 201) {
    won.add(1);
    // Read it back: a 201 for a booking that was never stored is the worst
    // answer a booking system can give, and only reading it back shows it.
    const stored = http.get(`${BASE_URL}/bookings/${res.json("id")}`, authHeaders(token, "GET /bookings/:id"));
    if (stored.status !== 200 || stored.json("status") !== "confirmed" || stored.json("start") !== target.start) lost.add(1);
  } else if (res.status === 409) {
    refused.add(1);
  } else {
    unexpected.add(1);
  }
  check(res, {
    "booked, or refused cleanly": (r) => r.status === 201 || r.status === 409,
    "a refusal says why": (r) => r.status !== 409 || ["slot_taken", "customer_overlap", "too_many_bookings"].includes(r.json("code")),
  });
}

export function teardown(data) {
  for (const id of data.barbers) {
    const rows = http.get(`${BASE_URL}/bookings?barber_id=${id}&status=confirmed&limit=100`, authHeaders(data.owner, "GET /bookings")).json("content");
    if (rows.length === 0) idleBarbers.add(1);
    const spans = rows.map((r) => [Date.parse(r.start), Date.parse(r.end)]).sort((a, b) => a[0] - b[0]);
    for (let i = 1; i < spans.length; i++) {
      if (spans[i][0] < spans[i - 1][1]) doubleBooked.add(1);
    }
  }
}
