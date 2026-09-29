// Smoke: does the API work at all under one user? Runs in seconds, gates every merge.
import http from "k6/http";
import { check, group } from "k6";
import { BASE_URL, authHeaders, login } from "./lib/session.js";

export const options = {
  vus: 1,
  iterations: 5,
  thresholds: {
    http_req_failed: ["rate==0"],
    http_req_duration: ["p(95)<500"],
    checks: ["rate==1"],
  },
};

export default function () {
  const admin = login("admin");
  const member = login("member");

  group("catalogue", () => {
    const created = http.post(
      `${BASE_URL}/items`,
      JSON.stringify({ name: `perf-item-${__ITER}`, price: 10.0, active: true }),
      authHeaders(admin, "POST /items"),
    );
    check(created, { "item created": (r) => r.status === 201 });

    const listed = http.get(`${BASE_URL}/items?active=true`, authHeaders(member, "GET /items"));
    check(listed, {
      "catalogue readable": (r) => r.status === 200,
      "catalogue not empty": (r) => r.json("content").length > 0,
    });
  });

  group("ordering", () => {
    const itemId = http.get(`${BASE_URL}/items?limit=1`, authHeaders(member, "GET /items")).json("content")[0].id;

    const order = http.post(
      `${BASE_URL}/orders`,
      JSON.stringify({ lines: [{ item_id: itemId, quantity: 1 }] }),
      authHeaders(member, "POST /orders"),
    );
    check(order, {
      "order created": (r) => r.status === 201,
      "total is computed server side": (r) => r.json("total_amount") === 10.0,
    });
  });
}
