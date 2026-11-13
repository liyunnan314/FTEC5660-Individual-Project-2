"""One-shot sanity check: can the upstream graph reach a decision fully offline?"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pytest import MonkeyPatch  # noqa: E402

from offline_harness import (  # noqa: E402
    EXPECTED_TOOL_METHODS, REPORT_FIELDS, build_config, install, load_dataset,
)
from scripted_model import TRADE_DATE, SeedScriptedModel  # noqa: E402
from tradingagents.graph.trading_graph import TradingAgentsGraph  # noqa: E402


def main() -> int:
    dataset = load_dataset(ROOT / "data" / "synthetic_prices.csv")
    work = ROOT / "results" / "raw" / "_smoke"
    work.mkdir(parents=True, exist_ok=True)

    mp = MonkeyPatch()
    model = SeedScriptedModel(seed=0)
    called = install(mp, model, dataset, "NVDA")
    try:
        cfg = build_config(work)
        graph = TradingAgentsGraph(config=cfg)
        t0 = time.perf_counter()
        state, signal = graph.propagate("NVDA", TRADE_DATE)
        elapsed = time.perf_counter() - t0
        summary = {
            "signal": signal,
            "final_rating": state.get("final_rating"),
            "elapsed_s": round(elapsed, 4),
            "llm_calls": len(model.stats["calls"]),
            "tool_calls": len(model.stats["tool_calls"]),
            "prompt_chars": model.stats["prompt_chars"],
            "threads": len(model.stats["threads"]),
            "data_methods_reached": sorted(called),
            "data_methods_expected": sorted(EXPECTED_TOOL_METHODS),
            "missing_data_methods": sorted(EXPECTED_TOOL_METHODS - called),
            "reports_nonempty": sum(bool(str(state.get(k, "")).strip()) for k in REPORT_FIELDS),
            "reports_expected": len(REPORT_FIELDS),
            "nodes": sorted({c["node"] for c in model.stats["calls"] if c["node"]}),
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        ok = (signal == state.get("final_rating")
              and not summary["missing_data_methods"]
              and summary["reports_nonempty"] == summary["reports_expected"])
        print("SMOKE_OK" if ok else "SMOKE_FAILED")
        return 0 if ok else 1
    finally:
        mp.undo()


if __name__ == "__main__":
    raise SystemExit(main())
