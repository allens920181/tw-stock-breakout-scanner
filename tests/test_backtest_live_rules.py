"""回測的實盤規則：空頭不進場、品質過濾、跳空停損以開盤價成交。"""
import numpy as np
import pandas as pd

from twscanner.research.backtest import backtest_symbol
from twscanner.services.research import live_rules_from_cfg

WEIGHTS = {"breakout_with_volume": 2, "ma_bullish": 2, "kd": 1, "macd": 1}


def _uptrend(n=260, gap_at=None):
    idx = pd.bdate_range("2025-01-01", periods=n)
    close = 50 + np.arange(n) * 0.4 + np.sin(np.arange(n) / 3) * 1.5
    df = pd.DataFrame({"Open": close - 0.2, "High": close + 1.0, "Low": close - 1.0,
                       "Close": close, "Volume": np.full(n, 2_000_000.0)}, index=idx)
    df.loc[df.index[::7], "Volume"] = 5_000_000.0      # 週期性放量，製造突破訊號
    return df


def _rules(**kw):
    base = {"blocked_regimes": {"bear"}, "min_price": 10, "min_avg_volume": 500_000,
            "require_ma60": True, "min_risk_pct": 0.0, "gap_fill": True}
    base.update(kw)
    return base


def test_bear_regime_blocks_all_entries():
    df = _uptrend()
    bull = pd.Series("bull", index=df.index)
    bear = pd.Series("bear", index=df.index)
    assert len(backtest_symbol(df, WEIGHTS, 4, lookback=120, regime_map=bull, live_rules=_rules())) > 0
    assert backtest_symbol(df, WEIGHTS, 4, lookback=120, regime_map=bear, live_rules=_rules()) == []


def test_quality_filters():
    df = _uptrend()
    bull = pd.Series("bull", index=df.index)
    assert backtest_symbol(df, WEIGHTS, 4, lookback=120, regime_map=bull,
                           live_rules=_rules(min_avg_volume=10_000_000)) == []
    assert backtest_symbol(df, WEIGHTS, 4, lookback=120, regime_map=bull,
                           live_rules=_rules(min_price=1_000)) == []


def test_gap_down_stop_fills_at_open():
    df = _uptrend()
    bull = pd.Series("bull", index=df.index)
    first = backtest_symbol(df, WEIGHTS, 4, lookback=120, regime_map=bull, live_rules=_rules())[0]
    i = df.index.get_loc(pd.Timestamp(first["entry_date"]))
    crash = df.copy()
    crash.iloc[i + 1, crash.columns.get_loc("Open")] = 1.0      # 隔天開盤崩到 1 元
    crash.iloc[i + 1, crash.columns.get_loc("Low")] = 1.0
    old = backtest_symbol(crash, WEIGHTS, 4, lookback=120, regime_map=bull)[0]
    new = backtest_symbol(crash, WEIGHTS, 4, lookback=120, regime_map=bull, live_rules=_rules())[0]
    assert old["exit_reason"] == new["exit_reason"] == "停損"
    assert new["exit_price"] == 1.0 and old["exit_price"] > 1.0     # 舊版假設以停損價成交（過度樂觀）


def test_rules_from_cfg():
    cfg = {"filters": {"min_price": 10, "min_avg_volume": 500_000, "require_above_ma60": True,
                       "min_risk_pct": 0.02}, "backtest": {"live_rules": True}}
    r = live_rules_from_cfg(cfg)
    assert r["blocked_regimes"] == {"bear"} and r["min_risk_pct"] == 0.02
    assert live_rules_from_cfg({"backtest": {"live_rules": False}}) is None
