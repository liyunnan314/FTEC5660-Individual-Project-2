"""Real-LLM follow-up experiment (Edge Case A, with a live DeepSeek key)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

if not os.environ.get("DEEPSEEK_API_KEY"):
    raise SystemExit("DEEPSEEK_API_KEY is not set; see docs/REAL_LLM_UPGRADE.md")

# Placeholders stop upstream constructors from probing for absent credentials.
for _key in ("OPENAI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY",
             "XAI_API_KEY", "ALPHA_VANTAGE_API_KEY", "FRED_API_KEY",
             "OPENROUTER_API_KEY"):
    os.environ.setdefault(_key, "placeholder-not-a-real-key")

from pytest import MonkeyPatch  # noqa: E402

from offline_harness import (  # noqa: E402
    EXPECTED_TOOL_METHODS, REPORT_FIELDS, build_config, install, load_dataset,
)
from real_llm_harness import UsageHandler  # noqa: E402
from scripted_model import RATINGS, TRADE_DATE  # noqa: E402
from tradingagents.graph.trading_graph import TradingAgentsGraph  # noqa: E402

logging.disable(logging.WARNING)

TICKER = "NVDA"
DATES = ("2025-12-15", "2025-12-22", "2026-01-05")
OUT = ROOT / "results" / "real_llm"
ARMS = {
    arm: json.loads((ROOT / "configs" / f"{arm}.json").read_text(encoding="utf-8"))
    for arm in ("baseline", "modified")
}

# The model is the only difference; both tiers use the same one.
REAL_LLM_CONFIG = {
    "llm_provider": "deepseek",
    "quick_think_llm": "deepseek-flash",
    "deep_think_llm": "deepseek-flash",
    "backend_url": "https://api.deepseek.com/v1",
    "temperature": 0.0,
    "max_tokens": 2048,
}

FIELDS = [
    "arm", "trial", "ticker", "date", "max_debate_rounds", "success", "error",
    "signal", "final_rating", "rating_legal", "elapsed_s", "llm_calls",
    "input_tokens", "output_tokens", "total_tokens", "prompt_chars",
    "llm_seconds", "llm_errors", "data_methods", "reports",
]


def config_record(dataset_path: Path) -> dict:
    sha = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    return {
        "provider": "deepseek",
        "model_quick": REAL_LLM_CONFIG["quick_think_llm"],
        "model_deep": REAL_LLM_CONFIG["deep_think_llm"],
        "model_note": ("The deepseek-chat alias is deprecated upstream "
                       "(2026-07-24) and now maps to V4 Flash; the API response "
                       "reports model=deepseek-flash. The official ID is used here "
                       "so upstream suppresses tool_choice for this thinking model."),
        "base_url": REAL_LLM_CONFIG["backend_url"],
        "api_key": "present (value never recorded)",
        "temperature": REAL_LLM_CONFIG["temperature"],
        "max_tokens": REAL_LLM_CONFIG["max_tokens"],
        "prompt_or_template_changes": "none",
        "dataset_sha256": sha,
        "trade_date_in_dataset": TRADE_DATE,
        "ticker": TICKER,
        "dates": list(DATES),
        "arms": {k: v for k, v in ARMS.items()},
    }


def run_cell(dataset, arm: str, trial: int, date: str, work_dir: Path) -> tuple[dict, dict]:
    """One live-model pipeline run with pinned data and callback instrumentation."""
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    handler = UsageHandler()
    mp = MonkeyPatch()
    called = install(mp, None, dataset, TICKER, patch_llm=False)
    record = {
        "arm": arm, "trial": trial, "ticker": TICKER, "date": date,
        "max_debate_rounds": ARMS[arm]["max_debate_rounds"],
        "success": False, "error": None,
    }
    raw: dict = {}
    try:
        cfg = build_config(work_dir, **{**ARMS[arm], **REAL_LLM_CONFIG})
        graph = TradingAgentsGraph(config=cfg, callbacks=[handler])
        t0 = time.perf_counter()
        state, signal = graph.propagate(TICKER, date)
        elapsed = time.perf_counter() - t0

        reports = sum(bool(str(state.get(k, "")).strip()) for k in REPORT_FIELDS)
        raw = {k: str(state.get(k, ""))[:20000] for k in REPORT_FIELDS}
        raw["signal"] = str(signal)
        raw["rating_legal"] = str(signal) in RATINGS

        record.update({
            "success": True,
            "signal": str(signal),
            "final_rating": str(state.get("final_rating")),
            "rating_legal": str(signal) in RATINGS,
            "elapsed_s": round(elapsed, 3),
            "data_methods": len(called & EXPECTED_TOOL_METHODS),
            "reports": reports,
            **{k: v for k, v in handler.snapshot().items()
               if k in ("llm_calls", "input_tokens", "output_tokens", "total_tokens",
                        "prompt_chars", "llm_seconds", "llm_errors")},
        })
    except Exception as exc:  # keep the grid running
        record["error"] = f"{type(exc).__name__}: {exc}"[:500]
        raw = {"error": record["error"]}
    finally:
        mp.undo()
    return record, raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("baseline", "modified", "both"), default="both")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--dates", type=int, default=0,
                    help="0 = all three dates; otherwise take the first N")
    args = ap.parse_args()

    dataset = load_dataset(ROOT / "data" / "synthetic_prices.csv")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "raw").mkdir(exist_ok=True)
    (OUT / "config_record.json").write_text(
        json.dumps(config_record(ROOT / "data" / "synthetic_prices.csv"), indent=2),
        encoding="utf-8",
    )

    dates = DATES[: args.dates] if args.dates else DATES
    arms = ("baseline", "modified") if args.arm == "both" else (args.arm,)
    rows, raws = [], {}
    for arm in arms:
        for date in dates:
            for trial in range(args.trials):
                work_dir = OUT / "work" / f"{arm}_{date}_{trial}"
                t0 = time.perf_counter()
                record, raw = run_cell(dataset, arm, trial, date, work_dir)
                row = {k: record.get(k, "") for k in FIELDS}
                rows.append(row)
                raws[f"{arm}_{date}_{trial}"] = raw
                print(
                    f"[{arm:8s} {date} t{trial}] "
                    f"ok={record['success']} signal={record.get('signal', '-')} "
                    f"calls={record.get('llm_calls', 0):2d} "
                    f"tokens={record.get('total_tokens', 0):5d} "
                    f"{time.perf_counter() - t0:6.1f}s "
                    f"{record.get('error') or ''}",
                    flush=True,
                )

    with (OUT / "cells.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "cells.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (OUT / "raw_responses.json").write_text(json.dumps(raws, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    print(f"\nwrote {len(rows)} records to {OUT}")


if __name__ == "__main__":
    main()
