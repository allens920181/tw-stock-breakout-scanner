# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

from src.adaptive import (
    pick_applicable, recommend_from_backtest, recommend_regime_thresholds,
)
from src.indicators import add_indicators


def _df(n=180, seed=0):
    rng = np.random.default_rng(seed)
    drift = np.linspace(40, 130, n)
    noise = rng.normal(0, 1.2, n).cumsum() * 0.3
    close = drift + noise
    idx = pd.date_range("2023-06-01", periods=n, freq="B")
    vol = rng.uniform(8e5, 1.5e6, n)
    vol[-1] = 5e6
    return add_indicators(pd.DataFrame({
        "Open": close, "High": close + 1.2, "Low": close - 1.2,
        "Close": close, "Volume": vol,
    }, index=idx)).dropna()


CFG = {
    "data": {"period": "1y", "cache_dir": ".cache"},
    "filters": {"atr_mult": 1.5},
    "scoring": {
        "weights": {"breakout_with_volume": 2, "ma_bullish": 2, "turnover_strong": 2,
                    "kd": 1, "macd": 1, "rel_strength": 1, "trend_confirm": 1},
        "thresholds": {"enter": 6, "watch": 4},
        "lift_weights": {"total": 8, "eps": 0.02},
    },
    "costs": {"enabled": True, "fee_rate": 0.001425, "tax_rate": 0.003,
              "slippage_pct": 0.0015},
    "sensitivity": {"plateau": {
        "min_score_grid": [3, 4, 5, 6, 7], "atr_mult_grid": [1.0, 1.5, 2.0, 2.5, 3.0],
        "tp_mult_grid": [1.5, 2.0, 2.5, 3.0], "plateau_ratio": 0.6,
        "min_width": 3, "neighbor_w": 1, "spike_drop": 0.5,
    }},
}


def test_recommend_thresholds_structure():
    resolved = [{"symbol": f"T{i}.TW", "company_name": f"co{i}", "df": _df(seed=i)}
                for i in range(6)]
    out = recommend_from_backtest(
        resolved, CFG, lookback=60, hold_days=8, targets=("thresholds",),
    )
    assert out["weights"] is None and out["regime"] is None
    assert len(out["params"]) == 3
    names = {p["param"] for p in out["params"]}
    assert names == {"min_score", "atr_mult", "tp_mult"}
    for p in out["params"]:
        assert "current" in p and "recommended" in p and "oos_ok" in p
        # 建議值（若有高原）必在該參數網格內
        if p["recommended"] is not None:
            grid = CFG["sensitivity"]["plateau"][f"{p['param']}_grid"]
            assert p["recommended"] in grid


def test_pick_applicable_oos_gate():
    ar = {
        "params": [
            {"param": "min_score", "current": 6, "recommended": 5, "oos_ok": True},
            {"param": "atr_mult", "current": 1.5, "recommended": 2.5, "oos_ok": False},
            {"param": "tp_mult", "current": 2.0, "recommended": 2.5, "oos_ok": True},
        ],
        "weights": {"current": {"kd": 1}, "recommended": {"kd": 2, "macd": 1}},
        "regime": {"by_regime": {
            "bull": {"recommended": 4}, "neutral": {"recommended": 6},
            "bear": {"recommended": 8}}},
    }
    plan = pick_applicable(ar, require_oos=True)
    ap = plan["applied"]
    assert ap["thr_enter"] == 5                 # OOS✅ → 套用
    assert "f_atr_mult" not in ap               # OOS❌ → 擋下
    assert ap["weights"] == {"kd": 2, "macd": 1}
    assert ap["regime_thresholds"] == {"bull": 4, "neutral": 6, "bear": 8}
    # tp_mult 永不套用（回測框架）；atr 被擋的原因有列入 skipped
    reasons = dict(plan["skipped"])
    assert "atr_mult" in reasons


def test_regime_thresholds_fallback():
    # 無 regime 標記的交易 → 各 regime 應回退整體最佳（fallback=True）
    resolved = [{"symbol": f"T{i}.TW", "company_name": f"co{i}", "df": _df(seed=i)}
                for i in range(4)]
    out = recommend_regime_thresholds(
        resolved, CFG, grid=[3, 4, 5, 6, 7], lookback=60, hold_days=8,
        regime_map=None, min_n=999,
    )
    assert out["overall_best"] in [3, 4, 5, 6, 7]
    for rg in ("bull", "neutral", "bear"):
        assert out["by_regime"][rg]["fallback"] is True
        assert out["by_regime"][rg]["recommended"] == out["overall_best"]
