// Load on the READ path: the catalogue and the order list under concurrency.
// Thresholds are the release gate - a breach fails the run, it is not a number
// somebody eyeballs in a dashboard. The write path lives in write_path.js.
//
// The ramp comes from PROFILE (load / spike / soak / stress), so this script
// answers four different questions without being edited.
import http from "k6/http";
import { check } from "k6";
import { Trend } from "k6/metrics";
import { BASE_URL, authHeaders, login } from "./lib/session.js";
import { stages, thresholds, track } from "./lib/profiles.js";

const catalogueLatency = new Trend("catalogue_latency", true);

export const options = {
  stages: stages(),
  thresholds: thresholds({
    "http_req_duration{name:GET /items}": ["p(95)<400", "p(99)<800"],
    "http_req_duration{name:GET /orders}": ["p(95)<400"],
  }),
};

export function setup() {
  const admin = login("admin");
  for (let i = 0; i < 20; i++) {
    http.post(
      `${BASE_URL}/items`,
      JSON.stringify({ name: `load-item-${i}`, price: 5 + i, active: true }),
      authHeaders(admin, "POST /items"),
    );
  }
  return { token: login("member") };
}

export default function (data) {
  const catalogue = track(
    http.get(`${BASE_URL}/items?active=true&limit=20`, authHeaders(data.token, "GET /items")),
  );
  catalogueLatency.add(catalogue.timings.duration);
  check(catalogue, { "catalogue 200": (r) => r.status === 200 });

  const orders = track(http.get(`${BASE_URL}/orders?limit=20`, authHeaders(data.token, "GET /orders")));
  check(orders, { "orders 200": (r) => r.status === 200 });
}
