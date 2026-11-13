# Measured results

All values are mean +/- population SD over 5 paired trials (3 cells per trial, 15 cells per arm). Both arms use identical seeds, grid, dataset, prompts and upstream commit.

## Table 1. Baseline vs modification

| Metric | Baseline (rounds=1) | Modified (rounds=3) | Delta |
|---|---:|---:|---:|
| Success rate | 1.00 +/- 0.00 | 1.00 +/- 0.00 | +0.00 (+0.0%) |
| Legal-rating rate | 1.00 +/- 0.00 | 1.00 +/- 0.00 | +0.00 (+0.0%) |
| LLM calls / run | 15.00 +/- 0.00 | 19.00 +/- 0.00 | +4.00 (+26.7%) |
| Tool-call turns / run | 3.00 +/- 0.00 | 3.00 +/- 0.00 | +0.00 (+0.0%) |
| Tool invocations / run | 12.00 +/- 0.00 | 12.00 +/- 0.00 | +0.00 (+0.0%) |
| Prompt chars / run | 48492 +/- 136 | 61286 +/- 266 | +12794.00 (+26.4%) |
| Data methods reached / run | 12.00 +/- 0.00 | 12.00 +/- 0.00 | +0.00 (+0.0%) |
| Non-empty reports / run | 7.00 +/- 0.00 | 7.00 +/- 0.00 | +0.00 (+0.0%) |
| Bull invocations / run | 1.00 +/- 0.00 | 3.00 +/- 0.00 | +2.00 (+200.0%) |
| Latency / run (s) | 0.0417 +/- 0.0103 | 0.0366 +/- 0.0010 | -0.0051 (-12.3%) |

Paired differences (modified - baseline) are identical for every seed. The count metrics (LLM calls, tool turns, data methods, reports, Bull invocations) have zero SD: the scripted model is deterministic. Prompt characters vary slightly with the analysis date because the upstream date-window text changes length. Wall-clock latency is the only metric with genuine run-to-run noise, caused by OS scheduling rather than by the pipeline.

## Table 2. Dose-response of max_debate_rounds (one cell, seed 0)

| max_debate_rounds | LLM calls | Bull calls | Bear calls | Prompt chars | Final rating |
|---:|---:|---:|---:|---:|---|
| 1 | 15 | 1 | 1 | 48330 | Buy |
| 2 | 17 | 2 | 2 | 54367 | Buy |
| 3 | 19 | 3 | 3 | 60972 | Buy |
| 4 | 21 | 4 | 4 | 68145 | Buy |
| 5 | 23 | 5 | 5 | 75886 | Buy |

LLM calls follow `calls = 13 + 2 x rounds` exactly. Prompt characters grow super-linearly because each additional debate round re-sends the accumulated history.

## Table 3. Reproduction checklist

| Claim / check | Target | Measured | Verdict |
|---|---|---|---|
| Upstream end-to-end test suite | all pass | 15 passed | reproduced |
| Pipeline reaches a decision | 100% | 30/30 | reproduced |
| Final rating in legal enum | 100% | 30/30 | reproduced |
| 12 data/tool methods reached | 12/12 | 12/12 in every cell | reproduced |
| 7 report fields non-empty | 7/7 | 7/7 in every cell | reproduced |
| Published return / Sharpe / drawdown table | paper numbers | not measured | NOT reproducible (model / data / code drift; see report §4.3) |

## Table 4. Decision distribution (cells)

| Rating | Baseline | Modified |
|---|---:|---:|
| Buy | 3 | 3 |
| Overweight | 3 | 3 |
| Hold | 3 | 3 |
| Underweight | 3 | 3 |
| Sell | 3 | 3 |
