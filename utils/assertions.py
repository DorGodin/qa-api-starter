"""Assertions shared by more than one suite."""

from __future__ import annotations

from obj.client import Response


def assert_refused(resp: Response, status: int, code: str) -> None:
    """A refusal is the status AND the product's machine-readable code. The status
    alone cannot tell "slot taken" from "you already have a booking then" - both
    are 409, and they mean different things to the person booking."""
    assert resp.status_code == status, f"expected {status} {code}, got {resp.status_code}: {resp.as_dict}"
    assert resp.as_dict.get("code") == code, f"expected code {code!r}: {resp.as_dict}"
