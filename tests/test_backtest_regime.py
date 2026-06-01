# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

from src.backtest import _regime_at, summarize_by_regime
from src.market import build_regime_map


def test_build_regime_map_synthetic(monkeypatch):
    n = 120
    # 造一段上漲（bull）→ 下跌（bear）的 TWII
    close = np.concatenate([np.linspace(100, 160, 60), np.linspace(160, 110, 60)])
    df = pd.DataFrame({
        "Open": close, "High": close + 1, "Low": close - 1,
        "Close": close, "Volume": np.full(n, 1e8),
    }, index=pd.date_range("2024-01-01", periods=n, freq="B"))
    monkeypatch.setattr("src.market.fetch_twii", lambda period, cache_dir: df)
    rm = build_regime_map("1y", ".cache")
    assert isinstance(rm, pd.Series)
    assert set(rm.unique()) <= {"bull", "neutral", "bear"}
    assert (rm == "bull").any() and (rm == "bear").any()


def test_regime_at_asof():
    rm = pd.Series(["bull", "bear"], index=pd.to_datetime(["2024-01-01", "2024-02-01"]))
    assert _regime_at(rm, "2024-01-15") == "bull"
    assert _regime_at(rm, "2024-03-01") == "bear"
    assert _regime_at(None, "2024-01-15") == "unknown"


def test_summarize_by_regime():
    trades = [
        {"regime": "bull", "return_pct": 5, "r_multiple": 1.0},
        {"regime": "bull", "return_pct": -2, "r_multiple": -1.0},
        {"regime": "bear", "return_pct": -3, "r_multiple": -1.0},
    ]
    df = summarize_by_regime(trades)
    assert df["總交易數"].sum() == 3
    assert set(df["regime"]) == {"bull", "bear"}
    assert summarize_by_regime([]).empty
