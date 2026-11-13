# Repeating the study with a real LLM (Edge Case A)

The assignment's Edge Case A allows replacing a hard-coded or unavailable LLM
with DeepSeek or another accessible model, **as long as the change is documented
and treated as a controlled variable**. This repository runs fully offline by
default and needs no credential. A live-model follow-up has since been run and
is reported as **§5.4 of `report/reproducibility_report.pdf`**; this file records
exactly how, so it can be repeated.

## 0. Status: executed, not hypothetical

| | |
|---|---|
| What ran | 6 paired pipeline runs (3 dates × 2 arms), one trial per cell |
| Key | `DEEPSEEK_API_KEY`, read from the environment, **never written to any file** |
| Command | `DEEPSEEK_API_KEY=... .venv/bin/python src/run_real_llm.py --arm both --trials 1` then `.venv/bin/python src/analyze_real_llm.py` |
| Results | `results/real_llm/{cells.csv,cells.json,summary.json,comparison.md,config_record.json,raw_responses.json}` and `results/figures/fig4_real_llm.png` (called Figure 4 in the report) |
| Cost | ~5 min wall-clock and ~170k billed tokens per run (see `summary.json` for totals) |

`run_all.sh` deliberately omits this step: it is slow and costs money, while the
30-run primary experiment completes in under a minute, offline.

## 1. The exact switch that was used

The upstream v0.7.1 registry has a **native `deepseek` provider**, so no generic
`openai_compatible` wiring is needed. `src/run_real_llm.py` sets these config keys
(no upstream source edits, no prompt changes):

```python
REAL_LLM_CONFIG = {
    "llm_provider": "deepseek",
    "quick_think_llm": "deepseek-flash",
    "deep_think_llm": "deepseek-flash",
    "backend_url": "https://api.deepseek.com/v1",
    "temperature": 0.0,
    "max_tokens": 2048,
}
```

The key comes from `DEEPSEEK_API_KEY` (see
`tradingagents/llm_clients/api_key_env.py`). Both tiers use the same model so
"deep thinking" is not a second confound. `src/offline_harness.py::install(...,
patch_llm=False)` keeps all data-vendor injections but leaves the upstream
`create_tier_client` intact; `TradingAgentsGraph(callbacks=[UsageHandler()])`
measures calls, tokens, latency and errors through LangChain's public API.

The equivalent environment-variable form (useful for the upstream CLI) is:

```bash
export DEEPSEEK_API_KEY=...                # never commit this
export TRADINGAGENTS_LLM_PROVIDER=deepseek
export TRADINGAGENTS_LLM_BACKEND_URL=https://api.deepseek.com/v1
export TRADINGAGENTS_QUICK_THINK_LLM=deepseek-flash
export TRADINGAGENTS_DEEP_THINK_LLM=deepseek-flash
export TRADINGAGENTS_TEMPERATURE=0.0
export TRADINGAGENTS_MAX_TOKENS=2048
```

`_ENV_OVERRIDES` in the upstream `tradingagents/default_config.py` is the
authoritative list of `TRADINGAGENTS_*` variables.

### Model-drift note (important)

The older `deepseek-chat` alias is deprecated upstream (catalog comment dated
2026-07-24) and now maps to **V4 Flash**; a probe request returns
`"model": "deepseek-flash"` in the response. `deepseek-flash` is a *thinking*
model that rejects `tool_choice`, and upstream's capability registry only
suppresses that parameter when the official ID is used. Requesting
`deepseek-chat` therefore risks a 400 on tool calls. Always use the official ID
and record it.

## 2. Controlled-variable ledger

`results/real_llm/config_record.json` is generated on every run and contains:

| Field | Value |
|---|---|
| Model (quick / deep) | `deepseek-flash` / `deepseek-flash` |
| Provider | `deepseek` |
| Base URL | `https://api.deepseek.com/v1` |
| API key | the literal string `"present (value never recorded)"` |
| Decoding | `temperature=0.0`, `max_tokens=2048`, reasoning effort = provider default |
| Prompt / template changes | `none` |
| Upstream commit | `9fa1196` (unchanged from the primary experiment) |
| Dataset | `data/synthetic_prices.csv`, SHA-256 in the record |
| Grid / arms | unchanged from `src/run_experiment.py` and `configs/*.json` |

State plainly in any derived write-up:

> Results are not directly comparable to the paper because the underlying LLM
> differs (the paper uses `gpt-4o` / `o1-preview`).

## 3. What changes, and what still does not

| Result | With a real LLM — observed |
|---|---|
| Structural claim (graph runs end to end, 12 tools, 7 reports) | Reproduced with substantive, data-grounded analyst text instead of a canned string. |
| LLM calls / cost law | **Does not transfer exactly.** The stub's `calls = 13 + 2 × rounds` becomes ~19 calls at 1 round and ~23 at 3 rounds, because a real model autonomously requests extra tool rounds. Token cost is a property of the model as well as the graph. |
| Decision distribution | Varies across dates (`Underweight` / `Hold`) but is **identical between arms on all three paired dates (0/3 changed)**, despite a ~70% token increase. Evidence of stability on this grid, not proof that debate depth never matters. |
| Paper's Table 1 (CR / ARR / SR / MDD) | **Still not reproducible.** v0.7.1's backtester is a decision scorer, not a portfolio simulator (report §4.3), and the 2024 multimodal data vintage is gone. More API credits do not change this. |

## 4. Keeping the comparison fair

The follow-up uses the **same tasks, metrics and measurement code** as the
primary study: same upstream commit, same pinned dataset hash, same
ticker/date grid, same `configs/*.json` arms, same `REPORT_FIELDS` and
`EXPECTED_TOOL_METHODS`. Only the LLM client differs. Raw model responses are
archived in `results/real_llm/raw_responses.json` so a costly run can be
re-scored without re-calling the API — the upstream README warns that even at a
fixed temperature, providers do not guarantee byte-identical output.

If you scale this up, raise `--trials` and record the per-cell variance; with
one trial per cell the report deliberately refrains from attributing a single
decision change to the modification.

## 5. Credential hygiene

Never put the key in `.env` inside the repository, in a command that is
committed, or in a results file. `.env`, `.venv/`, `vendor/` and
`results/real_llm/work/` are gitignored. Verify before every push:

```bash
git grep -nE 'sk-[A-Za-z0-9]{20,}' || echo "clean"
```
