import http from "k6/http";
import { check } from "k6";

// Everything here is handed over by scripts/perf_run.py, which resolves it from
// the same config and password rules the pytest suites use. Nothing is
// hardcoded, so the perf scripts never hold a password and never disagree with
// the tests about which environment they are pointed at.
export const BASE_URL = __ENV.BASE_URL;
export const TEST_HOOKS = __ENV.TEST_HOOKS === "true";
const AUTH_PATH = __ENV.AUTH_PATH;

if (!BASE_URL || !AUTH_PATH) {
  throw new Error(
    "BASE_URL and AUTH_PATH are not set. Run this through `make perf-*` or scripts/perf_run.py, " +
      "which resolve them - and the passwords - from config/config.json for ENV.",
  );
}

function credential(persona, kind) {
  const name = `QA_${persona.toUpperCase().replace(/[^A-Z0-9]/g, "_")}_${kind}`;
  const value = __ENV[name];
  if (!value) {
    throw new Error(`${name} is not set. Run through scripts/perf_run.py, or export it.`);
  }
  return value;
}

export function login(persona) {
  const res = http.post(
    `${BASE_URL}${AUTH_PATH}`,
    JSON.stringify({ username: credential(persona, "USER"), password: credential(persona, "PASSWORD") }),
    { headers: { "Content-Type": "application/json" }, tags: { name: `POST ${AUTH_PATH}` } },
  );
  check(res, { "login returns 200": (r) => r.status === 200 });
  return res.json("access_token");
}

export function authHeaders(token, name) {
  return {
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    tags: { name },
  };
}
