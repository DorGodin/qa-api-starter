import http from "k6/http";
import { check } from "k6";

export const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";

const PASSWORDS = { admin: "admin-secret", member: "member-secret" };

export function login(username) {
  const res = http.post(
    `${BASE_URL}/auth/token`,
    JSON.stringify({ username, password: PASSWORDS[username] }),
    { headers: { "Content-Type": "application/json" }, tags: { name: "POST /auth/token" } },
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
