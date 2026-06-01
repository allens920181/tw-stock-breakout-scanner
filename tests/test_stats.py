# -*- coding: utf-8 -*-
import numpy as np

from src.stats import bootstrap_diff_ci, bootstrap_mean_ci, sample_reliability


def test_bootstrap_mean_ci_basic():
    r = bootstrap_mean_ci([1, 2, 3, 4, 5], seed=1)
    assert r["low"] <= r["mean"] <= r["high"]
    assert r["n"] == 5


def test_bootstrap_all_positive_lower_bound():
    r = bootstrap_mean_ci(list(np.full(200, 2.0)), seed=1)
    assert r["low"] > 0


def test_bootstrap_zeros():
    r = bootstrap_mean_ci([0.0] * 50, seed=1)
    assert abs(r["low"]) < 1e-9 and abs(r["high"]) < 1e-9


def test_bootstrap_edge_cases():
    assert bootstrap_mean_ci([])["n"] == 0
    one = bootstrap_mean_ci([3.0])
    assert one["low"] == one["high"] == 3.0


def test_sample_reliability_thresholds():
    assert sample_reliability(50)["warn"] is True
    assert sample_reliability(99)["warn"] is True
    assert sample_reliability(100)["warn"] is False
    assert sample_reliability(500)["level"] == "足夠"


def test_bootstrap_diff_separation():
    a = list(np.full(100, 1.0))
    b = list(np.full(100, -1.0))
    d = bootstrap_diff_ci(a, b, seed=1)
    assert d["low"] > 0           # 明顯分離 → CI 不跨 0
    same = bootstrap_diff_ci(a, a, seed=1)
    assert same["low"] <= 0 <= same["high"]
