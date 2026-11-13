# Debug diary (full version)

Condensed into §6 of `report/reproducibility_report.pdf`. This file keeps the
evidence and commands for anyone re-running the study.

| # | Blocker / symptom | Root cause | Fix | Evidence |
|---|---|---|---|---|
| 1 | `error: externally-managed-environment` on `pip install -e .` | Debian/Ubuntu PEP 668 protection | Added `--break-system-packages` as a probe | first install log |
| 2 | `ERROR: Cannot uninstall typing_extensions 4.10.0, RECORD file not found. Hint: The package was installed by debian.` | apt-installed package cannot be upgraded by pip in the system interpreter | Abandoned the system interpreter; created a clean `.venv` | `setup.sh` |
| 3 | `Obtaining file:///workspace … neither 'setup.py' nor 'pyproject.toml' found` | Background shell's cwd was `/workspace`, not the cloned repo | Used the absolute path to the editable install | `setup.sh` |
| 4 | A piped `… \| tail -40` returned exit code 0 even though the install failed | Pipeline exit code is `tail`'s | `set -o pipefail` / explicit import check after install | `setup.sh` step 3 |
| 5 | `ModuleNotFoundError: No module named 'langchain_core'` when running the upstream tests | Dependency install had aborted at #2 | Reinstalled inside `.venv` | `upstream_test_output.txt`: 15 passed |
| 6 | No `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / any provider key in the sandbox | Environment has no credentials | Treated the LLM as a controlled variable; injected `SeedScriptedModel` through `trading_graph.create_tier_client` — the seam used by the authors' own `tests/test_graph_end_to_end.py` | `src/scripted_model.py`, `src/offline_harness.py` |
| 7 | Live yfinance / SEC EDGAR / Reddit / StockTwits / FRED calls would hang | No network access for data vendors, and the upstream test suite blocks sockets | Replaced `router.VENDOR_METHODS`, `snapshot.load_ohlcv`, `settlement.get_closes`, `yahoo_market.yf.Ticker`, StockTwits/Reddit fetchers; pinned a synthetic OHLCV CSV | `offline_harness.py`, `DATASET.md` |
| 8 | `Research Manager: provider does not support with_structured_output (); falling back to free-text generation` (4 lines/run) | The scripted stub raises `NotImplementedError` for structured output; the upstream has a documented free-text fallback | Confirmed it is a fallback, not a failure; disabled warning logging **in my harness only**. Also ran the structured path and confirmed identical call counts (15) | `smoke.py`, `run_experiment.py` |
| 9 | `iter_grid` clamps to today; settlement needs 5 trading days after each decision | Upstream point-in-time integrity rules | Chose 3 past dates inside the pinned dataset that leave a full holding window; each cell gets its own work dir | `run_experiment.py` `DATES` |
| 10 | First metric counted tool-call *turns* (3), not individual tool calls; paper reports "20+ tool calls" | Counting-convention mismatch | Added `tool_invocations` to the stub and re-ran all 30 cells → 12 invocations/run, reported as a lower bound | `cells.csv` |
| 11 | An earlier modification candidate (disabling memory) risked showing no effect with an empty memory log | Weak measurability | Ran a 1–5 round dose-response first; the clean `13 + 2R` relationship is why `max_debate_rounds` was chosen | `rounds_sweep.csv` |
| 12 | Several repository links in the assignment's paper list returned 404 | Placeholder / moved repos | Verified all 29 links via the GitHub API on 2026-11-13 and selected Tier A, actively maintained TradingAgents | report §1 |

## Order of verification

```bash
bash setup.sh                                   # fixes #1-#5
.venv/bin/python src/make_dataset.py             # fixes #7's data side
.venv/bin/python src/smoke.py                    # proves #6-#9 are solved end to end
.venv/bin/python -m pytest vendor/TradingAgents/tests/test_graph_end_to_end.py -q
.venv/bin/python src/run_experiment.py --arm both --trials 5
.venv/bin/python src/sweep_rounds.py && .venv/bin/python src/analyze.py
.venv/bin/python report/build_report.py
```

Logs are kept in `results/tables/experiment_log.txt`, `sweep_log.txt`,
`analyze_log.txt` and `upstream_test_output.txt`.
