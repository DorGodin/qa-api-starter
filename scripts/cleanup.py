#!/usr/bin/env python3
"""Delete what the runs created on one environment.

The artifact ledger already knows every object a run made. This closes the loop:
it reads the ledger, deletes through the same object layer the tests use, and
reports what it could not remove.

    python scripts/cleanup.py --env qa              # shows what it would delete
    python scripts/cleanup.py --env qa --yes        # deletes
    python scripts/cleanup.py --env qa --resource orders --since 2026-09-29
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from obj import ApiClient  # noqa: E402
from obj.base import Base  # noqa: E402
from utils.artifacts import load  # noqa: E402
from utils.helpers import assert_not_prod  # noqa: E402

REPORTS = Path(__file__).resolve().parents[1] / "reports"
PASSWORDS = {"admin": "admin-secret", "member": "member-secret"}


def select(records: list[dict], env: str, resource: str | None = None, since: str | None = None) -> list[dict]:
    """Newest first, so a delete that depends on order removes children before parents."""
    chosen = [r for r in records if r["env"] == env]
    if resource:
        chosen = [r for r in chosen if r["resource"] == resource]
    if since:
        chosen = [r for r in chosen if r["created_at"] >= since]
    seen, unique = set(), []
    for record in reversed(chosen):
        key = (record["resource"], record["entity_id"])
        if key not in seen:
            seen.add(key)
            unique.append(record)
    return unique


def summarise(records: list[dict]) -> str:
    counts = Counter(record["resource"] for record in records)
    return ", ".join(f"{count} {resource}" for resource, count in sorted(counts.items())) or "nothing"


class _Resource(Base):
    """A minimal handle for a resource name the ledger recorded."""

    def __init__(self, client: ApiClient, resource: str) -> None:
        self.resource = resource
        super().__init__(client)


def delete_all(client: ApiClient, records: list[dict]) -> dict[str, int]:
    """Delete each recorded entity, counting what happened to it."""
    assert_not_prod("cleanup")

    result = {"deleted": 0, "already gone": 0, "refused": 0, "failed": 0}
    for record in records:
        handle = _Resource(client, record["resource"])
        status = handle.delete_by_id(record["entity_id"], persona="admin").status_code
        if status in (200, 202, 204):
            result["deleted"] += 1
        elif status == 404:
            result["already gone"] += 1
        elif status in (401, 403, 405):
            result["refused"] += 1
        else:
            result["failed"] += 1
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, help="only objects created on this environment")
    parser.add_argument("--resource", help="limit to one resource, e.g. orders")
    parser.add_argument("--since", help="only objects created at or after this ISO timestamp")
    parser.add_argument("--yes", action="store_true", help="actually delete; without it nothing is removed")
    args = parser.parse_args()

    if args.env == "prod":
        print("refusing to clean up prod")
        return 2

    records = select(load(REPORTS / "artifacts.jsonl"), args.env, args.resource, args.since)
    if not records:
        print(f"nothing recorded for {args.env}")
        return 0

    print(f"{len(records)} object(s) on {args.env}: {summarise(records)}")
    if not args.yes:
        for record in records[:10]:
            print(f"  would delete {record['resource']} {record['entity_id']}")
        if len(records) > 10:
            print(f"  ... and {len(records) - 10} more")
        print("\nnothing was deleted. Re-run with --yes to remove them.")
        return 0

    client = ApiClient(env=args.env)
    for persona in ("admin", "member"):
        client.register_persona(persona, client.config[f"{persona}_user"], PASSWORDS[persona])

    outcome = delete_all(client, records)
    print("  " + " · ".join(f"{count} {label}" for label, count in outcome.items() if count))
    return 1 if outcome["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
