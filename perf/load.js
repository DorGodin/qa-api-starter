// Load: the read path under concurrency. Thresholds are the release gate -
// a breach fails the run, it is not a number somebody eyeballs in a dashboard.
import http from "k6/http";
import { check } from "k6";
import { Trend } from "k6/metrics";
import { BASE_URL, authHeaders, login } from "./lib/session.js";

const catalogueLatency = new Trend("catalogue_latency", true);

export const options = {
  stages: [
    { duration: __ENV.RAMP || "10s", target: Number(__ENV.VUS || 10) },
    { duration: __ENV.HOLD || "20s", target: Number(__ENV.VUS || 10) },
    { duration: "5s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    "http_req_duration{name:GET /items}": ["p(95)<400", "p(99)<800"],
    "http_req_duration{name:GET /orders}": ["p(95)<400"],
    checks: ["rate>0.99"],
  },
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
  const catalogue = http.get(`${BASE_URL}/items?active=true&limit=20`, authHeaders(data.token, "GET /items"));
  catalogueLatency.add(catalogue.timings.duration);
  check(catalogue, { "catalogue 200": (r) => r.status === 200 });

  const orders = http.get(`${BASE_URL}/orders?limit=20`, authHeaders(data.token, "GET /orders"));
  check(orders, { "orders 200": (r) => r.status === 200 });
}
