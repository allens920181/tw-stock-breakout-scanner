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


def test_chip_sell_downgrades_entry():
    """法人賣超應把進場降為觀察（避免買在出貨）"""
    df = _strong_uptrend_df()
    cfg = {**CFG, "chips": {"sell_downgrade": True}}
    base = analyze_stock("2330.TW", "台積電", "TW", df, shares=10_000_000_000,
                         cfg=cfg, chips={"inst_net_lots": -5000, "foreign_net_lots": -4000})
    assert base["籌碼確認"] == "法人賣超"
    assert base["法人買賣超(張)"] == -5000
    # 進場訊號遇法人賣超 → 不應仍是進場
    assert base["訊號判斷"] != "進場"


def test_chip_buy_confirms():
    df = _strong_uptrend_df()
    res = analyze_stock("2330.TW", "台積電", "TW", df, shares=10_000_000_000,
                        cfg=CFG, chips={"inst_net_lots": 8000, "foreign_net_lots": 6000})
    assert res["籌碼確認"] == "法人買超"


def test_chip_buy_streak_label():
    df = _strong_uptrend_df()
    res = analyze_stock("2330.TW", "台積電", "TW", df, shares=10_000_000_000,
                        cfg=CFG, chips={"inst_net_lots": 8000, "foreign_net_lots": 6000,
                                        "inst_buy_streak": 3, "inst_net_5d_lots": 20000})
    assert res["籌碼確認"] == "法人連買3日"
    assert res["法人連買天數"] == 3
    assert res["法人5日累計(張)"] == 20000


def test_margin_surge_flag():
    df = _strong_uptrend_df()
    res = analyze_stock("2330.TW", "台積電", "TW", df, shares=10_000_000_000, cfg=CFG,
                        margin={"margin_chg_pct": 35.0, "short_margin_ratio": 1.0})
    assert res["融資券提示"] == "融資爆增"
    assert res["融資增減%"] == 35.0


def test_margin_high_short_ratio():
    df = _strong_uptrend_df()
    res = analyze_stock("2330.TW", "台積電", "TW", df, shares=10_000_000_000, cfg=CFG,
                        margin={"margin_chg_pct": 1.0, "short_margin_ratio": 25.0})
    assert res["融資券提示"] == "高券資比"


def test_margin_surge_downgrade_optional():
    df = _strong_uptrend_df()
    cfg = {**CFG, "margin": {"surge_downgrade": True, "surge_pct": 10.0}}
    res = analyze_stock("2330.TW", "台積電", "TW", df, shares=10_000_000_000, cfg=cfg,
                        margin={"margin_chg_pct": 30.0, "short_margin_ratio": 1.0})
    assert res["訊號判斷"] != "進場"


def test_no_chips_ok():
    df = _strong_uptrend_df()
    res = analyze_stock("2330.TW", "台積電", "TW", df, shares=10_000_000_000, cfg=CFG)
    assert res["籌碼確認"] == "—"
    assert res["法人買賣超(張)"] is None


def test_insufficient_data():
    df = pd.DataFrame({
        "Open": [1, 2], "High": [1, 2], "Low": [1, 2],
        "Close": [1, 2], "Volume": [1, 2],
    })
    res = analyze_stock("0001.TW", "TEST", "TW", df, shares=1, cfg=CFG)
    assert res["狀態"] == "資料不足"


def test_verdict_grade_present():
    df = _strong_uptrend_df()
    res = analyze_stock("2330.TW", "台積電", "TW", df, shares=10_000_000_000, cfg=CFG)
    assert res["綜合評級"] in ("A", "B", "C", "避開")
    assert isinstance(res["評級理由"], str) and len(res["評級理由"]) > 0


def test_verdict_avoid_on_chip_sell():
    df = _strong_uptrend_df()
    res = analyze_stock("2330.TW", "台積電", "TW", df, shares=10_000_000_000, cfg=CFG,
                        chips={"inst_net_lots": -8000, "foreign_net_lots": -5000})
    # 法人賣超會把進場降觀察 → 不可能是 A 級
    assert res["綜合評級"] != "A"
