"""Summarize the live-DeepSeek follow-up experiment."""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "results" / "real_llm"
FIG = ROOT / "results" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

rows = list(csv.DictReader((SRC / "cells.csv").open(encoding="utf-8")))
ok = [r for r in rows if r["success"] == "True"]
NUM = ("llm_calls", "input_tokens", "output_tokens", "total_tokens",
       "prompt_chars", "elapsed_s", "llm_seconds", "data_methods", "reports")


def num(r, k):
    try:
        return float(r.get(k) or 0)
    except ValueError:
        return 0.0


def mean(rs, k):
    return statistics.mean(num(r, k) for r in rs) if rs else 0.0


def summarize(arm: str) -> dict:
    all_rs = [r for r in rows if r["arm"] == arm]
    rs = [r for r in all_rs if r["success"] == "True"]
    return {
        "n_cells": len(all_rs),
        "n_success": len(rs),
        "rating_legal": sum(r["rating_legal"] == "True" for r in rs),
        "decisions": dict(Counter(r["signal"] for r in rs)),
        **{f"mean_{k}": round(mean(rs, k), 2) for k in NUM},
    }


by_key = {(r["arm"], r["date"], r["trial"]): r for r in rows}
dates = sorted({r["date"] for r in rows})
pairs = []
for date in dates:
    b, m = by_key.get(("baseline", date, "0")), by_key.get(("modified", date, "0"))
    if not (b and m):
        continue
    pairs.append({
        "date": date,
        "baseline_signal": b["signal"],
        "modified_signal": m["signal"],
        "changed": b["signal"] != m["signal"],
        "baseline_tokens": int(num(b, "total_tokens")),
        "modified_tokens": int(num(m, "total_tokens")),
        "baseline_calls": int(num(b, "llm_calls")),
        "modified_calls": int(num(m, "llm_calls")),
        "baseline_elapsed_s": num(b, "elapsed_s"),
        "modified_elapsed_s": num(m, "elapsed_s"),
    })

summary = {
    "baseline": summarize("baseline"),
    "modified": summarize("modified"),
    "pairs": pairs,
    "n_paired": len(pairs),
    "n_decision_changed": sum(p["changed"] for p in pairs),
    "total_api_tokens": int(sum(num(r, "total_tokens") for r in ok)),
    "total_wall_seconds": round(sum(num(r, "elapsed_s") for r in ok), 1),
    "config": json.loads((SRC / "config_record.json").read_text(encoding="utf-8")),
}
(SRC / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

lines = [
    "# Follow-up experiment: live DeepSeek model",
    "",
    "Only the model changed; the upstream commit, pinned synthetic data, ticker/date grid,",
    "metric definitions and `configs/*.json` arms are identical to the offline study.",
    "",
    "| Metric | Baseline (rounds=1) | Modified (rounds=3) | Delta |",
    "|---|---:|---:|---:|",
]
for label, key, fmt in (
    ("Successful runs", "n_success", "{:.0f}"),
    ("Legal rating", "rating_legal", "{:.0f}"),
    ("LLM calls / run", "mean_llm_calls", "{:.1f}"),
    ("Input tokens / run", "mean_input_tokens", "{:,.0f}"),
    ("Output tokens / run", "mean_output_tokens", "{:,.0f}"),
    ("Total tokens / run", "mean_total_tokens", "{:,.0f}"),
    ("Prompt characters / run", "mean_prompt_chars", "{:,.0f}"),
    ("Wall-clock s / run", "mean_elapsed_s", "{:.1f}"),
):
    b, m = summary["baseline"][key], summary["modified"][key]
    lines.append(f"| {label} | {fmt.format(b)} | {fmt.format(m)} | {m - b:+,.1f} |")

lines += [
    "",
    "## Paired decisions (same date, same data, only `max_debate_rounds` differs)",
    "",
    "| Date | Baseline decision | Modified decision | Changed | Baseline tokens | Modified tokens |",
    "|---|---|---|---|---:|---:|",
]
for p in pairs:
    lines.append(
        f"| {p['date']} | {p['baseline_signal']} | {p['modified_signal']} | "
        f"{'**yes**' if p['changed'] else 'no'} | {p['baseline_tokens']:,} | {p['modified_tokens']:,} |"
    )
lines += [
    "",
    f"Decisions changed in **{summary['n_decision_changed']}/{summary['n_paired']}** paired cells.",
    f"Total billed tokens across all runs: **{summary['total_api_tokens']:,}**;",
    f"total wall-clock: **{summary['total_wall_seconds'] / 60:.1f} min**.",
    "",
    "Caveat: one trial per cell, one ticker and three dates. At temperature 0 the",
    "provider still does not guarantee byte-identical output, so a null result is",
    "evidence of decision stability on this grid, not proof that debate depth",
    "never matters. Had a decision changed, it could not be attributed to debate",
    "depth alone without repeated trials.",
    "",
]
(SRC / "comparison.md").write_text("\n".join(lines), encoding="utf-8")

if pairs:
    labels = [p["date"][5:] for p in pairs]
    x = range(len(labels))
    w = 0.36
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.1))
    for ax, key, title, ylabel in (
        (axes[0], "tokens", "Token consumption per run", "tokens"),
        (axes[1], "calls", "LLM calls per run", "calls"),
    ):
        bvals = [p[f"baseline_{key}"] for p in pairs]
        mvals = [p[f"modified_{key}"] for p in pairs]
        ax.bar([i - w / 2 for i in x], bvals, w, label="baseline (1 round)", color="#4C72B0")
        ax.bar([i + w / 2 for i in x], mvals, w, label="modified (3 rounds)", color="#C44E52")
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_title(title, fontsize=9)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(axis="y", alpha=0.3)
        ax.legend(fontsize=7, frameon=False)
    fig.suptitle("Figure 4. Live-model cost of extra debate rounds", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIG / "fig4_real_llm.png", dpi=170)
    plt.close(fig)

print(f"cells={len(rows)} success={len(ok)} paired={len(pairs)} "
      f"decisions_changed={summary['n_decision_changed']} "
      f"tokens={summary['total_api_tokens']:,}")
print((SRC / "comparison.md").read_text(encoding="utf-8"))
