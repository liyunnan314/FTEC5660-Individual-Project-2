"""Dose-response diagnostic for the SAME single modification.

Runs the identical offline cell with ``max_debate_rounds`` in 1..5. This is not
a second modification: it characterises how the one changed parameter affects
cost, which is what makes the modification's impact interpretable.
"""

from __future__ import annotations

import csv
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
for _key in ("OPENAI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY",
             "DEEPSEEK_API_KEY", "ALPHA_VANTAGE_API_KEY", "FRED_API_KEY"):
    os.environ.setdefault(_key, "placeholder-not-a-real-key")
logging.disable(logging.WARNING)

from pytest import MonkeyPatch  # noqa: E402
from offline_harness import load_dataset, install, build_config  # noqa: E402
from scripted_model import SeedScriptedModel, TRADE_DATE  # noqa: E402
from tradingagents.graph.trading_graph import TradingAgentsGraph  # noqa: E402


def main() -> int:
    dataset = load_dataset(ROOT / "data" / "synthetic_prices.csv")
    rows = []
    for rounds in range(1, 6):
        work = ROOT / "results" / "raw" / "_sweep" / f"rounds_{rounds}"
        mp = MonkeyPatch()
        model = SeedScriptedModel(seed=0)
        install(mp, model, dataset, "NVDA")
        try:
            cfg = build_config(work, max_debate_rounds=rounds)
            graph = TradingAgentsGraph(config=cfg)
            state, signal = graph.propagate("NVDA", TRADE_DATE)
            from collections import Counter
            nodes = Counter(c["node"] for c in model.stats["calls"] if c["node"])
            rows.append({
                "max_debate_rounds": rounds,
                "llm_calls": len(model.stats["calls"]),
                "bull_calls": nodes.get("Bull Researcher", 0),
                "bear_calls": nodes.get("Bear Researcher", 0),
                "prompt_chars": model.stats["prompt_chars"],
                "signal": str(signal),
                "reports_nonempty": sum(
                    bool(str(state.get(k, "")).strip())
                    for k in ("market_report", "sentiment_report", "news_report",
                              "fundamentals_report", "investment_plan",
                              "trader_investment_plan", "final_trade_decision")),
            })
            print(f"rounds={rounds} calls={rows[-1]['llm_calls']} "
                  f"prompt_chars={rows[-1]['prompt_chars']} signal={signal}")
        finally:
            mp.undo()

    out = ROOT / "results" / "tables" / "rounds_sweep.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
