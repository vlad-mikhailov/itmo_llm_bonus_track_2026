#!/bin/bash
# Load testing suite for LLM Agent Platform.
# Requires: pip install locust
# Usage: ./run_tests.sh [host]

set -euo pipefail

HOST="${1:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"

mkdir -p "$RESULTS_DIR"

echo "=== LLM Agent Platform Load Tests ==="
echo "Host: $HOST"
echo "Results: $RESULTS_DIR"
echo ""

# Ensure MASTER_TOKEN is set
if [ -z "${MASTER_TOKEN:-}" ]; then
    echo "WARNING: MASTER_TOKEN not set. Using default test token."
    echo "  export MASTER_TOKEN=<your-token> to use a real token."
    echo ""
fi

echo "--- Scenario 1: Normal Load (15 users, 60s) ---"
locust -f "$SCRIPT_DIR/locustfile.py" \
    --headless \
    --users 15 \
    --spawn-rate 5 \
    --run-time 60s \
    --host "$HOST" \
    --only-summary \
    --csv "$RESULTS_DIR/normal" \
    --loglevel WARNING \
    2>&1 || true

echo ""
echo "--- Scenario 2: Peak Load (30 users, 60s) ---"
locust -f "$SCRIPT_DIR/locustfile.py" \
    --headless \
    --users 30 \
    --spawn-rate 10 \
    --run-time 60s \
    --host "$HOST" \
    --only-summary \
    --csv "$RESULTS_DIR/peak" \
    --loglevel WARNING \
    2>&1 || true

echo ""
echo "--- Scenario 3: Stress Test (50 users, 30s) ---"
LOCUST_MAX_REQUESTS=300 locust -f "$SCRIPT_DIR/locustfile.py" \
    --headless \
    --users 50 \
    --spawn-rate 20 \
    --run-time 30s \
    --host "$HOST" \
    --only-summary \
    --csv "$RESULTS_DIR/stress" \
    --loglevel WARNING \
    2>&1 || true

echo ""
echo "=== Results saved to $RESULTS_DIR ==="
echo "CSV files: normal_stats.csv, peak_stats.csv, stress_stats.csv"
