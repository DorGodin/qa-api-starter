#!/usr/bin/env python3
"""Compare the last run against the runs before it.

    python scripts/trends.py            # report
    python scripts/trends.py --check    # exit non-zero when something regressed
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.artifacts import load  # noqa: E402
from utils.trends import blocking, compare, format_findings  # noqa: E402

REPORTS = Path(__file__).resolve().parents[1] / "reports"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when a blocking regression is found")
    parser.add_argument("--baseline", type=int, default=5, help="how many previous runs to judge against")
    args = parser.parse_args()

    findings = compare(load(REPORTS / "history.jsonl"), baseline_size=args.baseline)
    print(format_findings(findings))
    raise SystemExit(1 if args.check and blocking(findings) else 0)
