// The load SHAPES, in one place. A profile is not "how many users" - it is a
// different question about the same endpoints:
//
//   load    does it hold up at the traffic we expect?
//   spike   does it survive a sudden jump, and recover after?
//   soak    does it leak - memory, connections, locks - over a long hold?
//   stress  where does it break, and does it break cleanly (4xx, not 5xx)?
//
// Keeping them here means a scenario script describes WHAT it exercises and
// never hard codes a ramp, so the same script answers all four questions.
import { Rate } from "k6/metrics";

const VUS = Number(__ENV.VUS || 10);
const RAMP = __ENV.RAMP || "10s";
const HOLD = __ENV.HOLD || "20s";

const SHAPES = {
  load: [
    { duration: RAMP, target: VUS },
    { duration: HOLD, target: VUS },
    { duration: "5s", target: 0 },
  ],
  spike: [
    { duration: "5s", target: VUS },
    { duration: "10s", target: VUS * 5 },
    { duration: HOLD, target: VUS },
    { duration: "5s", target: 0 },
  ],
  soak: [
    { duration: "30s", target: VUS },
    { duration: __ENV.HOLD || "10m", target: VUS },
    { duration: "30s", target: 0 },
  ],
  stress: [
    { duration: "20s", target: VUS },
    { duration: "20s", target: VUS * 2 },
    { duration: "20s", target: VUS * 4 },
    { duration: "20s", target: VUS * 8 },
    { duration: "10s", target: 0 },
  ],
};

export const serverErrors = new Rate("server_errors");

export function profileName() {
  return __ENV.PROFILE || "load";
}

export function stages() {
  const name = profileName();
  const shape = SHAPES[name];
  if (shape === undefined) {
    throw new Error(`unknown PROFILE '${name}'; known profiles: ${Object.keys(SHAPES).join(", ")}`);
  }
  return shape;
}

// Every request goes through here. A 5xx is a defect at any load level, so it
// is the one gate that never relaxes.
export function track(response) {
  serverErrors.add(response.status >= 500);
  return response;
}

// Stress deliberately pushes past capacity, so latency and error RATE stop
// being defects there - queueing and 429s are the expected answer. Asserting
// them anyway would mean a stress run is red by design, which trains everyone
// to ignore it. What stays asserted is that the API degrades cleanly.
export function thresholds(extra = {}) {
  if (profileName() === "stress") {
    return { server_errors: ["rate==0"] };
  }
  return {
    server_errors: ["rate==0"],
    http_req_failed: ["rate<0.01"],
    checks: ["rate>0.99"],
    ...extra,
  };
}
