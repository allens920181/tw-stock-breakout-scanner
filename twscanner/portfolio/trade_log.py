"""
已實現交易紀錄（賣出後記一筆）：算損益、R 倍數、持有天數與每月彙總。

欄位：賣出日 | 股票代號 | 公司名稱 | 買進日 | 買進價 | 賣出價 | 股數 | 停損價(可空) | 備註
成本：手續費（雙邊，最低 20 元，未滿 1 元不計）× 折扣 + 證交稅（賣出時，未滿 1 元不計）。費率取自 config 的 costs。
"""
import math

import pandas as pd

from twscanner.analysis.goal import stats_from_r

COLUMNS = ["賣出日", "股票代號", "公司名稱", "買進日", "買進價", "賣出價", "股數", "停損價", "備註"]
MIN_FEE = 20


def empty():
    return pd.DataFrame(columns=COLUMNS).astype({"股票代號": str})


def _fee(amount, costs):
    rate = costs.get("fee_rate", 0.001425) * costs.get("fee_discount", 1.0)
    return max(MIN_FEE, math.floor(amount * rate)) if amount > 0 else 0   # 未滿 1 元不計


def trade_pnl(buy, sell, shares, costs=None, stop=None):
    """回 {pnl, pnl_pct, r_multiple, fees}。r_multiple 需停損價（風險 = 買進價 − 停損價）。"""
    costs = costs or {}
    buy_amt, sell_amt = buy * shares, sell * shares
    fees = _fee(buy_amt, costs) + _fee(sell_amt, costs) + math.floor(sell_amt * costs.get("tax_rate", 0.003))
    pnl = sell_amt - buy_amt - fees
    r = None
    if stop is not None and buy > stop:
        r = pnl / ((buy - stop) * shares)
    return {"pnl": pnl, "pnl_pct": pnl / buy_amt * 100 if buy_amt else None,
            "r_multiple": r, "fees": fees}


def compute(df, costs=None):
    """加上 損益(元)、報酬%、R倍數、持有天數；資料不完整的列略過計算。"""
    if df is None or df.empty:
        return empty()
    out = df.copy()
    for c in COLUMNS:
        if c not in out.columns:
            out[c] = None
    pnl, pct, rr, days = [], [], [], []
    for _, row in out.iterrows():
        try:
            buy, sell, sh = float(row["買進價"]), float(row["賣出價"]), int(row["股數"])
            stop = float(row["停損價"]) if pd.notna(row.get("停損價")) and row.get("停損價") != "" else None
            res = trade_pnl(buy, sell, sh, costs, stop)
            pnl.append(res["pnl"])
            pct.append(res["pnl_pct"])
            rr.append(res["r_multiple"])
        except Exception:
            pnl.append(None)
            pct.append(None)
            rr.append(None)
        try:
            days.append((pd.to_datetime(row["賣出日"]) - pd.to_datetime(row["買進日"])).days)
        except Exception:
            days.append(None)
    out["損益(元)"] = pnl
    out["報酬%"] = pct
    out["R倍數"] = rr
    out["持有天數"] = days
    return out


def monthly_summary(computed):
    """每月：筆數、勝率、已實現損益、R 總和。依月份新→舊。"""
    cols = ["月份", "筆數", "勝率%", "已實現損益", "R總和"]
    if computed is None or computed.empty or "損益(元)" not in computed:
        return pd.DataFrame(columns=cols)
    d = computed.dropna(subset=["損益(元)"]).copy()
    if d.empty:
        return pd.DataFrame(columns=cols)
    d["月份"] = pd.to_datetime(d["賣出日"], errors="coerce").dt.strftime("%Y-%m")
    d = d.dropna(subset=["月份"])
    g = d.groupby("月份")
    out = pd.DataFrame({
        "筆數": g.size(),
        "勝率%": g["損益(元)"].apply(lambda s: (s > 0).mean() * 100),
        "已實現損益": g["損益(元)"].sum(),
        "R總和": g["R倍數"].apply(lambda s: s.dropna().sum() if s.notna().any() else None),
    }).reset_index()
    return out.sort_values("月份", ascending=False).reset_index(drop=True)


def month_stats(computed, month):
    """指定月份（YYYY-MM）的已實現損益與 R 總和，以及之前月份的損益（新→舊）。"""
    summ = monthly_summary(computed)
    cur = summ[summ["月份"] == month]
    realized = float(cur["已實現損益"].iloc[0]) if len(cur) else 0.0
    r_sum = cur["R總和"].iloc[0] if len(cur) else 0.0
    r_sum = float(r_sum) if r_sum is not None and pd.notna(r_sum) else 0.0
    prev = summ[summ["月份"] < month]["已實現損益"].tolist()
    return realized, r_sum, prev


def stats_for_goal(computed):
    """從實戰紀錄算勝率 / 平均賺 R / 期望值（需有停損價才有 R）。"""
    if computed is None or computed.empty or "R倍數" not in computed:
        return None
    return stats_from_r(pd.to_numeric(computed["R倍數"], errors="coerce").dropna().tolist(), "實戰紀錄")
