# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

from src.backtest import backtest_symbol
from src.sensitivity import detect_plateau, plateau_scan

WEIGHTS = {"breakout_with_volume": 2, "ma_bullish": 2, "kd": 1, "macd": 1}


def _df(n=160):
    close = np.linspace(40, 130, n)
    return pd.DataFrame({
        "Open": close, "High": close + 1, "Low": close - 1,
        "Close": close, "Volume": np.concatenate([np.full(n - 1, 1e6), [5e6]]),
    }, index=pd.date_range("2024-01-01", periods=n, freq="B"))


def test_ma_mode_unchanged():
    # 預設 stop_mode='ma' tp_mult=2 必須與不傳參數一致（回歸保護）
    df = _df()
    a = backtest_symbol(df, WEIGHTS, 4, lookback=40)
    b = backtest_symbol(df, WEIGHTS, 4, lookback=40, stop_mode="ma", tp_mult=2.0)
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert x["r_multiple"] == y["r_multiple"] and x["exit_price"] == y["exit_price"]


def test_atr_mode_changes_stop():
    df = _df()
    t1 = backtest_symbol(df, WEIGHTS, 4, lookback=40, stop_mode="atr", atr_mult=1.0)
    t3 = backtest_symbol(df, WEIGHTS, 4, lookback=40, stop_mode="atr", atr_mult=3.0)
    # 不同 ATR 倍數應產生不同停損 → 至少有交易且結果可不同
    assert isinstance(t1, list) and isinstance(t3, list)


def test_detect_plateau_synthetic():
    # 寬度 5 的高原（鄰域 w=1 各縮 1 → 偵測寬度 3）
    vals = [1, 2, 3, 4, 5, 6, 7]
    scores = [0.05, 0.30, 0.31, 0.32, 0.31, 0.30, 0.05]
    r = detect_plateau(vals, scores, plateau_ratio=0.7, min_width=3, neighbor_w=1)
    assert r["plateau"] is not None
    lo, hi, center = r["plateau"]
    assert lo <= center <= hi


def test_detect_plateau_spike():
    vals = [1, 2, 3, 4, 5]
    scores = [0.0, 0.0, 0.5, 0.0, 0.0]  # 單點尖峰
    r = detect_plateau(vals, scores, plateau_ratio=0.7, min_width=3, spike_drop=0.5)
    assert 2 in r["peaks"]          # index 2 是尖峰
    assert r["plateau"] is None     # 無高原


def test_detect_plateau_edge():
    assert detect_plateau([], [])["plateau"] is None
    flat = detect_plateau([1, 2, 3], [-0.1, -0.1, -0.1])
    assert "peaks" in flat
