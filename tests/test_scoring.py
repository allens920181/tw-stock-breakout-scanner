import numpy as np
import pandas as pd

from src.scoring import analyze_stock


CFG = {
    "filters": {
        "min_price": 10,
        "min_avg_volume": 500_000,
        "require_above_ma60": True,
        "min_risk_pct": 0.02,
    },
    "scoring": {
        "weights": {
            "breakout_with_volume": 2,
            "ma_bullish": 2,
            "turnover_strong": 2,
            "kd": 1,
            "macd": 1,
        },
        "thresholds": {"enter": 6, "watch": 5},
    },
}


def _strong_uptrend_df(n=120):
    """單純遞增 → MA 多頭、突破、量增、KD 高、MACD 多方"""
    closes = np.linspace(50, 200, n)
    df = pd.DataFrame({
        "Open": closes,
        "High": closes + 0.5,
        "Low": closes - 0.5,
        "Close": closes,
        "Volume": np.concatenate([
            np.full(n - 1, 1_000_000),
            np.array([5_000_000]),  # 最後一日爆量
        ]),
    })
    return df


def test_strong_signal():
    df = _strong_uptrend_df()
    res = analyze_stock("2330.TW", "台積電", "TW", df, shares=10_000_000_000, cfg=CFG)
    assert res["狀態"].startswith("成功")
    assert res["評分"] >= CFG["scoring"]["thresholds"]["watch"]
    assert res["訊號判斷"] in ("進場", "觀察")


def test_filter_low_price():
    df = _strong_uptrend_df()
    df[["Open", "High", "Low", "Close"]] = df[["Open", "High", "Low", "Close"]] / 100
    res = analyze_stock("0001.TW", "TEST", "TW", df, shares=10_000_000, cfg=CFG)
    assert "股價<" in res["狀態"]


def test_filter_low_liquidity():
    df = _strong_uptrend_df()
    df["Volume"] = 1000
    res = analyze_stock("0001.TW", "TEST", "TW", df, shares=10_000_000, cfg=CFG)
    assert res["狀態"] == "流動性不足"


def test_insufficient_data():
    df = pd.DataFrame({
        "Open": [1, 2], "High": [1, 2], "Low": [1, 2],
        "Close": [1, 2], "Volume": [1, 2],
    })
    res = analyze_stock("0001.TW", "TEST", "TW", df, shares=1, cfg=CFG)
    assert res["狀態"] == "資料不足"
