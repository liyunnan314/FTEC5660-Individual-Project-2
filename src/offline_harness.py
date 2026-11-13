"""Offline injection harness for the upstream TradingAgents pipeline.

The upstream repository's own end-to-end test
(``tests/test_graph_end_to_end.py::offline``) shows how to run the whole
LangGraph pipeline without network or API keys: replace the LLM client and
every data vendor. We reuse *exactly* that seam, with two additions that make
the run measurable and repeatable:

* a pinned, synthetic OHLCV dataset on disk (``data/synthetic_prices.csv``)
  instead of an inline DataFrame, so the data vintage is checkable;
* a call-counting scripted model (``SeedScriptedModel``).

No upstream source file is modified. All replacements are applied at runtime
through ``pytest.MonkeyPatch`` and undone after each trial.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd
from pytest import MonkeyPatch

from tradingagents.agents import context
from tradingagents.agents.analysts import sentiment_analyst
from tradingagents.dataflows import router
from tradingagents.dataflows.vendors.yahoo import market as yahoo_market
from tradingagents.dataflows.vendors.yahoo import snapshot
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph import trading_graph
from tradingagents.memory import settlement

from scripted_model import SeedScriptedModel, _StubClient

# The 12 tool methods the upstream end-to-end test asserts are all reached.
EXPECTED_TOOL_METHODS = {
    "get_stock_data", "get_indicators", "get_news", "get_global_news",
    "get_macro_indicators", "get_prediction_markets", "get_fundamentals",
    "get_balance_sheet", "get_cashflow", "get_income_statement",
    "get_insider_transactions", "ohlcv",
}

REPORT_FIELDS = (
    "market_report", "sentiment_report", "news_report", "fundamentals_report",
    "investment_plan", "trader_investment_plan", "final_trade_decision",
)


def load_dataset(path: str | Path) -> pd.DataFrame:
    """Load the pinned synthetic price table."""
    frame = pd.read_csv(path, parse_dates=["Date"])
    return frame


def price_frame_for(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """The OHLCV view the upstream market analyst expects."""
    sub = frame[frame["Ticker"] == ticker].copy()
    return sub[["Date", "Open", "High", "Low", "Close", "Volume"]].reset_index(drop=True)


def closes_for(frame: pd.DataFrame, ticker: str) -> pd.Series:
    """Settlement/backtest close series, indexed by date."""
    sub = frame[frame["Ticker"] == ticker]
    return pd.Series(sub["Close"].to_numpy(), index=pd.DatetimeIndex(sub["Date"]))


def install(mp: MonkeyPatch, model: SeedScriptedModel, dataset: pd.DataFrame,
            ticker: str) -> set[str]:
    """Apply all offline replacements; return the set of data methods reached."""
    called: set[str] = set()
    prices = price_frame_for(dataset, ticker)
    closes = closes_for(dataset, ticker)

    # 1. Every data vendor answers with a labelled synthetic payload.
    for method, vendors in router.VENDOR_METHODS.items():
        for vendor in list(vendors):
            mp.setitem(
                vendors, vendor,
                lambda *a, _m=method, **k: called.add(_m) or f"[{_m}: pinned synthetic data]",
            )

    # 2. Price history and company identity.
    mp.setattr(snapshot, "load_ohlcv", lambda *a, **k: called.add("ohlcv") or prices.copy())
    mp.setattr(sentiment_analyst, "fetch_stocktwits_messages", lambda *a, **k: "no posts")
    mp.setattr(sentiment_analyst, "fetch_reddit_posts", lambda *a, **k: "no posts")
    mp.setattr(yahoo_market.yf, "Ticker",
               lambda s: type("T", (), {"info": {"longName": f"{s} (synthetic)"}})())
    mp.setattr(settlement, "get_closes", lambda *a, **k: closes.copy())
    context._identity.cache_clear()

    # 3. The controlled variable: the LLM client factory.
    mp.setattr(trading_graph, "create_tier_client",
               lambda config, tier, **k: _StubClient(model))
    return called


def build_config(work_dir: Path, **overrides) -> dict:
    """A fresh upstream DEFAULT_CONFIG with all paths pointed at this trial."""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg.update(
        results_dir=str(work_dir / "results"),
        data_cache_dir=str(work_dir / "cache"),
        memory_log_path=str(work_dir / "memory" / "trading_memory.md"),
        checkpoint_enabled=False,
    )
    for key, value in overrides.items():
        if key not in cfg:
            raise KeyError(f"unknown upstream config key: {key}")
        cfg[key] = value
    for sub in ("results", "cache", "memory"):
        (work_dir / sub).mkdir(parents=True, exist_ok=True)
    return cfg
