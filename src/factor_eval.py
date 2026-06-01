# -*- coding: utf-8 -*-
"""
因子增量貢獻驗證（factor lift / ablation）

問題：評分權重是手設的，沒有證據哪些因子真的提升期望值。
做法：對歷史每根 K 棒，
  1) 用「進場=收盤、停損=ATR×倍數、持有 hold_days 或先觸 +2R/停損」算出未來 R 倍數；
  2) 記錄該棒各因子是否成立（突破量增 / MA多頭 / KD / MACD / 相對強度 / 趨勢確認）；
彙總後比較每個因子「成立 vs 不成立」的平均 R，差值（lift）即該因子的增量貢獻。

僅驗證可由歷史價量 + 大盤算出的因子。
換手率（需歷史流通股數）、籌碼 / 融資券（僅當日快照、無歷史）→ 無法在此驗證，另註明。
"""
import logging

import numpy as np
import pandas as pd

from .indicators import add_indicators
from .market import fetch_twii

log = logging.getLogger(__name__)

# 可驗證因子（價量 / 大盤可重算）
FACTORS = [
    ("breakout_vol", "突破+量增"),
    ("ma_bullish", "MA多頭"),
    ("kd", "KD強勢"),
    ("macd", "MACD多方"),
    ("rel_strength", "相對強度RS"),
    ("trend_confirm", "趨勢確認"),
]


def _twii_ret60(cache_dir, period):
    """大盤 60 日報酬序列（index=日期），給相對強度比較。"""
    try:
        tw = fetch_twii(period, cache_dir)
        tw = add_indicators(tw).dropna()
        s = tw["Close"].pct_change(60) * 100
        s.index = pd.to_datetime(tw.index)
        return s
    except Exception as e:
        log.warning("TWII 報酬序列失敗：%s", e)
        return None


def _bar_factors(df, i, twii_ret, vol_mult):
    """回傳該棒各因子布林 dict；資料不足回 None。"""
    if i < 60:
        return None
    latest = df.iloc[i]
    close = float(latest["Close"])
    high_20 = df["High"].iloc[i - 20:i].max()
    vol50 = df["Volume"].iloc[max(0, i - 49):i + 1].mean()
    if not np.isfinite(close) or not np.isfinite(vol50) or vol50 <= 0:
        return None

    breakout_vol = bool(close > high_20 and latest["Volume"] >= vol50 * vol_mult)
    ma_bullish = bool(latest["MA5"] > latest["MA20"] > latest["MA60"]
                      and close > latest["MA20"])
    kd = bool(latest["K"] > latest["D"] and latest["K"] > 70)
    macd = bool(latest["OSC"] > 0)

    # 相對強度：個股 60 日報酬 vs 大盤同日 60 日報酬
    rel_strength = False
    if twii_ret is not None and i >= 60:
        past = float(df["Close"].iloc[i - 60])
        if past > 0:
            stock_ret = (close / past - 1) * 100
            dt = pd.to_datetime(df.index[i])
            tw_val = twii_ret.asof(dt) if len(twii_ret) else np.nan
            if np.isfinite(tw_val):
                rel_strength = bool(stock_ret > tw_val)

    # 趨勢確認：ADX>20 或 MA60 斜率向上
    adx_ok = bool(np.isfinite(latest.get("ADX14", np.nan)) and latest["ADX14"] > 20)
    slope_ok = False
    if i >= 5 and np.isfinite(df["MA60"].iloc[i]) and np.isfinite(df["MA60"].iloc[i - 5]):
        slope_ok = bool(df["MA60"].iloc[i] - df["MA60"].iloc[i - 5] > 0)
    trend_confirm = bool(adx_ok or slope_ok)

    return {
        "breakout_vol": breakout_vol, "ma_bullish": ma_bullish,
        "kd": kd, "macd": macd, "rel_strength": rel_strength,
        "trend_confirm": trend_confirm,
    }


