"""
今日決策（操盤視角）：把大盤、持股、候選、組合風險、月目標組成「今天要做什麼」。

純函式：只吃頁面已經有的資料（掃描結果、持股分析、交易紀錄），不抓網路，方便測試。
順序即優先序：能不能開新倉 → 持股要動的 → 候選交易計畫 → 組合風險 → 月目標。
"""
import pandas as pd

from twscanner.analysis.goal import month_progress, plan, stats_from_r
from twscanner.portfolio.risk import portfolio_risk
from twscanner.portfolio.trade_log import month_stats

CONDITION_KEYS = [  # (欄位, 白話)
    ("突破+量增", "突破近 20 日高點且放量"),
    ("MA多頭", "均線多頭排列"),
    ("換手率強勢", "換手熱絡"),
    ("KD強勢", "KD 強勢"),
    ("MACD多方", "MACD 翻多"),
    ("相對強度", "比大盤強"),
    ("趨勢確認", "趨勢確認（ADX/均線斜率）"),
]
URGENT_WORDS = ("停損", "轉弱", "了結", "全出", "時間停損", "移動停利")


def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _true(v):
    """條件欄位是否成立；None / NaN（bool(nan) 是 True！）都算不成立。"""
    return v is not None and v == v and bool(v)


def trade_plan(row, max_hold_days=20):
    """掃描結果的一列 → 交易計畫卡資料。"""
    entry, stop = _f(row.get("進場參考價")), _f(row.get("停損價"))
    t1, t2 = _f(row.get("目標價1(+1R半倉)")), _f(row.get("目標價2(+2R出清)"))
    lots = int(_f(row.get("建議張數")) or 0)
    risk_ps = entry - stop if entry and stop and entry > stop else None
    reasons = [label for key, label in CONDITION_KEYS if _true(row.get(key))]
    for key in ("籌碼確認", "營收動能"):
        v = row.get(key)
        if isinstance(v, str) and v not in ("", "—"):
            reasons.append(v)
    return {
        "code": str(row.get("股票", "")).split(".")[0], "name": row.get("公司名稱"),
        "grade": row.get("綜合評級"), "signal": row.get("訊號判斷"), "action": row.get("操作建議"),
        "score": row.get("評分顯示", row.get("評分")),
        "entry": entry, "stop": stop, "t1": t1, "t2": t2, "lots": lots,
        "risk_amount": risk_ps * lots * 1000 if risk_ps else None,
        "risk_pct": _f(row.get("風險%")),
        "cost": _f(row.get("進場成本")),
        "entry_type": row.get("進場類型"), "entry_note": row.get("進場條件"),
        "reasons": reasons, "why": row.get("評級理由"),
        "max_hold_days": max_hold_days,
        "invalidation": f"收盤跌破 {stop:,.2f} 就出場，不攤平" if stop else "依停損規則出場",
    }


def candidates(scan_df, n=5):
    """依訊號（進場 > 觀察）與分數排序，取前 n 檔做成交易計畫。"""
    if scan_df is None or len(scan_df) == 0 or "訊號判斷" not in scan_df:
        return []
    d = scan_df[scan_df["訊號判斷"].isin(["進場", "觀察"])].copy()
    if d.empty:
        return []
    d["_rank"] = d["訊號判斷"].map({"進場": 0, "觀察": 1})
    d = d.sort_values(["_rank", "評分"], ascending=[True, False])
    return [trade_plan(r) for _, r in d.head(n).iterrows()]


def holding_actions(holdings_df):
    """需要處理的持股排最前面。"""
    if holdings_df is None or len(holdings_df) == 0:
        return []
    out = []
    for _, r in holdings_df.iterrows():
        act = str(r.get("操作建議", ""))
        qty = str(r.get("賣出量", ""))
        urgent = qty in ("全出", "賣半") or any(w in act for w in URGENT_WORDS)
        out.append({"code": str(r.get("股票", "")).split(".")[0], "name": r.get("公司名稱"),
                    "action": act, "qty": qty, "note": r.get("說明"), "urgent": urgent,
                    "r": _f(r.get("R倍數")), "pnl_pct": _f(r.get("報酬%")),
                    "price": _f(r.get("目前價")), "stop": _f(r.get("停損價")),
                    "entry_source": r.get("進場日來源")})
    return sorted(out, key=lambda x: (not x["urgent"], x["code"]))


