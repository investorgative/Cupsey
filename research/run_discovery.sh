#!/usr/bin/env bash
# Re-runs the shadow wallet discovery (≈1000 SolanaTracker credits, ~45 min on the free rate limit).
# Usage on the Pi:  bash research/run_discovery.sh   then   sudo systemctl restart shadowwatch
set -euo pipefail
cd "$(dirname "$0")"
set -a; [ -f ../.env ] && . ../.env; set +a
[ -n "${SOLANATRACKER_API_KEY:-}" ] || { echo "Set SOLANATRACKER_API_KEY in .env"; exit 1; }
PY=../.venv/bin/python; [ -x "$PY" ] || PY=python3
rm -f features.json scored.json bundle.json preccache.json
rm -rf tok
$PY fetch_cupsey.py
$PY collect.py
$PY analyze.py > /dev/null
$PY score.py
$PY bundle.py
$PY export.py
echo "Done -> shadowwatch/data/wallets.json. Restart: sudo systemctl restart shadowwatch"
