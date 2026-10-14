#!/usr/bin/env bash
# Run the access review on the bundled sample data (or pass your own flags).
set -euo pipefail
cd "$(dirname "$0")"
python -m access_review --as-of 2026-10-14 "$@"
