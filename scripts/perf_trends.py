#!/usr/bin/env python3
"""Compare the last perf run against earlier runs of the same shape.

python scripts/perf_trends.py            # report
python scripts/perf_trends.py --check    # exit non-zero when a threshold was crossed

A p95 rise is reported but never blocks: latency on a shared runner is noisy,
and a gate that fires on noise is a gate people learn to ignore. What blocks is
what k6 already judged - a crossed threshold.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.artifacts import load  # noqa: E402
from utils.perf_history import blocking, compare, format_findings  # noqa: E402

REPORTS = Path(__file__).resolve().parents[1] / "reports"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--check", action="store_true", help="exit 1 when the last run crossed a threshold")
    parser.add_argument("--baseline", type=int, default=5, help="how many earlier runs of the same shape")
    parser.add_argument("--tolerance", type=float, default=0.25, help="p95 rise that is worth reporting")
    args = parser.parse_args()

    findings = compare(load(REPORTS / "perf.jsonl"), baseline_size=args.baseline, tolerance=args.tolerance)
    print(format_findings(findings))
    raise SystemExit(1 if args.check and blocking(findings) else 0)
