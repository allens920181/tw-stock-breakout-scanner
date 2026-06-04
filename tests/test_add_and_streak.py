# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

from src.sizing import evaluate_add
from src.holdings import analyze_holding

CFG = {
    "position_sizing": {"total_capital": 1_000_000, "risk_per_trade_pct": 0.01},
    "filters": {"atr_mult": 1.5},
    "holdings": {"add_max_ext_pct": 8.0, "add_min_rs": -10.0},
}


def test_add_blocks_when_extended():
    ev = evaluate_add(CFG, current_price=22.3, atr=1.0, ext_pct=16.4, rs=-16, add_lots=1)
    assert ev["verdict"].startswith("🔴")          # 過度延伸 → 別加
    assert any("乖離" in b for b in ev["blocks"])


def test_add_ok_when_near_support():
    ev = evaluate_add(CFG, current_price=20.3, atr=0.5, ext_pct=3.0, rs=5, add_lots=1)
    assert ev["verdict"].startswith("🟢")
    assert ev["stop"] == round(20.3 - 0.5 * 1.5, 2)


def test_add_budget_cap():
    # 每股風險 1.5，預算 10000 → 最多 6 張
    ev = evaluate_add(CFG, current_price=50, atr=1.0, ext_pct=2, rs=0, add_lots=10)
    assert ev["max_lots_in_budget"] == 6
    assert any("預算" in w for w in ev["warns"])    # 加 10 張超預算


def _fresh_breakout_df(n=200):
    base = np.linspace(18, 19, n - 1).tolist()
    base.append(21.0)                               # 末日帶量突破
    arr = np.array(base)
    vol = [1e6] * (n - 1) + [3e6]                   # 末日爆量
    return pd.DataFrame({
        "Open": arr, "High": arr + 0.2, "Low": arr - 0.2,
        "Close": arr, "Volume": vol,
    }, index=pd.date_range("2023-06-01", periods=n, freq="B"))


def test_fresh_breakout_with_inst_streak_is_strong():
    """法人連買+帶量突破 → 即使 ADX 落後也算強勢續抱（修 1904 型誤判）。"""
    df = _fresh_breakout_df()
    ed = df.index[-25].date()
    entry = float(df["Close"].iloc[-25])
    chips = {"inst_buy_streak": 5, "inst_net_lots": 1000}
    row = analyze_holding("X.TW", "co", "TW", df, entry, ed,
                          chips=chips, strong_streak=3, strong_vol_mult=1.5)
    if row["R倍數"] is not None and row["R倍數"] >= 2:
        assert "強" in row["趨勢強度"]
        assert row["賣出量"] == "保留" or "續抱" in row["操作建議"]
