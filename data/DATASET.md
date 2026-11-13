# Pinned synthetic OHLCV dataset

- generator: `src/make_dataset.py`, fixed seed `20261113`
- trading days: 120 business days ending 2026-01-09
- tickers: NVDA, AAPL, MSFT, SPY
- rows: 480
- sha256: `25658b718ee106182f08486d08e89b47378ee80322a7e53941280e4ae1c5d6d3`

Regenerate with `python src/make_dataset.py`. The upstream data vendors are replaced at runtime by `src/offline_harness.py`; no live market, news or social data is fetched during the experiments.

**This is synthetic data.** Any return/alpha computed from it measures only that the evaluation plumbing runs, not trading performance.
