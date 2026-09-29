"""Load test scenarios from files.

A scenario that lives in a CSV can be added by someone who does not write
Python, reviewed by someone who does not read Python, and kept next to the rules
it encodes. The test stays one function.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

SCENARIOS = Path(__file__).resolve().parents[1] / "data" / "scenarios"


def load_csv(name: str) -> list[dict[str, str]]:
    path = SCENARIOS / name
    if not path.exists():
        raise FileNotFoundError(f"no scenario file at {path}. Scenarios live in data/scenarios/.")

    with path.open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if any(value.strip() for value in row.values())]

    if not rows:
        raise AssertionError(f"{name} has no scenarios; an empty file would silently test nothing")
    return rows


def load_json(name: str) -> Any:
    path = SCENARIOS / name
    if not path.exists():
        raise FileNotFoundError(f"no scenario file at {path}. Scenarios live in data/scenarios/.")
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: str) -> float | None:
    value = (value or "").strip()
    return float(value) if value else None
