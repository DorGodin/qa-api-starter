#!/usr/bin/env bash
# Rerun one test many times and report how often it fails.
#
#   scripts/flake_check.sh tests/suites/test_order_flow.py::test_totals 30
#   scripts/flake_check.sh tests/suites/test_order_flow.py::test_totals 30 --module
#
# Alone vs with its module is the whole diagnosis: green alone and red together
# means an earlier test leaves state behind.
set -uo pipefail
cd "$(dirname "$0")/.."

NODEID="${1:?usage: flake_check.sh <nodeid> [runs] [--module]}"
RUNS="${2:-20}"
TARGET="$NODEID"
[[ "${3:-}" == "--module" ]] && TARGET="${NODEID%%::*}"

PY="${PY:-.venv/bin/python}"
FLAGS=""
[[ "$TARGET" == *"tests/unit"* ]] && FLAGS="--unit"
[[ "$TARGET" == *"tests/edge-cases"* ]] && FLAGS="--edge-cases"
[[ "$TARGET" == *"tests/ui"* ]] && FLAGS="--ui"
[[ "$TARGET" == *"tests/llm"* ]] && FLAGS="--llm"

fails=0
for i in $(seq 1 "$RUNS"); do
  if ! PYTHONPATH=. $PY -m pytest $FLAGS "$TARGET" -q >/dev/null 2>&1; then
    fails=$((fails + 1))
    printf 'x'
  else
    printf '.'
  fi
done
echo
echo "target : $TARGET"
echo "runs   : $RUNS"
echo "failed : $fails"

if [[ "$fails" -eq 0 ]]; then
  echo "verdict: stable in this configuration"
elif [[ "$fails" -eq "$RUNS" ]]; then
  echo "verdict: fails every time - this is not flakiness, it is a broken test or a broken product"
else
  echo "verdict: intermittent ($((fails * 100 / RUNS))%) - rerun with and without --module to tell order dependence from a genuinely unstable test"
fi
