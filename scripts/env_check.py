#!/usr/bin/env python3
"""Prove an environment is usable before any suite runs against it.

    ENV=qa python scripts/env_check.py

Checks, in order, and stops at the first that fails: the config block, the health
path, and a login for every persona. For each password it says WHERE it came
from - an environment variable, the local override, the committed file - and
never what it is. Read-only: it logs in and creates nothing, so it is safe on
any environment, prod included.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.loader import load_env_config, resolve_password  # noqa: E402
from obj import ApiClient  # noqa: E402
from obj.auth import LoginFailed  # noqa: E402


def main() -> int:
    try:
        config = load_env_config()
    except (KeyError, TypeError, ValueError) as exc:
        print(f"config: {exc}")
        return 1

    env = config["env"]
    print(f"ENV={env}  {config['url']}")
    print(f"  auth        {config['auth']['type']}")
    print(
        f"  test hooks  {'yes - /_test/reset is used' if config['test_hooks'] else 'no - nothing is ever reset'}"
    )

    client = ApiClient()
    if config["health_path"] is None:
        print("  health      not configured (health_path is null)")
    else:
        try:
            status = client.request("GET", config["health_path"], persona=None).status_code
        except Exception as exc:  # noqa: BLE001
            print(f"  health      cannot reach {client.base_url}: {type(exc).__name__}")
            return 1
        print(f"  health      GET {config['health_path']} -> {status}")
        if not 200 <= status < 300:
            return 1

    failed = False
    for persona, username in config["personas"].items():
        try:
            password, source = resolve_password(persona, env)
        except KeyError as exc:
            print(f"  {persona:<11} no password: {exc.args[0]}")
            failed = True
            continue
        try:
            client.register_persona(persona, username, password)
        except LoginFailed as exc:
            print(f"  {persona:<11} login failed ({source}): {exc}")
            failed = True
            continue
        print(f"  {persona:<11} logged in as {username!r}, password from {source}")

    print("\nready" if not failed else "\nnot ready - fix the first failure above and run again")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
