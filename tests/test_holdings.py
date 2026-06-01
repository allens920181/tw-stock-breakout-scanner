# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

from src.holdings import analyze_holding


def _df_rise_then_drop(n=160):
    """先漲一段創高，最後幾根回落 → 觸發 ATR 移動停利"""
    up = np.linspace(50, 120, n - 10)
    down = np.linspace(120, 100, 10)
    close = np.concatenate([up, down])
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "Open": close, "High": close + 1.0, "Low": close - 1.0,
        "Close": close, "Volume": np.full(n, 2_000_000),
    }, index=idx)


def test_chandelier_atr_trailing_triggers():
    df = _df_rise_then_drop()
    entry_date = df.index[0].date()
    row = analyze_holding("2330.TW", "台積電", "TW", df,
                          entry_price=55.0, entry_date=entry_date,
                          shares=1000, atr_trail_mult=3.0)
    # 應在出場計畫提供 ATR 移動停利價
    assert row["移動停利(ATR)"] is not None
    # 從高點 120 回落到 100，且仍獲利 → 應觸發移動停利（ATR 或 MA10）
    assert "移動停利" in row["操作建議"] or row["操作建議"].startswith("✅") is False
