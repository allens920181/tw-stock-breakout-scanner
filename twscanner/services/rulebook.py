"""
實證規則名單：把掃描結果（已有「距一年高點」）接上月營收驚喜，回答「現在符合規則的是哪幾檔、持股該不該換」。

規則與回測見 twscanner/analysis/revenue_surprise.py 與 docs/research/portfolio_study_2026-11.json。
"""
import pandas as pd

from twscanner.analysis.revenue_surprise import (
    BUY_HIGH_PCT,
    RULE_N,
    pick_candidates,
    revenue_surprise,
    sell_check,
)
from twscanner.data.revenue_history import fetch_many


def _code(symbol):
    return str(symbol).split(".")[0]


def _num(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def build_rulebook(scan_df, cache_dir, holding_codes=(), progress_cb=None, fetch=fetch_many):
    """
    scan_df：掃描結果（需有 股票、公司名稱、收盤價、距一年高點%）。
    回 {"candidates", "eligible", "near_high", "holdings", "missing", "month"}。
    只對「距一年高點 ≥ 90%」的股票與持股抓營收歷史，其餘不抓。
    """
    if scan_df is None or len(scan_df) == 0 or "距一年高點%" not in scan_df:
        return None
    d = scan_df.copy()
    d["_code"] = d["股票"].map(_code)
    d["_h1y"] = pd.to_numeric(d["距一年高點%"], errors="coerce")
    d = d.drop_duplicates("_code").set_index("_code")
    near = list(d.index[d["_h1y"] >= BUY_HIGH_PCT])
    held = [c for c in dict.fromkeys(map(str, holding_codes)) if c]
    hist = fetch(list(dict.fromkeys(near + held)), cache_dir, progress_cb=progress_cb)

    def row(code):
        s = revenue_surprise(hist.get(code) or [])
        in_scan = code in d.index
        return {"code": code, "name": d.at[code, "公司名稱"] if in_scan else None,
                "close": _num(d.at[code, "收盤價"]) if in_scan and "收盤價" in d else None,
                "high_1y": _num(d.at[code, "_h1y"]) if in_scan else None,
                "sur": s["sur"], "yoy_pct": s["yoy_pct"], "month": s["month"]}

    rows = [row(c) for c in near]
    picks = pick_candidates(rows, RULE_N)
    pick_codes = {r["code"] for r in picks}
    holdings = []
    for c in held:
        r = row(c)
        action, reason = sell_check(r["high_1y"], r["sur"])
        holdings.append({**r, "action": action, "reason": reason, "in_list": c in pick_codes})
    months = [r["month"] for r in rows if r["month"]]
    return {"candidates": picks, "eligible": sum(r["sur"] is not None for r in rows), "near_high": len(near),
            "holdings": holdings, "missing": [r["code"] for r in rows if r["sur"] is None],
            "month": max(months) if months else None}
