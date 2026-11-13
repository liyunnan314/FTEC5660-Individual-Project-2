# FTEC5660 Reproducibility Work — TradingAgents

Course: Agentic AI for Business and FinTech (FTEC5660) · Due: 13 November 2026
Target: [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) @ `9fa1196` (v0.7.1), Tier A, No. 22 in the instructor's list
Paper: Xiao et al., [arXiv:2412.20138v7](https://arxiv.org/abs/2412.20138)

> I reproduced the structural claim of TradingAgents — that the complete
> LangGraph multi-agent pipeline runs end to end and reaches a logged decision —
> using the authors' own offline test seam, a deterministic scripted LLM and a
> pinned synthetic dataset. Then I changed one config key
> (`max_debate_rounds` 1 → 3) and measured its impact. A second experiment
> repeated the same grid with a live DeepSeek model (report §5.4).
> The paper's trading-return table is reported as not reproducible,
> with the reasons documented.

---

## TL;DR results

| Check | Result |
|---|---|
| Upstream end-to-end test suite | 15/15 passing |
| Instrumented pipeline runs | 30/30 successful, 30/30 legal final ratings |
| Data/tool methods reached per run | 12/12 |
| Report fields non-empty per run | 7/7 |
| Modification | `max_debate_rounds` 1 → 3 (single isolated change) |
| LLM calls per run | 15 → 19 (+26.7%) |
| Prompt characters per run | 48,492 → 61,286 (+26.4%) |
| Bull/Bear debate turns | 1 → 3 (+200%) |
| Decision distribution | unchanged |
| Live DeepSeek follow-up (§5.4) | 6/6 legal decisions, 0/3 decisions changed, +70% tokens (166k → 283k); see `results/real_llm/comparison.md` |
| Paper's CR / Sharpe / MDD table | not reproducible (see below) |

Full write-up: [`report/reproducibility_report.pdf`](report/reproducibility_report.pdf) (8 pages, A4).

---

## Submission package

The assignment requires three items. The report is here; the GitHub link and the
recording need to be produced by the student.

| # | Required item | Status here |
|---|---|---|
| 1 | Brief report (max 10 pages) | ✅ `report/reproducibility_report.pdf` (8 pp) + editable `report/reproducibility_report.html` |
| 2 | GitHub link: clear README, changes in commits, no secrets | ✅ This repo, with staged, reviewable commits (see `git log`) and `.gitignore`. You still need to push it — see [Publishing](#publishing-to-github). |
| 3 | Recorded Zoom presentation (max 15 min) | ✅ Script + slides prepared in `presentation/`. You still need to record the video — see [Presentation](#presentation-13-minutes). |

---

## Quickstart

Requirements: Python 3.11+, git, internet for the one-time clone. The primary study
needs no API key, no GPU and no paid service. The optional §5.4 follow-up needs a
DeepSeek key (read from the environment, never stored).

```bash
git clone <your-fork-url> ftec5660-reproducibility
cd ftec5660-reproducibility

bash setup.sh                     # clone+pin upstream, create .venv, install deps

.venv/bin/python src/make_dataset.py                       # pinned synthetic OHLCV
.venv/bin/python src/smoke.py                             # one offline end-to-end run
.venv/bin/python src/run_experiment.py --arm both --trials 5
.venv/bin/python src/sweep_rounds.py                      # dose-response diagnostic
.venv/bin/python src/analyze.py                           # tables + figures
.venv/bin/python report/build_report.py                   # HTML + PDF report
```

Or run the whole chain at once: `bash run_all.sh`.

Optional live-model follow-up (report §5.4). Same grid, same data, only the LLM changes:

```bash
export DEEPSEEK_API_KEY=...            # never commit this
.venv/bin/python src/run_real_llm.py --arm both --trials 1
.venv/bin/python src/analyze_real_llm.py
.venv/bin/python report/build_report.py
```

Each live run takes ~5 minutes, so `run_all.sh` leaves this step out.

Expected output of `smoke.py` (abridged):

```json
{
  "signal": "Buy", "final_rating": "Buy",
  "llm_calls": 15, "tool_calls": 3,
  "missing_data_methods": [], "reports_nonempty": 7,
  "SMOKE_OK": true
}
```

Everything runs offline after `setup.sh`: the LLM client factory and all data
vendors are replaced at runtime. No upstream source file is edited.

---

## Repository layout

```
configs/          baseline.json / modified.json  <- the ONE modification lives here
data/             synthetic_prices.csv (pinned) + DATASET.md (seed & sha256)
src/
  make_dataset.py     deterministic OHLCV generator
  scripted_model.py   seeded, call-counting deterministic LLM stub
  offline_harness.py  runtime injection into the upstream pipeline
  smoke.py            one-shot sanity check
  run_experiment.py   5 paired trials x 3 cells x 2 arms = 30 runs
  sweep_rounds.py     dose-response of the same single change
  analyze.py          CSV tables + 3 PNG figures + report_numbers.json
  real_llm_harness.py  LangChain callback: calls, tokens, latency, errors
  run_real_llm.py      live-model paired grid (needs DEEPSEEK_API_KEY)
  analyze_real_llm.py  §5.4 tables, summary.json and Figure 4
results/
  raw/                per-cell metrics.json (all 30 runs + sweep)
  tables/             cells.csv, trials.csv, summary.csv, comparison.md,
                      experiment_audit.json, upstream_test_output.txt, logs
  figures/            fig1..fig4 PNG
  real_llm/           cells.csv, summary.json, comparison.md, config_record.json,
                      raw_responses.json (archived for re-scoring)
report/             build_report.py, reproducibility_report.{html,pdf}
presentation/       slides.html, slides.pdf, speaker_script.md
docs/               REAL_LLM_UPGRADE.md, DEBUG_DIARY.md
vendor/             upstream clone (gitignored, pinned to 9fa1196)
```

---

## What was reproduced, and what was not

Reproduced. The upstream repository claims (in the docstring of
`tests/test_graph_end_to_end.py`) that "the whole graph, end to end … every
tool-using analyst calls each of its tools once … the debates and managers run,
and the decision is parsed and logged". That claim, its 15 upstream assertions,
the 12 tool/data methods, the 7 report fields and the legal-decision behaviour
all reproduce under a deterministic stub LLM and pinned data.

Not reproduced. The paper's Table 1 (AAPL CR 26.62% / SR 8.21 / MDD 0.91%,
etc.). Three independent causes:

1. Model drift — the paper uses `gpt-4o` / `o1-preview`; this work uses a
   deterministic stub and, in §5.4, `deepseek-flash`, neither of which is the paper's
   model. *Results are not directly comparable to the paper because the underlying LLM differs.*
2. Code drift — `tradingagents/backtest.py` in v0.7.1 says
   *"It is not a portfolio simulator … none of which the system has"*. The
   simulated broker with a cash ledger that produced Table 1 no longer ships;
   `summarize()` now scores direction hit-rate and mean alpha instead. The
   headline table therefore cannot be emitted by the released code at all.
3. Data drift — the 2024 multimodal snapshot is unavailable; current feeds
   are live and time-varying. Pinning synthetic data removes this source of variation, but any return-like
   number from it says nothing about trading performance.

The README's own *Reproducibility* section agrees: "Backtest results are not
guaranteed to match any published figure … Treat the framework as a research
scaffold … not as a strategy with a fixed, replicable return."

---

## The modification

Exactly one upstream config key changes. `src/run_experiment.py` loads both arms
from `configs/*.json`, so the change is a two-line, reviewable diff:

```diff
# configs/baseline.json -> configs/modified.json
-  "max_debate_rounds": 1
+  "max_debate_rounds": 3
```

Everything else is identical between arms: upstream commit, dataset hash,
scripted model class, seeds 0–4, ticker (NVDA), dates, prompts, tool schemas,
measurement code. `results/tables/experiment_audit.json` records this
machine-readably. The modification is in its own git commit.

---

## Reproducibility ledger

| Item | Pinned value |
|---|---|
| Upstream commit | `9fa1196fffbcfd9de5146d2dd2869df84ab99838` (2026-11-04) |
| Upstream version | 0.7.1 |
| Python | 3.11.1 (isolated venv) |
| Dataset | `data/synthetic_prices.csv`, seed `20261113`, sha256 in `data/DATASET.md` |
| Model (primary) | `seed-scripted-stub-v1` (in-process, deterministic), temperature/top-p/max-tokens n/a |
| Model (§5.4) | `deepseek-flash` on both tiers, provider `deepseek`, base URL `https://api.deepseek.com/v1`, temperature 0.0, max_tokens 2048 |
| Prompts / templates | unchanged from upstream |
| Seeds | 0, 1, 2, 3, 4 (paired across arms) |
| Grid | NVDA × {2025-12-15, 2025-12-22, 2026-01-05} |
| Trials | 5 per arm; 15 cells per arm; 30 runs total |
| API keys | none in the primary study; `DEEPSEEK_API_KEY` used at run time only for §5.4, value never recorded |

To verify the dataset has not changed: `sha256sum data/synthetic_prices.csv`
against `data/DATASET.md`.

---

## No secrets

`.env.example` contains only the literal `placeholder-not-a-real-key`. The
offline harness replaces the LLM client before any credential is used, and
`.env`, `.venv/`, `vendor/` and `results/real_llm/work/` are gitignored. The live key is
read from the environment at run time and never written to disk; `config_record.json`
records only the word "present". There is no `sk-…` string, token, or personal
credential anywhere in the tracked files. Verify with:

```bash
git grep -nE 'sk-[A-Za-z0-9]{20,}|api[_-]?key\s*[:=]\s*["'"'"'][A-Za-z0-9]{20,}' || echo "clean"
```

---

## Publishing to GitHub

This repository is already on branch `main` with `origin` pointing at
`https://github.com/liyunnan314/ftec5660-reproducibility.git`, with clean,
incremental commits (`git log --oneline`). Publish it with one command:

```bash
git push -u origin main
```

That needs credentials for the `liyunnan314` account (a repo-scoped Personal
Access Token works); no token is stored in this repository. If you are
re-creating the repo from scratch, first run `git remote add origin
https://github.com/liyunnan314/ftec5660-reproducibility.git` and
`git branch -M main`. Then paste the public URL into the submission. Do not
commit `.env`, `.venv/` or `vendor/`. The upstream code is pinned by commit hash
in `setup.sh`, so the repo stays small and reviewable.

---

## Presentation (13 minutes)

- `presentation/slides.html` — 12 slides, self-contained, open in a browser
  (also exported to `presentation/slides.pdf`).
- `presentation/speaker_script.md` — timed speaker notes covering exactly what
  the brief asks: what was attempted, the modification and its measured impact,
  what worked / didn't, and lessons + recommendations.

Record your screen + voice in Zoom while presenting the slides, then submit the
recording link.

---

## Upgrading to a real LLM

Report §5.4 repeats the grid with a live `deepseek-flash` model: 6 paired runs with real token and latency measurements,
archived raw responses, and a paired-decision comparison. See
[`docs/REAL_LLM_UPGRADE.md`](docs/REAL_LLM_UPGRADE.md) for the exact config-only
switch, the decoding parameters that were logged, and which paper results remain
out of reach even with a key.

---

## Citation

```bibtex
@article{xiao2025tradingagents,
  title   = {TradingAgents: Multi-Agents LLM Financial Trading Framework},
  author  = {Xiao, Yijia and Sun, Edward and Luo, Di and Wang, Wei},
  journal = {arXiv preprint arXiv:2412.20138},
  year    = {2025}
}
```

This repository is coursework support material. The upstream project is
licensed under its own [LICENSE](https://github.com/TauricResearch/TradingAgents/blob/main/LICENSE).
