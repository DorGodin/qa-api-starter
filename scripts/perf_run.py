#!/usr/bin/env python3
"""Run a k6 script, then record the result in the perf history.

k6 prints its own summary and this stays out of the way of it - the output you
see is k6's, unchanged. What this adds is the line in `reports/perf.jsonl` that
makes a trend possible, because one run cannot tell you that p95 has been
climbing 4% a week.

    python scripts/perf_run.py perf/write_path.js --profile spike -e VUS=25

Two deliberate behaviours:

* A run that breaches a threshold is still recorded, and this exits with k6's
  own code afterwards. The breached runs are the ones worth having in history,
  so recording must not be chained behind k6 succeeding.
* k6's summary export carries `setup_data`, which on the write path holds a
  bearer token. The export goes to a temporary file, only the normalised fields
  are kept, and the temporary file is deleted even when k6 fails.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.loader import is_local_host, load_env_config, password_env_var, password_for  # noqa: E402
from utils.helpers import assert_not_prod  # noqa: E402
from utils.perf_history import TREND_STATS, append, normalise  # noqa: E402

REPORTS = ROOT / "reports"

# Which product each folder of k6 scripts drives; a script in no listed folder is
# the demo's. One product's script against another product's environment would
# only measure 404s, and record them as a load test.
SCRIPT_PRODUCTS = {"perf/barber": "barber-booking"}


def product_of(script: str) -> str:
    path = Path(script)
    path = (path if path.is_absolute() else ROOT / path).resolve()
    try:
        relative = path.relative_to(ROOT).as_posix()
    except ValueError:
        return "demo"
    return next(
        (product for folder, product in SCRIPT_PRODUCTS.items() if relative.startswith(folder + "/")), "demo"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("script", help="the k6 script, e.g. perf/write_path.js")
    parser.add_argument("--profile", default="load", help="load, spike, soak or stress (default: load)")
    parser.epilog = "Anything this does not recognise is passed to k6 verbatim, e.g. -e VUS=25."
    # parse_known_args, not REMAINDER: REMAINDER swallows every argument that
    # follows the script path, so `perf/x.js --profile spike` would hand k6 a
    # --profile flag it does not have.
    args, passthrough = parser.parse_known_args()

    # A load test generates thousands of real orders. Pointing one at prod is
    # the worst thing in this repo, so it is refused rather than documented.
    assert_not_prod("perf_run.py")
    config = load_env_config()
    base_url = config["url"].rstrip("/")
    if "prod" in base_url:
        raise SystemExit(f"refusing to load test {base_url}: the URL names prod")
    drives = product_of(args.script)
    if config["product"] != drives:
        raise SystemExit(
            f"{args.script} drives the {drives!r} product; ENV={config['env']} is {config['product']!r}. "
            "Run it against its own product, or write that product's own k6 script."
        )
    if config["auth"]["type"] != "password_token":
        raise SystemExit(
            f"perf/lib/session.js logs in with password_token; ENV={config['env']} uses "
            f"{config['auth']['type']!r}. Add that login to session.js before load testing this environment."
        )
    if not (is_local_host(base_url) or os.getenv("PERF_REMOTE_OK") == "1"):
        # Thousands of requests a second is an attack when it is somebody else's
        # server. A remote target has to be claimed on purpose.
        raise SystemExit(
            f"refusing to load test {base_url}: it is not on this machine. If it is your own "
            "environment, set PERF_REMOTE_OK=1."
        )

    # Handed to k6 through its environment, not as -e flags: arguments are
    # visible to anyone who can list processes, and these include passwords.
    k6_env = {
        **os.environ,
        "BASE_URL": base_url,
        "TEST_HOOKS": "true" if config["test_hooks"] else "false",
        "AUTH_PATH": config["auth"]["path"],
    }
    for persona, username in config["personas"].items():
        k6_env[password_env_var(persona).replace("_PASSWORD", "_USER")] = username
        k6_env[password_env_var(persona)] = password_for(persona, config["env"])

    script = Path(args.script)
    if not script.is_file():
        raise SystemExit(f"no such k6 script: {script}")

    export = Path(tempfile.mkstemp(prefix="k6-summary-", suffix=".json")[1])
    command = [
        "k6",
        "run",
        f"--summary-export={export}",
        f"--summary-trend-stats={TREND_STATS}",
        "-e",
        f"PROFILE={args.profile}",
        *[a for a in passthrough if a != "--"],
        str(script),
    ]

    started = datetime.now(UTC)
    clock = time.monotonic()
    try:
        exit_code = subprocess.run(command, cwd=ROOT, env=k6_env).returncode
    except FileNotFoundError:
        export.unlink(missing_ok=True)
        raise SystemExit("k6 is not installed. See perf/README.md.") from None
    duration = time.monotonic() - clock

    try:
        summary = json.loads(export.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(f"\nk6 exited {exit_code} without writing a summary, so nothing was recorded.")
        return exit_code or 1
    finally:
        export.unlink(missing_ok=True)

    row = normalise(
        summary,
        scenario=script.stem,
        profile=args.profile,
        env=config["env"],
        base_url=base_url,
        started=started.isoformat(timespec="seconds"),
        duration=duration,
        exit_code=exit_code,
    )
    append(row, REPORTS / "perf.jsonl")

    print(
        f"\nrecorded in reports/perf.jsonl: {row['scenario']}/{row['profile']} on {row['env']} - "
        f"{row['verdict']}, p95 {row['p95']}ms, {row['iterations']} iterations, {row['rps']} req/s"
    )
    for expr in row["breached"]:
        print(f"  crossed: {expr}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
