// A shop of the run's own, made in setup() through the ordinary API: a service, barbers open every day,
// and customers who each sign up from an address of their own. Shared by the barbershop's scripts, so
// every run touches only what it made and two runs never collide.
import http from "k6/http";
import { BASE_URL, authHeaders } from "../lib/session.js";

export const json = (body) => JSON.stringify(body);
export const runId = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`;
const OPEN_ALL_WEEK = { hours: Object.fromEntries(["mon", "tue", "wed", "thu", "fri", "sat", "sun"].map((d) => [d, ["10:00", "19:00"]])) };

export function addDays(isoDate, days) {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

export function created(res, what) {
  if (res.status !== 201 && res.status !== 200) {
    throw new Error(`setup could not create ${what} on ${BASE_URL}: ${res.status} ${res.body}`);
  }
  return res;
}

// An address per device, in IPv6's documentation range (2001:db8::/32, never routed), a new range every
// run: one address may make only a few accounts and ask only so many codes an hour, and addresses reused
// from run to run would use up their hour on a long-lived copy.
export function addressMaker() {
  const hex = () => Math.floor(Math.random() * 65536).toString(16);
  const prefix = `${hex()}:${hex()}:${hex()}:${hex()}`;
  return (i) => `2001:db8:${prefix}:${i.toString(16)}`;
}

export function makeShop(owner, { barbers = 4, customers = 0 } = {}) {
  const run = runId();
  const password = `load-${run}-password`;

  const service = created(
    http.post(`${BASE_URL}/services`, json({ name: `QA load ${run}`, duration_minutes: 30, price_minor: 8000 }), authHeaders(owner, "POST /services")),
    "a service",
  ).json("id");

  const barberIds = [];
  for (let i = 0; i < barbers; i++) {
    const id = created(
      http.post(`${BASE_URL}/barbers`, json({ username: `qa-load-${run}-b${i}`, password, display_name: `Load ${i}` }), authHeaders(owner, "POST /barbers")),
      "a barber",
    ).json("id");
    created(http.put(`${BASE_URL}/barbers/${id}/hours`, json(OPEN_ALL_WEEK), authHeaders(owner, "PUT /barbers/:id/hours")), "hours");
    barberIds.push(id);
  }

  const address = addressMaker();
  const tokens = [];
  for (let i = 0; i < customers; i++) {
    const username = `qa-load-${run}-c${i}`;
    created(
      http.post(`${BASE_URL}/customers`, json({ username, password, display_name: `Load customer ${i}` }), {
        headers: { "Content-Type": "application/json", "X-Forwarded-For": address(i) },
        tags: { name: "POST /customers" },
      }),
      "a customer",
    );
    tokens.push(http.post(`${BASE_URL}/auth/token`, json({ username, password }), { headers: { "Content-Type": "application/json" }, tags: { name: "POST /auth/token" } }).json("access_token"));
  }
  return { service, barbers: barberIds, customers: tokens };
}
