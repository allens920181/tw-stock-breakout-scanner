"""回測敏感度：跑多個 min_score 比較 edge"""
import numpy as np
import pandas as pd

from .backtest import backtest_symbol, summarize_trades


def sensitivity_scan(resolved, cfg, score_range, lookback_days, hold_days,
                     progress_cb=None):
    """
    對指定股票清單，跑多個 min_score 並彙整。
    回傳 DataFrame：score | n_trades | win_rate | avg_R | expectancy | max_dd
    """
    weights = cfg["scoring"]["weights"]
    costs = cfg.get("costs")
    rows = []
    total_steps = len(score_range)

    for step_i, score in enumerate(score_range):
        all_trades = []
        for r in resolved:
            try:
                trades = backtest_symbol(
                    r["df"], weights, score,
                    hold_days=hold_days, lookback=lookback_days, costs=costs,
                )
                all_trades.extend(trades)
            except Exception:
                pass

        s = summarize_trades(all_trades, cfg)
        rows.append({
            "min_score": score,
            "總交易數": s["總交易數"],
            "勝率%": s["勝率%"],
            "平均報酬%": s["平均報酬%"],
            "平均R": s["平均R"],
            "期望值R": s["期望值R"],
            "期望值R_CI下界": s.get("期望值R_CI下界"),
            "期望值R_CI上界": s.get("期望值R_CI上界"),
            "顯著": s.get("顯著正Edge"),
            "最大回撤R": s["最大回撤R"],
        })

        if progress_cb:
            try:
                progress_cb(step_i + 1, total_steps, score)
            except Exception:
                pass

    return pd.DataFrame(rows)


def plateau_scan(resolved, cfg, param_name, grid, lookback_days, hold_days,
                 progress_cb=None):
    """
    對單一參數（min_score / atr_mult / tp_mult）一維掃描，每格重跑回測。
    回傳 DataFrame：param_value | 總交易數 | 勝率% | 平均R | 期望值R | 最大回撤R
    """
    weights = cfg["scoring"]["weights"]
    costs = cfg.get("costs")
    base_min_score = cfg["scoring"]["thresholds"].get("enter", 7)
    base_atr = cfg["filters"].get("atr_mult", 1.5)
    rows = []
    for gi, val in enumerate(grid):
        min_score = base_min_score
        stop_mode, atr_mult, tp_mult = "ma", None, 2.0
        if param_name == "min_score":
            min_score = val
        elif param_name == "atr_mult":
            stop_mode, atr_mult = "atr", val
        elif param_name == "tp_mult":
            tp_mult = val
            stop_mode, atr_mult = "atr", base_atr  # 停利掃描固定 ATR 停損框架
        all_trades = []
        for r in resolved:
            try:
                all_trades.extend(backtest_symbol(
                    r["df"], weights, min_score,
                    hold_days=hold_days, lookback=lookback_days, costs=costs,
                    stop_mode=stop_mode, atr_mult=atr_mult, tp_mult=tp_mult,
                ))
            except Exception:
                pass
        s = summarize_trades(all_trades, cfg)
        rows.append({
            "param_value": val, "總交易數": s["總交易數"], "勝率%": s["勝率%"],
            "平均R": s["平均R"], "期望值R": s["期望值R"], "最大回撤R": s["最大回撤R"],
        })
        if progress_cb:
            try:
                progress_cb(gi + 1, len(grid), val)
            except Exception:
                pass
    return pd.DataFrame(rows)


def detect_plateau(values, scores, plateau_ratio=0.7, min_width=3,
                   neighbor_w=1, spike_drop=0.5):
    """
    從期望值曲線找「高原」與「尖峰」。
    高原 = 連續區段內每點的鄰域最小值 ≥ 全域最大 × plateau_ratio 且寬度 ≥ min_width。
    尖峰 = 該點高（≥ 全域最大）但鄰域落差大。
    回傳 {plateau:(lo,hi,center)|None, peaks:[idx], neighbor_min:[...], recommended:value|None}
    """
    s = np.asarray(scores, dtype=float)
    v = list(values)
    n = len(s)
    if n == 0:
        return {"plateau": None, "peaks": [], "neighbor_min": [], "recommended": None}
    gmax = float(np.nanmax(s))
    neigh_min = []
    for i in range(n):
        lo = max(0, i - neighbor_w)
        hi = min(n, i + neighbor_w + 1)
        neigh_min.append(float(np.nanmin(s[lo:hi])))
    neigh_min = np.asarray(neigh_min)

    thr = gmax * plateau_ratio if gmax > 0 else gmax
    robust = neigh_min >= thr
    # 找最長連續 robust 區段
    best = None
    i = 0
    while i < n:
        if robust[i]:
            j = i
            while j < n and robust[j]:
                j += 1
            if (j - i) >= min_width and (best is None or (j - i) > (best[1] - best[0] + 1)):
                best = (i, j - 1)
            i = j
        else:
            i += 1
    plateau = None
    recommended = None
    if best is not None:
        center = (best[0] + best[1]) // 2
        plateau = (v[best[0]], v[best[1]], v[center])
        recommended = v[center]

    peaks = []
    for i in range(n):
        if s[i] >= gmax and gmax > 0:
            drop = (s[i] - neigh_min[i]) / abs(s[i]) if s[i] != 0 else 0
            if drop >= spike_drop:
                peaks.append(i)
    return {"plateau": plateau, "peaks": peaks,
            "neighbor_min": neigh_min.tolist(), "recommended": recommended}
