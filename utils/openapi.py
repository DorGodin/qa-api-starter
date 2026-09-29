"""Validate responses against the API's own OpenAPI document.

Asserting field by field is fine for the handful of fields a test cares about.
It does not notice a field that quietly changed type somewhere else. The spec
already describes every response, so use it: one helper covers drift across the
whole surface.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import jsonschema
import requests

from utils.helpers import cached_lookup


@cached_lookup
def load_spec(base_url: str) -> dict[str, Any]:
    resp = requests.get(f"{base_url.rstrip('/')}/openapi.json", timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(
            f"no OpenAPI document at {base_url}/openapi.json (got {resp.status_code}). "
            "Point `spec_url` at wherever the product publishes it."
        )
    return resp.json()


def response_schema(spec: dict, method: str, path: str, status: int) -> dict | None:
    """The declared schema for one response, or None when the spec does not describe it."""
    operation = spec.get("paths", {}).get(path, {}).get(method.lower())
    if operation is None:
        raise KeyError(f"{method.upper()} {path} is not in the OpenAPI document")

    response = operation.get("responses", {}).get(str(status))
    if response is None:
        return None
    return response.get("content", {}).get("application/json", {}).get("schema")


def validate(spec: dict, payload: Any, method: str, path: str, status: int) -> None:
    """Raise AssertionError with a readable message when the payload does not match."""
    schema = response_schema(spec, method, path, status)
    if schema is None:
        return

    resolved = dict(schema)
    resolved["components"] = spec.get("components", {})
    resolved["$defs"] = spec.get("components", {}).get("schemas", {})

    try:
        jsonschema.validate(payload, resolved)
    except jsonschema.ValidationError as err:
        location = "/".join(str(part) for part in err.absolute_path) or "(root)"
        raise AssertionError(
            f"{method.upper()} {path} -> {status} does not match its own OpenAPI schema.\n"
            f"  at: {location}\n  problem: {err.message}"
        ) from None


@lru_cache(maxsize=1)
def documented_operations(base_url: str) -> tuple[tuple[str, str], ...]:
    spec = load_spec(base_url)
    return tuple(
        (method.upper(), path)
        for path, operations in spec.get("paths", {}).items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    )