def goal_stats(backtest=None, trades_computed=None):
    """實戰紀錄 ≥ 10 筆優先，否則用回測。"""
    live = None
    if trades_computed is not None and "R倍數" in getattr(trades_computed, "columns", []):
        live = stats_from_r(pd.to_numeric(trades_computed["R倍數"], errors="coerce").tolist(), "實戰紀錄")
    if live and live["n"] >= 10:
        return live
    if backtest and backtest.get("trades") is not None and len(backtest["trades"]):
        bt = stats_from_r(backtest["trades"]["r_multiple"].tolist(), "回測")
        if bt:
            return bt
    return live


def build_today(market_state, scan_df, holdings_df, trades_computed, cfg, month,
                target=10_000, loss_limit_r=2.0, max_risk_pct=5.0, max_positions=5,
                backtest=None, sector_map=None, top_n=5):
    ps = cfg.get("position_sizing", {})
    capital = ps.get("total_capital", 1_000_000)
    risk_pct = ps.get("risk_per_trade_pct", 0.01)

    realized, r_sum, prev = month_stats(trades_computed, month) if trades_computed is not None \
        else (0.0, 0.0, [])
    stats = goal_stats(backtest, trades_computed)
    g_plan = plan(capital, risk_pct, target, stats, loss_limit_r=loss_limit_r)
    prog = month_progress(realized, r_sum, target, loss_limit_r=loss_limit_r, history=prev)
    risk = portfolio_risk(holdings_df, capital, max_risk_pct=max_risk_pct,
                          max_positions=max_positions, sector_map=sector_map)

    reasons = []
    regime = (market_state or {}).get("regime")
    if regime == "bear":
        reasons.append("台股大盤空頭：策略只做多，空頭時休息是最好的操作。")
    elif regime in (None, "unknown"):
        reasons.append("還不知道今天的大盤狀態（資料暫時抓不到）：確認大盤前先不開新倉。")
    if prog["stop_trading"]:
        reasons.append(f"本月已達虧損上限 {loss_limit_r:.0f}R。")
    if risk["risk_pct"] is not None and risk["risk_pct"] > max_risk_pct:
        reasons.append(f"組合風險 {risk['risk_pct']:.1f}% 已超過 {max_risk_pct:.0f}%。")
    if risk["positions"] >= max_positions:
        reasons.append(f"已持有 {risk['positions']} 檔，達上限。")
    can_open = not reasons
    cands = candidates(scan_df, n=top_n)
    acts = holding_actions(holdings_df)
    urgent = [a for a in acts if a["urgent"]]

    if not can_open:
        headline = "今天不開新倉" + ("，先處理持股" if urgent else "") + "。"
    elif scan_df is None:
        headline = "可以開新倉，但今天還沒掃描：先跑一次「找標的」。"
    elif not any(c["signal"] == "進場" for c in cands):
        headline = "可以開新倉，但今天沒有達到進場標準的股票，耐心等待。"
    else:
        n_go = sum(1 for c in cands if c["signal"] == "進場")
        headline = f"可以開新倉：{n_go} 檔達進場標準，挑 1–2 檔就好。"
    if urgent:
        headline += f" 持股有 {len(urgent)} 檔需要處理。"

    return {"can_open": can_open, "reasons": reasons, "headline": headline,
            "regime": regime, "candidates": cands, "actions": acts, "urgent": urgent,
            "risk": risk, "plan": g_plan, "progress": prog, "stats": stats,
            "target": target, "capital": capital}
