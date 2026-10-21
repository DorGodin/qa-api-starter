// The evening rush on the read path: everyone opens the app at once and looks before they book - the
// shop, the barbers, the services, a month's open days and one day's times, then their own bookings.
// Reads hold no lock and corrupt nothing, so the question here is speed and clean answers: a 5xx or a
// time listing that comes back empty for a barber who is open is a defect at any load.
import http from "k6/http";
import { check } from "k6";
import exec from "k6/execution";
import { Counter } from "k6/metrics";
import { BASE_URL, authHeaders, login } from "../lib/session.js";
import { stages, thresholds, track } from "../lib/profiles.js";
import { addDays, makeShop } from "./shop.js";

const BARBERS = Number(__ENV.BARBERS || 4);
const CUSTOMERS = Number(__ENV.CUSTOMERS || 30);

const unexpected = new Counter("unexpected_status");
const emptyDays = new Counter("open_days_without_times");

export const options = {
  stages: stages(),
  setupTimeout: "120s",
  thresholds: thresholds(
    {
      "http_req_duration{name:GET /barbers/:id/availability}": ["p(95)<800"],
      "http_req_duration{name:GET /barbers/:id/days}": ["p(95)<800"],
      "http_req_duration{name:GET /barbers}": ["p(95)<500"],
      "http_req_duration{name:GET /bookings}": ["p(95)<500"],
    },
    { unexpected_status: ["count==0"], open_days_without_times: ["count==0"] },
  ),
};

export function setup() {
  const owner = login("owner");
  const shop = makeShop(owner, { barbers: BARBERS, customers: CUSTOMERS });
  return { ...shop, today: http.get(`${BASE_URL}/shop`).json("today") };
}

function read(url, token, name) {
  const res = track(http.get(url, token ? authHeaders(token, name) : { tags: { name } }));
  if (res.status !== 200) unexpected.add(1);
  return res;
}

export default function (data) {
  const i = exec.scenario.iterationInTest;
  const token = data.customers[i % data.customers.length];
  const barber = data.barbers[i % data.barbers.length];
  const day = addDays(data.today, 2 + (i % 5));

  read(`${BASE_URL}/shop`, null, "GET /shop");
  read(`${BASE_URL}/barbers`, token, "GET /barbers");
  read(`${BASE_URL}/services`, token, "GET /services");
  read(`${BASE_URL}/barbers/${barber}/days?month=${day.slice(0, 7)}&service_id=${data.service}`, token, "GET /barbers/:id/days");
  const times = read(`${BASE_URL}/barbers/${barber}/availability?date=${day}&service_id=${data.service}`, token, "GET /barbers/:id/availability");
  read(`${BASE_URL}/bookings`, token, "GET /bookings");
  read(`${BASE_URL}/me`, token, "GET /me");

  const slots = times.status === 200 ? times.json("slots") : [];
  if (slots.length === 0) emptyDays.add(1);
  check(times, { "an open day lists its times": () => slots.length > 0 });
}
