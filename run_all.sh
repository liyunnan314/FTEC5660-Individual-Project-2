#!/usr/bin/env bash
# Regenerate all artefacts in dependency order.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"

echo "[1/6] pinned synthetic dataset"
"$PY" src/make_dataset.py
echo "[2/6] offline end-to-end sanity check"
"$PY" src/smoke.py | tail -3
echo "[3/6] upstream offline end-to-end test suite"
"$PY" -m pytest vendor/TradingAgents/tests/test_graph_end_to_end.py -q \
  > results/tables/upstream_test_output.txt 2>&1
tail -1 results/tables/upstream_test_output.txt
echo "[4/6] controlled experiment (5 paired trials x 2 arms)"
"$PY" src/run_experiment.py --arm both --trials 5 > results/tables/experiment_log.txt 2>&1
tail -1 results/tables/experiment_log.txt
echo "[5/6] dose-response + analysis"
"$PY" src/sweep_rounds.py > results/tables/sweep_log.txt 2>&1
"$PY" src/analyze.py > results/tables/analyze_log.txt 2>&1
echo "[6/6] report"
"$PY" report/build_report.py
echo "Done. Report: report/reproducibility_report.pdf"
