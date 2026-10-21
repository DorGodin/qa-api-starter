// Sign-in by SMS code under load: a crowd of new customers, each on a phone and an address of their own,
// asks for a code, reads it from the fake provider's inbox and signs in. Every step writes - the code,
// the attempt, the account, the session - so this is the write path every customer takes before a
// booking. On SQLite a write outside the lock is "database is locked", a 5xx; a code that never reaches
// the inbox, or a right code refused, is a customer who cannot get in.
import http from "k6/http";
import { check, sleep } from "k6";
import exec from "k6/execution";
import { Counter } from "k6/metrics";
import { BASE_URL } from "../lib/session.js";
import { stages, thresholds, track } from "../lib/profiles.js";
import { addressMaker, json } from "./shop.js";

const SMS_INBOX = __ENV.SMS_INBOX;
if (!SMS_INBOX) throw new Error("SMS_INBOX is not set: run through scripts/perf_run.py with an ENV whose block has sms_inbox");

http.setResponseCallback(http.expectedStatuses(200, 202, 204));

const signedIn = new Counter("signed_in");
const unexpected = new Counter("unexpected_status");
const lostCodes = new Counter("codes_never_received");
const refusedCodes = new Counter("right_codes_refused");

export const options = {
  stages: stages(),
  thresholds: thresholds(
    {
      "http_req_duration{name:POST /auth/otp}": ["p(95)<1000"],
      "http_req_duration{name:POST /auth/otp/verify}": ["p(95)<1000"],
    },
    { unexpected_status: ["count==0"], codes_never_received: ["count==0"], right_codes_refused: ["count==0"] },
  ),
};

export function setup() {
  return { prefix: addressMaker()(0).slice(0, -2), phoneBase: Math.floor(Math.random() * 9e6) * 10 };
}

const headers = (address) => ({ "Content-Type": "application/json", "X-Forwarded-For": address });

function codeFor(phone) {
  for (let tries = 0; tries < 50; tries++) {
    const inbox = http.get(`${SMS_INBOX}/messages?to=${phone}`, { tags: { name: "fake SMS inbox" } });
    const found = inbox.status === 200 ? inbox.json() : [];
    const match = found.length ? /\b(\d{4})\b/.exec(found[found.length - 1].text) : null;
    if (match) return match[1];
    sleep(0.1);
  }
  return null;
}

export default function (data) {
  const i = exec.scenario.iterationInTest;
  const phone = `05${String(data.phoneBase + i).padStart(8, "0").slice(-8)}`;
  const address = `${data.prefix}:${(i + 1).toString(16)}`;

  const asked = track(http.post(`${BASE_URL}/auth/otp`, json({ full_name: "לקוח עומס", phone }), { headers: headers(address), tags: { name: "POST /auth/otp" } }));
  if (asked.status !== 202) {
    unexpected.add(1);
    return;
  }
  const code = codeFor(phone);
  if (code === null) {
    lostCodes.add(1);
    return;
  }
  const verified = track(http.post(`${BASE_URL}/auth/otp/verify`, json({ phone, code }), { headers: headers(address), tags: { name: "POST /auth/otp/verify" } }));
  if (verified.status !== 200) {
    if (verified.status < 500) refusedCodes.add(1);
    unexpected.add(1);
    return;
  }
  const me = track(http.get(`${BASE_URL}/me`, { headers: { Authorization: `Bearer ${verified.json("access_token")}` }, tags: { name: "GET /me" } }));
  if (me.status === 200) signedIn.add(1);
  else unexpected.add(1);
  check(me, { "signed in as a customer": (r) => r.status === 200 && r.json("role") === "customer" });
}
