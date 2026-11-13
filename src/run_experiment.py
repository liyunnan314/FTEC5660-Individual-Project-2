"""Run the controlled reproduction experiment.

Two arms differ in exactly ONE upstream config key: ``max_debate_rounds``
(1 = upstream default, 3 = modification). Everything else is held fixed:
same upstream commit, same pinned synthetic dataset, same scripted model
class, same seeds, same ticker/date grid, same measurement code.

Usage:
    .venv/bin/python src/run_experiment.py --arm both --trials 5
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Placeholder keys only. The real client factory is replaced at runtime, so no
# credential is ever used or required. Nothing secret is written to disk.
for _key in ("OPENAI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY",
             "DEEPSEEK_API_KEY", "XAI_API_KEY", "ALPHA_VANTAGE_API_KEY",
             "FRED_API_KEY", "OPENROUTER_API_KEY"):
    os.environ.setdefault(_key, "placeholder-not-a-real-key")

from pytest import MonkeyPatch  # noqa: E402

from offline_harness import (  # noqa: E402
    EXPECTED_TOOL_METHODS, REPORT_FIELDS, build_config, install, load_dataset,
)
from scripted_model import RATINGS, TRADE_DATE, SeedScriptedModel  # noqa: E402
from tradingagents.graph.trading_graph import TradingAgentsGraph  # noqa: E402

logging.disable(logging.WARNING)  # upstream free-text fallback warnings

# The two arms live in configs/*.json so the modification is a reviewable diff.
ARMS = {
    arm: json.loads((ROOT / "configs" / f"{arm}.json").read_text(encoding="utf-8"))
    for arm in ("baseline", "modified")
}
TICKER = "NVDA"
# All dates lie inside the pinned dataset and leave a 5-day settlement window.
DATES = ("2025-12-15", "2025-12-22", "2026-01-05")


def run_cell(dataset, arm: str, trial: int, date: str, work_dir: Path) -> dict:
    """One independent, fully offline run of the upstream pipeline."""
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    model = SeedScriptedModel(seed=trial)
    mp = MonkeyPatch()
    called = install(mp, model, dataset, TICKER)
    record = {
        "arm": arm, "trial": trial, "ticker": TICKER, "date": date,
        "seed": trial, "max_debate_rounds": ARMS[arm]["max_debate_rounds"],
        "success": False, "error": None,
    }
    try:
        cfg = build_config(work_dir, **ARMS[arm])
        graph = TradingAgentsGraph(config=cfg)
        t0 = time.perf_counter()
        state, signal = graph.propagate(TICKER, date)
        elapsed = time.perf_counter() - t0

        nodes = Counter(c["node"] for c in model.stats["calls"] if c["node"])
        missing = sorted(EXPECTED_TOOL_METHODS - called)
        reports = sum(bool(str(state.get(k, "")).strip()) for k in REPORT_FIELDS)
        record.update({
            "success": True,
            "signal": str(signal),
            "final_rating": str(state.get("final_rating")),
            "rating_legal": str(signal) in RATINGS,
            "signal_matches_state": str(signal) == str(state.get("final_rating")),
            "elapsed_s": round(elapsed, 6),
            "llm_calls": len(model.stats["calls"]),
            "tool_turns": len(model.stats["tool_calls"]),
            "tool_invocations": model.stats["tool_invocations"],
            "prompt_chars": model.stats["prompt_chars"],
            "threads": len(model.stats["threads"]),
            "data_methods": len(called),
            "data_methods_missing": len(missing),
            "reports_nonempty": reports,
            "reports_expected": len(REPORT_FIELDS),
            "bull_calls": nodes.get("Bull Researcher", 0),
            "bear_calls": nodes.get("Bear Researcher", 0),
            "research_manager_calls": nodes.get("Research Manager", 0),
            "nodes": dict(nodes),
        })
    except Exception as exc:  # a failed cell is data, not a crash of the sweep
        record["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        mp.undo()
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("baseline", "modified", "both"), default="both")
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--out", type=Path, default=ROOT / "results")
    args = ap.parse_args()

    dataset = load_dataset(ROOT / "data" / "synthetic_prices.csv")
    out = args.out
    (out / "raw").mkdir(parents=True, exist_ok=True)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    arms = list(ARMS) if args.arm == "both" else [args.arm]

    all_rows = []
    for arm in arms:
        for trial in range(args.trials):
            for date in DATES:
                work = out / "raw" / arm / f"trial_{trial}" / f"cell_{date}"
                rec = run_cell(dataset, arm, trial, date, work)
                all_rows.append(rec)
                raw_path = work / "metrics.json"
                raw_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
                status = "OK" if rec["success"] else f"FAIL {rec['error']}"
                print(f"[{arm:8s}] trial={trial} date={date} "
                      f"calls={rec.get('llm_calls', '-'):>3} "
                      f"rating={rec.get('signal', '-'):<11} {status}")

    # ---- cell-level table ----
    import csv
    fields = ["arm", "trial", "date", "ticker", "seed", "max_debate_rounds",
              "success", "signal", "rating_legal", "signal_matches_state",
              "llm_calls", "tool_turns", "tool_invocations", "prompt_chars", "data_methods",
              "data_methods_missing", "reports_nonempty", "bull_calls",
              "bear_calls", "research_manager_calls", "threads", "elapsed_s", "error"]
    with (out / "tables" / "cells.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)

    # ---- trial-level aggregate (the unit reported as mean/variance) ----
    trial_rows = []
    for arm in arms:
        for trial in range(args.trials):
            rows = [r for r in all_rows if r["arm"] == arm and r["trial"] == trial]
            ok = [r for r in rows if r["success"]]
            trial_rows.append({
                "arm": arm, "trial": trial, "cells": len(rows),
                "cells_ok": len(ok),
                "success_rate": len(ok) / len(rows) if rows else 0,
                "rating_legal_rate": sum(r["rating_legal"] for r in ok) / len(ok) if ok else 0,
                "mean_llm_calls": statistics.mean(r["llm_calls"] for r in ok) if ok else 0,
                "mean_tool_turns": statistics.mean(r["tool_turns"] for r in ok) if ok else 0,
                "mean_tool_invocations": statistics.mean(r["tool_invocations"] for r in ok) if ok else 0,
                "mean_prompt_chars": statistics.mean(r["prompt_chars"] for r in ok) if ok else 0,
                "mean_data_methods": statistics.mean(r["data_methods"] for r in ok) if ok else 0,
                "mean_reports": statistics.mean(r["reports_nonempty"] for r in ok) if ok else 0,
                "mean_bull_calls": statistics.mean(r["bull_calls"] for r in ok) if ok else 0,
                "mean_bear_calls": statistics.mean(r["bear_calls"] for r in ok) if ok else 0,
                "mean_elapsed_s": statistics.mean(r["elapsed_s"] for r in ok) if ok else 0,
                "ratings": ",".join(r["signal"] for r in ok),
            })
    with (out / "tables" / "trials.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(trial_rows[0]))
        w.writeheader()
        w.writerows(trial_rows)

    # ---- arm-level summary ----
    metrics = ["success_rate", "rating_legal_rate", "mean_llm_calls",
               "mean_tool_turns", "mean_tool_invocations",
               "mean_prompt_chars", "mean_data_methods",
               "mean_reports", "mean_bull_calls", "mean_bear_calls", "mean_elapsed_s"]
    summary_rows = []
    for arm in arms:
        rows = [r for r in trial_rows if r["arm"] == arm]
        row = {"arm": arm, "max_debate_rounds": ARMS[arm]["max_debate_rounds"],
               "trials": len(rows)}
        for m in metrics:
            vals = [r[m] for r in rows]
            row[f"{m}_mean"] = round(statistics.mean(vals), 6)
            row[f"{m}_std"] = round(statistics.pstdev(vals), 6)
        summary_rows.append(row)
    with (out / "tables" / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary_rows[0]))
        w.writeheader()
        w.writerows(summary_rows)

    # ---- audit: prove the modification is isolated ----
    audit = {
        "upstream_repo": "https://github.com/TauricResearch/TradingAgents",
        "upstream_commit": "9fa1196fffbcfd9de5146d2dd2869df84ab99838",
        "upstream_version": "0.7.1",
        "target_capability": (
            "tests/test_graph_end_to_end.py::test_a_full_run_reaches_a_logged_decision "
            "and the README's claim that the LangGraph multi-agent pipeline runs "
            "analysts -> debate -> trader -> risk -> portfolio manager end to end"
        ),
        "controlled_variable": "LLM replaced by in-process deterministic scripted stub",
        "dataset": str(ROOT / "data" / "synthetic_prices.csv"),
        "grid": {"tickers": [TICKER], "dates": list(DATES)},
        "trials": args.trials,
        "arms": {k: {"config_diff": v, "everything_else": "identical to the other arm"}
                 for k, v in ARMS.items()},
        "isolated_change": {"key": "max_debate_rounds", "from": 1, "to": 3},
        "seeds": list(range(args.trials)),
    }
    (out / "tables" / "experiment_audit.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8")

    print(f"\nwrote {len(all_rows)} cell records -> {out / 'tables'}")
    return 0 if all(r["success"] for r in all_rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
