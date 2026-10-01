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

// How long a run lasts and how many users it peaks at, from the stages
// themselves - so anything sized to the run follows the profile and HOLD
// instead of being a number someone has to remember to raise.
const UNIT_SECONDS = { ms: 0.001, s: 1, m: 60, h: 3600 };

function seconds(duration) {
  let total = 0;
  for (const [, amount, unit] of String(duration).matchAll(/(\d+(?:\.\d+)?)(ms|s|m|h)/g)) {
    total += Number(amount) * UNIT_SECONDS[unit];
  }
  if (total === 0) throw new Error(`cannot read the duration '${duration}'`);
  return total;
}

export function runShape() {
  const shape = stages();
  return {
    seconds: shape.reduce((sum, stage) => sum + seconds(stage.duration), 0),
    peakVUs: Math.max(...shape.map((stage) => stage.target)),
  };
}

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

// Two kinds of gate, kept apart because stress treats them differently.
//
// `latency` - how fast, how often refused. Stress pushes past capacity on
// purpose, so there queueing and refusals are the expected answer, not defects;
// asserting them anyway makes every stress run red by design, which trains
// everyone to ignore it. Under stress these are dropped.
//
// `correctness` - a wrong total, a double booking, a 5xx. Those are defects at
// any load, so they are kept under every profile. The first version of this
// function returned only server_errors under stress and silently dropped the
// script's correctness gates with the latency ones.
export function thresholds(latency = {}, correctness = {}) {
  const always = { server_errors: ["rate==0"], ...correctness };
  if (profileName() === "stress") {
    return always;
  }
  return {
    ...always,
    http_req_failed: ["rate<0.01"],
    checks: ["rate>0.99"],
    ...latency,
  };
}
