# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd

from src.factor_eval import factor_correlation, suggest_weights_from_lift

CFG = {"scoring": {"weights": {
    "breakout_with_volume": 2, "ma_bullish": 2, "turnover_strong": 2,
    "kd": 1, "macd": 1, "rel_strength": 1, "trend_confirm": 1}}}


def test_suggest_weights_basic():
    fe = {"lift_map": {"breakout_vol": 0.5, "ma_bullish": 0.3, "kd": -0.1,
                       "macd": 0.0, "rel_strength": 0.1, "trend_confirm": 0.05}}
    out = suggest_weights_from_lift(fe, CFG, total=8, eps=0.02)
    w = out["weights"]
    assert w["kd"] == 0 and w["macd"] == 0          # 負/≈0 歸零
    assert w["breakout_with_volume"] > w["ma_bullish"]  # lift 高者權重高
    assert all(0 <= v <= 5 for v in w.values())
    assert w["turnover_strong"] == 2                 # 沿用原權重（無 lift）


def test_suggest_weights_all_nonpositive():
    fe = {"lift_map": {"breakout_vol": -0.5, "ma_bullish": -0.3}}
    out = suggest_weights_from_lift(fe, CFG)
    assert out["weights"]["breakout_with_volume"] == 0
    assert out["weights"]["turnover_strong"] == 2    # preserve


def test_suggest_weights_empty():
    out = suggest_weights_from_lift({"lift_map": {}}, CFG)
    assert out["weights"] == CFG["scoring"]["weights"]


def test_factor_correlation_collinear():
    n = 200
    rng = np.random.default_rng(0)
    a = rng.integers(0, 2, n).astype(bool)
    data = pd.DataFrame({
        "breakout_vol": a, "ma_bullish": a,          # 完全共線
        "kd": rng.integers(0, 2, n).astype(bool),
        "macd": rng.integers(0, 2, n).astype(bool),
        "rel_strength": rng.integers(0, 2, n).astype(bool),
        "trend_confirm": rng.integers(0, 2, n).astype(bool),
        "r": rng.normal(0, 1, n),
    })
    out = factor_correlation(data, lift_map={"breakout_vol": 0.3, "ma_bullish": 0.1}, high_thresh=0.7)
    assert any(abs(p["phi"]) > 0.99 for p in out["pairs"])
    assert any("半" not in str(g) and g["建議保留"] for g in out["groups"])
    # 保留 lift 較高的 breakout
    grp = out["groups"][0]
    assert grp["建議保留"] == "突破+量增"


def test_factor_correlation_constant_column_nan():
    n = 100
    data = pd.DataFrame({
        "breakout_vol": np.ones(n, dtype=bool),       # 全 True → phi NaN
        "ma_bullish": np.random.default_rng(1).integers(0, 2, n).astype(bool),
        "kd": np.zeros(n, dtype=bool), "macd": np.zeros(n, dtype=bool),
        "rel_strength": np.zeros(n, dtype=bool), "trend_confirm": np.zeros(n, dtype=bool),
        "r": np.random.default_rng(2).normal(0, 1, n),
    })
    out = factor_correlation(data, high_thresh=0.7)
    # 全 True 欄與他欄 phi=NaN → 不應出現在 pairs
    assert all("突破+量增" not in (p["因子A"], p["因子B"]) for p in out["pairs"])
