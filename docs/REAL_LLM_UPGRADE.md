# Repeating this study with a real LLM (Edge Case A)

The assignment's Edge Case A allows replacing a hard-coded or unavailable LLM
with DeepSeek or another accessible model, **as long as the change is documented
and treated as a controlled variable**. This repository runs fully offline by
default because no API key was available. If you have a key, the switch is
config-only — no source changes are needed, because TradingAgents v0.7.1
supports any OpenAI-compatible endpoint.

## 1. Configure the endpoint

DeepSeek's API is OpenAI-compatible. Set these environment variables (or put
them in `.env`, which is gitignored):

```bash
export DEEPSEEK_API_KEY="<your key>"          # never commit this
export TRADINGAGENTS_LLM_PROVIDER=openai_compatible
export TRADINGAGENTS_LLM_BACKEND_URL=https://api.deepseek.com/v1
export TRADINGAGENTS_QUICK_THINK_LLM=deepseek-chat
export TRADINGAGENTS_DEEP_THINK_LLM=deepseek-reasoner
export TRADINGAGENTS_TEMPERATURE=0.0
export TRADINGAGENTS_MAX_DEBATE_ROUNDS=1
```

`_ENV_OVERRIDES` in the upstream `tradingagents/default_config.py` is the
authoritative list of `TRADINGAGENTS_*` variables. Per-tier overrides also
exist (`TRADINGAGENTS_QUICK_THINK_PROVIDER`, `..._BACKEND_URL`, etc.).

## 2. Record the controlled variable

Fill this in before reporting any number:

| Field | Value to record |
|---|---|
| Model name(s) | quick tier / deep tier separately |
| Provider | e.g. DeepSeek, or `openai_compatible` |
| Base URL | the exact endpoint, including `/v1` |
| API key | **never** record the value; record only "present" |
| Decoding | `temperature`, `top_p`, `max_tokens` (`TRADINGAGENTS_MAX_TOKENS`), reasoning effort |
| Prompt / template changes | list any; ideally "none" |
| Commit + dataset hash | unchanged from `data/DATASET.md` and `setup.sh` |

Then state explicitly in the report:

> Results are not directly comparable to the paper because the underlying LLM
> differs.

## 3. What changes, and what still does not

| Result | With a real LLM |
|---|---|
| Structural claim (graph runs end to end, 12 tools, 7 reports) | Reproducible; now with real model outputs and real latency/token cost. Expect non-zero variance across the 5 trials. |
| LLM calls / prompt characters vs `max_debate_rounds` | Same linear law `calls = 13 + 2 × rounds`; token cost will be much larger and worth reporting in real tokens. |
| Decision distribution | May now change with debate depth — this is the interesting experiment the offline stub cannot answer. |
| Paper's Table 1 (CR / ARR / SR / MDD) | **Still not reproducible.** v0.7.1's backtester is a decision scorer, not a portfolio simulator (see report §4.3), and the 2024 multimodal data vintage is gone. |

## 4. Cost expectation

The paper reports **11 LLM calls and 20+ tool calls per prediction**; v0.7.1
measures **15 LLM calls** with the default `max_debate_rounds=1` and **19** with
3 rounds. Budget accordingly for 30 runs (plus retries) before starting a sweep,
and set `TRADINGAGENTS_MAX_TOKENS` to bound cost.

## 5. Keep the comparison fair

Use the **same tasks, same metrics and same measurement script** as this repo
(`src/run_experiment.py`), and keep the same paired seeds / grid. Only the model
changes. Archive raw responses so the run can be re-scored without re-calling
the API — the upstream README warns that even at a fixed temperature, providers
do not guarantee byte-identical output.
