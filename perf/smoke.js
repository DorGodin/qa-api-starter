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

  // The item this iteration created is carried between the groups on purpose.
  // Reading `items?limit=1` back instead would pick up whatever another run
  // left in the catalogue, and the total assertion below would really be
  // asserting "the first item in the catalogue happens to cost 10".
  const price = 10.0;
  let itemId;

  group("catalogue", () => {
    const created = http.post(
      `${BASE_URL}/items`,
      JSON.stringify({ name: `perf-item-${__ITER}`, price: price, active: true }),
      authHeaders(admin, "POST /items"),
    );
    check(created, { "item created": (r) => r.status === 201 });
    itemId = created.json("id");

    const listed = http.get(`${BASE_URL}/items?active=true`, authHeaders(member, "GET /items"));
    check(listed, {
      "catalogue readable": (r) => r.status === 200,
      "the item we just created is listed": (r) => r.json("content").some((row) => row.id === itemId),
    });
  });

  group("ordering", () => {
    const quantity = 2;
    const order = http.post(
      `${BASE_URL}/orders`,
      JSON.stringify({ lines: [{ item_id: itemId, quantity: quantity }] }),
      authHeaders(member, "POST /orders"),
    );
    check(order, {
      "order created": (r) => r.status === 201,
      "total is computed server side": (r) => r.json("total_amount") === price * quantity,
      "the order is about the item we created": (r) => r.json("lines")[0].item_id === itemId,
    });
  });
}
