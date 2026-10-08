#!/usr/bin/env python3
"""Keep the barbershop's test copy small enough to test against.

    python scripts/tidy_test_copy.py            # reset it if it has grown, else do nothing
    python scripts/tidy_test_copy.py --check    # only say

The product cannot be reset and every run leaves services, courses and barbers behind. Past a few hundred
the owner's screen takes seconds to draw and phone tests fail for a reason that is not the product's (it
cost a day once). So when the test copy holds SERVICES_MAX services or COURSES_MAX courses it is stopped,
its database deleted (`make reset-test-db` in the product - the test copy's file only), and started again.

It acts on the test copy on port 8101 and nothing else: a URL that is not 127.0.0.1:8101, or a product
whose checkout is not where --product says, and it stops before doing anything.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.loader import load_env_config, resolve_password  # noqa: E402
from obj import ApiClient  # noqa: E402

SERVICES_MAX = 200
COURSES_MAX = 20
TEST_COPY = ("127.0.0.1", 8101)


def counts(client: ApiClient) -> tuple[int, int]:
    services = client.request("GET", "/services", persona="owner", params={"limit": 1}).as_dict["total"]
    courses = client.request("GET", "/courses", persona="owner", params={"limit": 1}).as_dict["total"]
    return services, courses


def listening(port: int) -> list[str]:
    done = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], capture_output=True, text=True)
    return done.stdout.split()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--product", type=Path, default=Path(__file__).resolve().parents[2] / "barber-booking-api")
    parser.add_argument("--check", action="store_true", help="only say whether it has grown")
    parser.add_argument("--services-max", type=int, default=SERVICES_MAX)
    parser.add_argument("--courses-max", type=int, default=COURSES_MAX)
    args = parser.parse_args()

    config = load_env_config()
    url = urlparse(config["url"])
    if (url.hostname, url.port) != TEST_COPY:
        print(f"refusing: ENV={config['env']} is {config['url']}, not the test copy on {TEST_COPY[0]}:{TEST_COPY[1]}")
        return 2
    if not (args.product / "Makefile").exists():
        print(f"refusing: no product checkout at {args.product}")
        return 2

    client = ApiClient()
    password, _ = resolve_password("owner", config["env"])
    client.register_persona("owner", config["personas"]["owner"], password)
    services, courses = counts(client)
    grown = services >= args.services_max or courses >= args.courses_max
    print(f"test copy: {services} services, {courses} courses - {'grown, tidying' if grown else 'small enough'}")
    if not grown or args.check:
        return 0

    for pid in listening(TEST_COPY[1]):
        subprocess.run(["kill", pid], check=False)
    for _ in range(50):
        if not listening(TEST_COPY[1]):
            break
        time.sleep(0.2)
    subprocess.run(["make", "-C", str(args.product), "reset-test-db"], check=True)
    subprocess.Popen(
        ["make", "-C", str(args.product), "run-test"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(100):
        try:
            if client.request("GET", config["health_path"], persona=None).status_code == 200:
                print("test copy: reset and running")
                return 0
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.3)
    print("test copy: reset, but it did not come back - start it with `make run-test`")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
