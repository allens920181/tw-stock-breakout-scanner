# -*- coding: utf-8 -*-
"""
統計顯著性工具：bootstrap 信賴區間 + 樣本可信度。

防過擬合用：若期望值的 CI 跨 0（下界 ≤ 0），就不該據敏感度/高原峰值調參。
交易間非完全獨立（同期市場相關）→ 真實 CI 偏窄，文案以「樣本獨立假設下的下界」呈現。
"""
import numpy as np


def _arr(values):
    a = np.asarray([v for v in values if v is not None], dtype=float)
    return a[np.isfinite(a)]


def bootstrap_mean_ci(values, n_boot=1000, ci=0.95, seed=42):
    """對平均值做有放回重抽的信賴區間。回 {mean, low, high, n}。"""
    a = _arr(values)
    n = len(a)
    if n == 0:
        return {"mean": float("nan"), "low": float("nan"), "high": float("nan"), "n": 0}
    if n == 1:
        return {"mean": float(a[0]), "low": float(a[0]), "high": float(a[0]), "n": 1}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    means = a[idx].mean(axis=1)
    lo = float(np.percentile(means, (1 - ci) / 2 * 100))
    hi = float(np.percentile(means, (1 + ci) / 2 * 100))
    return {"mean": float(a.mean()), "low": lo, "high": hi, "n": n}


def bootstrap_diff_ci(group_a, group_b, n_boot=1000, ci=0.95, seed=42):
    """兩組平均差（a - b）的 bootstrap CI。回 {diff, low, high, n_a, n_b}。"""
    a = _arr(group_a)
    b = _arr(group_b)
    if len(a) == 0 or len(b) == 0:
        return {"diff": float("nan"), "low": float("nan"), "high": float("nan"),
                "n_a": len(a), "n_b": len(b)}
    rng = np.random.default_rng(seed)
    ia = rng.integers(0, len(a), size=(n_boot, len(a)))
    ib = rng.integers(0, len(b), size=(n_boot, len(b)))
    diffs = a[ia].mean(axis=1) - b[ib].mean(axis=1)
    lo = float(np.percentile(diffs, (1 - ci) / 2 * 100))
    hi = float(np.percentile(diffs, (1 + ci) / 2 * 100))
    return {"diff": float(a.mean() - b.mean()), "low": lo, "high": hi,
            "n_a": len(a), "n_b": len(b)}


def sample_reliability(n, cfg=None):
    """依交易筆數給可信度等級。回 {level, label, warn}。"""
    cfg = cfg or {}
    warn_thr = cfg.get("min_samples_warn", 100)
    reliable_thr = cfg.get("min_samples_reliable", 300)
    if n < 30:
        return {"level": "極度不足", "label": f"{n} 筆（<30，幾乎無統計意義）", "warn": True}
    if n < warn_thr:
        return {"level": "噪音", "label": f"{n} 筆（<{warn_thr}，統計噪音大）", "warn": True}
    if n < reliable_thr:
        return {"level": "偏少", "label": f"{n} 筆（<{reliable_thr}，參考用）", "warn": False}
    return {"level": "足夠", "label": f"{n} 筆", "warn": False}