def _forward_r(df, i, hold_days, atr_mult, costs=None):
    """ATR 停損框架下，第 i 棒進場的未來淨 R 倍數；無效回 None。
    costs：來回成本以「成本率 / (risk/entry)」換算成 R 折減，於各出場情境一致扣除。"""
    latest = df.iloc[i]
    entry = float(latest["Close"])
    atr = float(latest.get("ATR14", np.nan))
    if not np.isfinite(atr) or atr <= 0 or entry <= 0:
        return None
    risk = atr * atr_mult
    stop = entry - risk
    target_2r = entry + 2 * risk

    from .backtest import _apply_costs
    end = min(i + 1 + hold_days, len(df))
    for j in range(i + 1, end):
        bar = df.iloc[j]
        if float(bar["Low"]) <= stop:
            _, r = _apply_costs(entry, stop, risk, costs)
            return r if r is not None else -1.0
        if float(bar["High"]) >= target_2r:
            _, r = _apply_costs(entry, target_2r, risk, costs)
            return r if r is not None else 2.0
    if end - 1 > i:
        exit_price = float(df.iloc[end - 1]["Close"])
        _, r = _apply_costs(entry, exit_price, risk, costs)
        return r
    return None


def evaluate_factors(resolved, cfg, lookback=250, hold_days=10, max_symbols=None):
    """
    回傳 dict:
      table: DataFrame（每因子 on/off 的樣本數、平均R、勝率、lift）
      base:  整體基準（所有樣本平均R / 勝率 / 樣本數）
      note:  無法驗證的因子說明
    """
    filters = cfg.get("filters", {})
    atr_mult = filters.get("atr_mult", 1.5)
    vol_mult = filters.get("vol_multiple", 1.5)
    period = cfg.get("data", {}).get("period", "1y")
    cache_dir = cfg.get("data", {}).get("cache_dir", ".cache")

    costs_cfg = cfg.get("costs")
    costs = costs_cfg if (costs_cfg and costs_cfg.get("apply_to_factor_eval", False)) else None

    twii_ret = _twii_ret60(cache_dir, period)

    rows = []  # 每筆：{factor bools..., 'r': float}
    items = resolved if max_symbols is None else resolved[:max_symbols]
    for r in items:
        df = r.get("df")
        if df is None or df.empty:
            continue
        d = add_indicators(df).dropna()
        if len(d) < 80:
            continue
        start = max(60, len(d) - lookback)
        for i in range(start, len(d) - 1):
            fac = _bar_factors(d, i, twii_ret, vol_mult)
            if fac is None:
                continue
            rmult = _forward_r(d, i, hold_days, atr_mult, costs=costs)
            if rmult is None:
                continue
            fac["r"] = rmult
            rows.append(fac)

    if not rows:
        return {"table": pd.DataFrame(), "base": {}, "note": "樣本不足"}

    data = pd.DataFrame(rows)
    from .stats import bootstrap_diff_ci, bootstrap_mean_ci
    stats_cfg = cfg.get("stats", {})
    nboot = stats_cfg.get("bootstrap_n", 1000)
    seed = stats_cfg.get("seed", 42)
    base_ci = bootstrap_mean_ci(data["r"].tolist(), n_boot=nboot, seed=seed)
    base = {
        "樣本數": int(len(data)),
        "整體平均R": round(float(data["r"].mean()), 3),
        "整體平均R_CI下界": round(base_ci["low"], 3),
        "整體平均R_CI上界": round(base_ci["high"], 3),
        "整體勝率%": round(float((data["r"] > 0).mean() * 100), 1),
    }

    out = []
    lift_map = {}
    for key, label in FACTORS:
        on = data[data[key]]
        off = data[~data[key]]
        if len(on) == 0 or len(off) == 0:
            continue
        r_on = float(on["r"].mean())
        r_off = float(off["r"].mean())
        lift_map[key] = r_on - r_off
        dci = bootstrap_diff_ci(on["r"].tolist(), off["r"].tolist(), n_boot=nboot, seed=seed)
        out.append({
            "因子": label,
            "成立樣本": int(len(on)),
            "成立平均R": round(r_on, 3),
            "成立勝率%": round(float((on["r"] > 0).mean() * 100), 1),
            "不成立平均R": round(r_off, 3),
            "lift(R)": round(r_on - r_off, 3),
            "lift_CI下界": round(dci["low"], 3),
            "lift_CI上界": round(dci["high"], 3),
            "顯著": bool(dci["low"] > 0 or dci["high"] < 0),
        })
    table = pd.DataFrame(out).sort_values("lift(R)", ascending=False) if out else pd.DataFrame()

    note = ("換手率需歷史流通股數、籌碼/融資券僅當日快照無歷史，"
            "無法在此回測驗證；其餘 6 因子如上。lift(R) > 0 代表該因子提升期望值。")
    corr_info = factor_correlation(
        data, lift_map=lift_map,
        high_thresh=cfg.get("factor_eval", {}).get("corr_high_thresh", 0.7),
    )
    return {"table": table, "base": base, "note": note,
            "lift_map": lift_map, "data": data, **corr_info}


