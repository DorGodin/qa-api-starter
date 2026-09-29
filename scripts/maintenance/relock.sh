#!/usr/bin/env bash
# Re-resolve requirements.txt into requirements.lock.txt. Commit both together.
set -euo pipefail
cd "$(dirname "$0")/../.."
.venv/bin/pip install -r requirements.txt
.venv/bin/pip freeze > requirements.lock.txt
echo "requirements.lock.txt updated - commit it with requirements.txt"
