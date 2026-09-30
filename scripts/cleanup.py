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
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from obj import ApiClient  # noqa: E402
from obj.base import Base  # noqa: E402
from utils.artifacts import load  # noqa: E402
from utils.helpers import assert_not_prod  # noqa: E402
from utils.openapi import documented_operations  # noqa: E402

REPORTS = Path(__file__).resolve().parents[1] / "reports"


def select(
    records: list[dict], env: str, resource: str | None = None, since: str | None = None
) -> list[dict]:
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


def deletable_resources(operations: tuple[tuple[str, str], ...]) -> set[str]:
    """Resources whose OpenAPI document has DELETE /{resource}/{id}."""
    found = set()
    for method, path in operations:
        match = re.fullmatch(r"/([^/{}]+)/\{[^/]+\}", path)
        if method == "DELETE" and match:
            found.add(match.group(1))
    return found


def delete_all(client: ApiClient, records: list[dict], deletable: set[str] | None = None) -> dict[str, int]:
    """Delete each recorded entity, counting what happened to it.

    A 404 answers two different questions with one number: "that entity is
    gone" and "there is no DELETE here at all". Counting every 404 as gone once
    reported 2300 objects removed from a product that cannot delete anything.
    With the product's OpenAPI document (`deletable`), a resource that has no
    delete endpoint is reported as such and never called. Without it, a 404 is
    reported as what it is - not found - and not as a deletion.
    """
    assert_not_prod("cleanup")

    result = {
        "deleted": 0,
        "already gone": 0,
        "no delete endpoint": 0,
        "not found": 0,
        "refused": 0,
        "failed": 0,
    }
    for record in records:
        if deletable is not None and record["resource"] not in deletable:
            result["no delete endpoint"] += 1
            continue
        handle = _Resource(client, record["resource"])
        status = handle.delete_by_id(record["entity_id"], persona=client.config["admin_persona"]).status_code
        if status in (200, 202, 204):
            result["deleted"] += 1
        elif status == 404:
            result["already gone" if deletable is not None else "not found"] += 1
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

    client = ApiClient(env=args.env).login_personas()
    try:
        deletable = deletable_resources(documented_operations(client.base_url))
    except Exception:  # noqa: BLE001 - no spec is a normal product, not a crash
        deletable = None
        print("  (no OpenAPI document: a 404 cannot be told apart from a missing delete endpoint)")

    outcome = delete_all(client, records, deletable)
    print("  " + " · ".join(f"{count} {label}" for label, count in outcome.items() if count))
    if outcome["no delete endpoint"]:
        print(
            f"  {outcome['no delete endpoint']} object(s) cannot be removed through this product's API. "
            "They stay until the environment is reset some other way."
        )
    return 1 if outcome["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
