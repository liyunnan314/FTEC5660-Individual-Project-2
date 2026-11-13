#!/usr/bin/env bash
# Clone and pin upstream, create .venv, install deps. No API keys are read.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM_SHA="9fa1196fffbcfd9de5146d2dd2869df84ab99838"
UPSTREAM_URL="https://github.com/TauricResearch/TradingAgents.git"
VENDOR_DIR="$ROOT/vendor/TradingAgents"

echo "==> 1/3  Cloning upstream TradingAgents at pinned commit $UPSTREAM_SHA"
if [ ! -d "$VENDOR_DIR/.git" ]; then
  git clone --quiet "$UPSTREAM_URL" "$VENDOR_DIR"
fi
git -C "$VENDOR_DIR" checkout --quiet "$UPSTREAM_SHA"

echo "==> 2/3  Creating isolated virtual environment (avoids PEP 668 conflicts)"
python3.11 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install --quiet --disable-pip-version-check \
  -e "$VENDOR_DIR" pytest matplotlib weasyprint

echo "==> 3/3  Verifying imports"
"$ROOT/.venv/bin/python" -c \
  "import tradingagents, langgraph, matplotlib, weasyprint; print('OK: tradingagents', tradingagents.__version__)"

echo ""
echo "Setup complete. Next:"
echo "  .venv/bin/python src/make_dataset.py"
echo "  .venv/bin/python src/smoke.py"
echo "  .venv/bin/python src/run_experiment.py --arm both --trials 5"
