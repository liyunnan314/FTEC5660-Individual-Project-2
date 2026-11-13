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
| 6 | No `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / any provider key in the sandbox **at the time of the primary study** | Environment had no credentials then | Treated the LLM as a controlled variable; injected `SeedScriptedModel` through `trading_graph.create_tier_client` — the seam used by the authors' own `tests/test_graph_end_to_end.py` | `src/scripted_model.py`, `src/offline_harness.py` |
| 7 | Live yfinance / SEC EDGAR / Reddit / StockTwits / FRED calls would hang | No network access for data vendors, and the upstream test suite blocks sockets | Replaced `router.VENDOR_METHODS`, `snapshot.load_ohlcv`, `settlement.get_closes`, `yahoo_market.yf.Ticker`, StockTwits/Reddit fetchers; pinned a synthetic OHLCV CSV | `offline_harness.py`, `DATASET.md` |
| 8 | `Research Manager: provider does not support with_structured_output (); falling back to free-text generation` (4 lines/run) | The scripted stub raises `NotImplementedError` for structured output; the upstream has a documented free-text fallback | Confirmed it is a fallback, not a failure; disabled warning logging **in my harness only**. Also ran the structured path and confirmed identical call counts (15) | `smoke.py`, `run_experiment.py` |
| 9 | `iter_grid` clamps to today; settlement needs 5 trading days after each decision | Upstream point-in-time integrity rules | Chose 3 past dates inside the pinned dataset that leave a full holding window; each cell gets its own work dir | `run_experiment.py` `DATES` |
| 10 | First metric counted tool-call *turns* (3), not individual tool calls; paper reports "20+ tool calls" | Counting-convention mismatch | Added `tool_invocations` to the stub and re-ran all 30 cells → 12 invocations/run, reported as a lower bound | `cells.csv` |
| 11 | An earlier modification candidate (disabling memory) risked showing no effect with an empty memory log | Weak measurability | Ran a 1–5 round dose-response first; the clean `13 + 2R` relationship is why `max_debate_rounds` was chosen | `rounds_sweep.csv` |
| 12 | Several repository links in the assignment's paper list returned 404 | Placeholder / moved repos | Verified all 29 links via the GitHub API on 2026-11-13 and selected Tier A, actively maintained TradingAgents | report §1 |
| 13 | A live-model probe of `deepseek-chat` returned `"model": "deepseek-flash"` | The alias is deprecated upstream (catalog comment dated 2026-07-24) and now maps to V4 Flash, a *thinking* model that rejects `tool_choice` | Used the official `deepseek-flash` ID so the upstream capability registry suppresses `tool_choice`; recorded the model drift in `config_record.json` | `docs/REAL_LLM_UPGRADE.md`, `results/real_llm/config_record.json` |
| 14 | One live pipeline run took ~5 min and ~170k billed tokens | Thinking model + accumulated context + extra self-directed tool rounds | Bounded `max_tokens=2048`, kept one trial per cell (6 runs instead of 30), and left `run_all.sh` offline by default | `results/real_llm/run_log.txt`, `summary.json` |
| 15 | Token counts missing from some callback responses | Providers fill `llm_output.token_usage` or `AIMessage.usage_metadata` inconsistently | `UsageHandler._usage_from_response` checks both, and records call count, latency and errors through LangChain's public `callbacks` hook | `src/real_llm_harness.py` |
| 16 | The stub's exact `calls = 13 + 2R` law did not hold with a real model (~21 calls at R=1) | A real LLM autonomously requests extra tool rounds; the law was a property of the scripted model, not of the graph alone | Reported it as a negative transfer in report §5.4 instead of silently forcing `max_tool_rounds` | `results/real_llm/cells.csv` |

## Order of verification

```bash
bash setup.sh                                   # fixes #1-#5
.venv/bin/python src/make_dataset.py             # fixes #7's data side
.venv/bin/python src/smoke.py                    # proves #6-#9 are solved end to end
.venv/bin/python -m pytest vendor/TradingAgents/tests/test_graph_end_to_end.py -q
.venv/bin/python src/run_experiment.py --arm both --trials 5
.venv/bin/python src/sweep_rounds.py && .venv/bin/python src/analyze.py
.venv/bin/python report/build_report.py

# optional: live-model follow-up (needs DEEPSEEK_API_KEY, ~30 min)
DEEPSEEK_API_KEY=... .venv/bin/python src/run_real_llm.py --arm both --trials 1
.venv/bin/python src/analyze_real_llm.py
.venv/bin/python report/build_report.py     # adds section 5.4 / Figure 4
```

Logs are kept in `results/tables/` and `results/real_llm/run_log.txt`. in `results/tables/experiment_log.txt`, `sweep_log.txt`,
`analyze_log.txt` and `upstream_test_output.txt`.
