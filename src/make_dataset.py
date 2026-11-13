"""Generate the pinned synthetic OHLCV dataset used by every experiment run."""

from __future__ import annotations

import hashlib
import math
import random
from pathlib import Path

import pandas as pd

SEED = 20261113
END_DATE = "2026-01-09"
N_DAYS = 120
TICKERS = {
    "NVDA": {"start": 118.0, "drift": 0.0018, "vol": 0.021, "volume": 42_000_000},
    "AAPL": {"start": 191.0, "drift": 0.0006, "vol": 0.013, "volume": 55_000_000},
    "MSFT": {"start": 372.0, "drift": 0.0009, "vol": 0.012, "volume": 21_000_000},
    "SPY":  {"start": 472.0, "drift": 0.0005, "vol": 0.008, "volume": 78_000_000},
}


def build() -> pd.DataFrame:
    dates = pd.bdate_range(end=END_DATE, periods=N_DAYS)
    rows = []
    for ticker, spec in TICKERS.items():
        rng = random.Random(SEED + sum(ord(c) for c in ticker))
        close = spec["start"]
        for day in dates:
            shock = rng.gauss(0.0, 1.0)
            open_ = close
            close = close * math.exp(spec["drift"] - 0.5 * spec["vol"] ** 2
                                    + spec["vol"] * shock)
            high = max(open_, close) * (1.0 + abs(rng.gauss(0, 0.004)))
            low = min(open_, close) * (1.0 - abs(rng.gauss(0, 0.004)))
            volume = int(spec["volume"] * (0.8 + 0.4 * rng.random()))
            rows.append({
                "Date": day.strftime("%Y-%m-%d"), "Ticker": ticker,
                "Open": round(open_, 4), "High": round(high, 4),
                "Low": round(low, 4), "Close": round(close, 4),
                "Volume": volume,
            })
    return pd.DataFrame(rows)


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = build()
    csv_path = out_dir / "synthetic_prices.csv"
    frame.to_csv(csv_path, index=False)
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    (out_dir / "DATASET.md").write_text(
        "# Pinned synthetic OHLCV dataset\n\n"
        f"- generator: `src/make_dataset.py`, fixed seed `{SEED}`\n"
        f"- trading days: {N_DAYS} business days ending {END_DATE}\n"
        f"- tickers: {', '.join(TICKERS)}\n"
        f"- rows: {len(frame)}\n"
        f"- sha256: `{digest}`\n\n"
        "Regenerate with `python src/make_dataset.py`. The upstream data vendors "
        "are replaced at runtime by `src/offline_harness.py`; no live market, "
        "news or social data is fetched during the experiments.\n\n"
        "**This is synthetic data.** Any return/alpha computed from it measures "
        "only that the evaluation plumbing runs, not trading performance.\n",
        encoding="utf-8",
    )
    print(f"wrote {csv_path} ({len(frame)} rows, sha256 {digest[:16]}...)")


if __name__ == "__main__":
    main(Path(__file__).resolve().parents[1] / "data")
