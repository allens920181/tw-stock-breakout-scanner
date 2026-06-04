# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

from src.holdings import analyze_holding


def _uptrend(n=300, lo=50, hi=140):
    base = np.linspace(lo, hi, n)
    return pd.DataFrame({
        "Open": base, "High": base + 1.0, "Low": base - 1.0,
        "Close": base, "Volume": [2e6] * n,
    }, index=pd.date_range("2023-06-01", periods=n, freq="B"))


def test_strong_winner_runs_not_sold():
    """達 +2R 且趨勢仍強 → 強勢續抱（保留），不被目標價砍掉。"""
    df = _uptrend()
    ed = df.index[-30].date()
    entry = float(df["Close"].iloc[-30])
    row = analyze_holding("X.TW", "co", "TW", df, entry, ed, let_winners_run=True)
    assert row["R倍數"] is not None and row["R倍數"] >= 2
    assert row["賣出量"] == "保留"
    assert "續抱" in row["操作建議"]


def test_let_winners_run_off_sells_at_target():
    """關閉 let_winners_run → 達 +2R 一律了結（全出）。"""
    df = _uptrend()
    ed = df.index[-30].date()
    entry = float(df["Close"].iloc[-30])
    row = analyze_holding("X.TW", "co", "TW", df, entry, ed, let_winners_run=False)
    assert row["R倍數"] >= 2
    assert row["賣出量"] == "全出"
    assert "了結" in row["操作建議"]


def test_trend_strength_column_present():
    df = _uptrend()
    ed = df.index[-30].date()
    entry = float(df["Close"].iloc[-30])
    row = analyze_holding("X.TW", "co", "TW", df, entry, ed)
    assert "趨勢強度" in row and row["趨勢強度"]