# factor_eval 鍵 → scoring 權重鍵
_FE_TO_SCORING = {
    "breakout_vol": "breakout_with_volume",
    "ma_bullish": "ma_bullish",
    "kd": "kd",
    "macd": "macd",
    "rel_strength": "rel_strength",
    "trend_confirm": "trend_confirm",
}


def suggest_weights_from_lift(fe_result, cfg, total=8, eps=0.02,
                              min_w=0, max_w=5, preserve_unverifiable=None):
    """
    依 lift(R) 建議一組權重：正 lift ∝ 重要性、負/≈0 歸零。
    無歷史 lift 的因子（換手率）沿用 cfg 現有權重，不歸零。
    回 {weights, detail(list), note}。
    """
    if preserve_unverifiable is None:
        preserve_unverifiable = ["turnover_strong"]
    lift_map = (fe_result or {}).get("lift_map") or {}
    cur = dict(cfg.get("scoring", {}).get("weights", {}))

    if not lift_map:
        return {"weights": cur, "detail": [], "note": "無 lift 資料，沿用現有權重"}

    pos = {k: max(v, 0.0) for k, v in lift_map.items() if abs(v) >= eps and v > 0}
    total_pos = sum(pos.values())
    weights = {}
    detail = []
    for fe_key, sc_key in _FE_TO_SCORING.items():
        lift = lift_map.get(fe_key)
        if total_pos > 0 and fe_key in pos:
            w = int(round(total * pos[fe_key] / total_pos))
        else:
            w = 0
        w = max(min_w, min(max_w, w))
        weights[sc_key] = w
        detail.append({"因子": sc_key, "lift(R)": round(lift, 3) if lift is not None else None,
                       "原權重": cur.get(sc_key, 0), "建議權重": w})

    # 無 lift 證據的因子沿用原權重
    for sc_key in preserve_unverifiable:
        weights[sc_key] = cur.get(sc_key, 0)
        detail.append({"因子": sc_key, "lift(R)": None,
                       "原權重": cur.get(sc_key, 0), "建議權重": weights[sc_key]})

    note = (f"正 lift 因子按比例分配 {total} 分；|lift|<{eps} 或負值歸零；"
            f"{', '.join(preserve_unverifiable)} 無歷史 lift 故沿用原權重。")
    return {"weights": weights, "detail": detail, "note": note}


def factor_correlation(data, lift_map=None, high_thresh=0.7):
    """
    6 因子兩兩 phi 相關（0/1 序列的 Pearson）。回 {corr, pairs, groups}。
    高相關群內保留 lift 最高者、其餘建議合併/降權。0 變異欄 phi=NaN 已過濾。
    """
    keys = [k for k, _ in FACTORS if k in data.columns]
    labels = {k: lab for k, lab in FACTORS}
    if not keys:
        return {"corr": pd.DataFrame(), "pairs": [], "groups": []}
    binm = data[keys].astype(float)
    corr = binm.corr()  # phi
    corr_disp = corr.rename(index=labels, columns=labels)

    pairs = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            phi = corr.iloc[i, j]
            if phi == phi and abs(phi) >= high_thresh:  # 非 NaN 且超門檻
                pairs.append({"因子A": labels[keys[i]], "因子B": labels[keys[j]],
                              "phi": round(float(phi), 3)})

    # union-find 連通分群
    parent = {k: k for k in keys}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            phi = corr.iloc[i, j]
            if phi == phi and abs(phi) >= high_thresh:
                parent[find(keys[i])] = find(keys[j])
    comp = {}
    for k in keys:
        comp.setdefault(find(k), []).append(k)
    lift_map = lift_map or {}
    groups = []
    for members in comp.values():
        if len(members) < 2:
            continue
        keep = max(members, key=lambda m: lift_map.get(m, 0.0))
        groups.append({
            "成員": [labels[m] for m in members],
            "建議保留": labels[keep],
            "建議合併": [labels[m] for m in members if m != keep],
        })
    return {"corr": corr_disp, "pairs": pairs, "groups": groups}
