# Follow-up experiment: live DeepSeek model

Only the model changed; the upstream commit, pinned synthetic data, ticker/date grid,
metric definitions and `configs/*.json` arms are identical to the offline study.

| Metric | Baseline (rounds=1) | Modified (rounds=3) | Delta |
|---|---:|---:|---:|
| Successful runs | 3 | 3 | +0.0 |
| Legal rating | 3 | 3 | +0.0 |
| LLM calls / run | 19.0 | 23.3 | +4.3 |
| Input tokens / run | 113,707 | 207,982 | +94,275.3 |
| Output tokens / run | 52,799 | 75,248 | +22,449.3 |
| Total tokens / run | 166,505 | 283,230 | +116,724.7 |
| Prompt characters / run | 392,465 | 770,494 | +378,028.7 |
| Wall-clock s / run | 291.1 | 435.8 | +144.7 |

## Paired decisions (same date, same data, only `max_debate_rounds` differs)

| Date | Baseline decision | Modified decision | Changed | Baseline tokens | Modified tokens |
|---|---|---|---|---:|---:|
| 2025-12-15 | Underweight | Underweight | no | 171,967 | 245,486 |
| 2025-12-22 | Hold | Hold | no | 156,645 | 321,780 |
| 2026-01-05 | Underweight | Underweight | no | 170,904 | 282,424 |

Decisions changed in **0/3** paired cells.
Total billed tokens across all runs: **1,349,206**;
total wall-clock: **36.3 min**.

Caveat: one trial per cell, one ticker and three dates. At temperature 0 the
provider still does not guarantee byte-identical output, so a null result is
evidence of decision stability on this grid, not proof that debate depth
never matters. Had a decision changed, it could not be attributed to debate
depth alone without repeated trials.
