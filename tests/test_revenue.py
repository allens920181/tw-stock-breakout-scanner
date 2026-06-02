# -*- coding: utf-8 -*-
from src.revenue import classify_revenue

CFG = {"yoy_strong": 10.0, "yoy_weak": -20.0}


def test_classify_strong():
    label, warn, strong, weak = classify_revenue({"yoy_pct": 25.0}, CFG)
    assert strong is True and weak is False and warn is None
    assert "25" in label


def test_classify_weak():
    label, warn, strong, weak = classify_revenue({"yoy_pct": -35.0}, CFG)
    assert weak is True and strong is False
    assert warn is not None and "35" in warn


def test_classify_neutral():
    label, warn, strong, weak = classify_revenue({"yoy_pct": 3.0}, CFG)
    assert strong is False and weak is False and warn is None


def test_classify_missing():
    assert classify_revenue(None, CFG) == ("—", None, False, False)
    assert classify_revenue({"mom_pct": 5}, CFG) == ("—", None, False, False)


def test_scoring_weak_revenue_downgrades_entry():
    """營收大幅衰退 + 進場訊號 → 應降為觀察。"""
    import numpy as np
    import pandas as pd
    from src.scoring import analyze_stock

    n = 160
    close = np.linspace(40, 80, n)
    vol = np.concatenate([np.full(n - 1, 1e6), [5e6]])
    df = pd.DataFrame({
        "Open": close, "High": close + 1, "Low": close - 1,
        "Close": close, "Volume": vol,
    }, index=pd.date_range("2024-01-01", periods=n, freq="B"))
    cfg = {
        "filters": {"min_price": 10, "min_avg_volume": 1e5, "require_above_ma60": False,
                    "min_risk_pct": 0.02, "atr_mult": 1.5, "vol_multiple": 1.5,
                    "ext_threshold": 1.10},
        "scoring": {"weights": {"breakout_with_volume": 2, "ma_bullish": 2,
                                "turnover_strong": 2, "kd": 1, "macd": 1,
                                "rel_strength": 1, "trend_confirm": 1},
                    "thresholds": {"enter": 3, "watch": 2}},
        "position_sizing": {"total_capital": 1_000_000, "risk_per_trade_pct": 0.01,
                            "lot_size": 1000, "max_position_pct": 0.2},
        "revenue": {"yoy_strong": 10, "yoy_weak": -20, "downgrade_on_weak": True},
    }
    strong_rev = analyze_stock("X.TW", "co", "TW", df.copy(), 1e8, cfg,
                               revenue={"yoy_pct": 30.0})
    weak_rev = analyze_stock("X.TW", "co", "TW", df.copy(), 1e8, cfg,
                             revenue={"yoy_pct": -40.0})
    # 衰退版若原為進場應被降級；強勢版維持較高訊號
    order = {"進場": 2, "觀察": 1, "不操作": 0, "無法分析": -1}
    assert order[weak_rev["訊號判斷"]] <= order[strong_rev["訊號判斷"]]
    assert weak_rev["營收動能"].startswith("營收年減")
