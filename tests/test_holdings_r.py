# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

from src.holdings import analyze_holding


def _df(n=300, lo=60, hi=115):
    base = np.linspace(lo, hi, n)
    return pd.DataFrame({
        "Open": base, "High": base + 1.5, "Low": base - 1.5,
        "Close": base, "Volume": [2e6] * n,
    }, index=pd.date_range("2023-06-01", periods=n, freq="B"))


def test_winner_has_positive_R_not_none():
    """回歸：獲利持股的 R 不該因『重估停損>進場價』而變 None。"""
    df = _df()
    ed = df.index[-30].date()
    entry = float(df["Close"].iloc[-30])
    row = analyze_holding("X.TW", "co", "TW", df, entry, ed)
    assert row["R倍數"] is not None
    assert row["R倍數"] > 0                       # 上漲中應為正 R
    # 硬停損 = 進場 - ATR×1.5 < 進場
    assert row["停損價"] < entry


def test_R_uses_fixed_risk_not_moving_ma20():
    """R 基準固定（ATR），不隨價格上漲而讓 risk→0。"""
    df = _df()
    ed = df.index[-40].date()
    entry = float(df["Close"].iloc[-40])
    row = analyze_holding("X.TW", "co", "TW", df, entry, ed)
    risk = entry - row["停損價"]
    expected_r = (row["目前價"] - entry) / risk
    assert abs(row["R倍數"] - round(expected_r, 2)) < 0.05
