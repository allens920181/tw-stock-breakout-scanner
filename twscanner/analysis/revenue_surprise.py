"""
實證規則：距一年高點 + 月營收驚喜（研究：docs/research/portfolio_study_2026-11.json）。

純計算，不抓網路。回測（2005–2026、1,034 檔、扣成本）：每月營收公布後，在距一年高點 ≥ 90% 的股票裡
買營收驚喜最高的 20 檔，全期年化報酬高於 0050 與可交易股平均；停損與大盤擇時都沒有加分（停利沒有測）。
這是一籃子股票的統計優勢，單一檔仍可能賠錢。
"""
from statistics import mean, pstdev

RULE_N = 20                 # 持股檔數
BUY_HIGH_PCT = 90.0         # 買進：距一年高點 ≥ 90%
KEEP_HIGH_PCT = 80.0        # 續抱：距一年高點 ≥ 80%
KEEP_SURPRISE = 0.0         # 續抱：營收驚喜 ≥ 0（約等於回測用的「可交易股中位數」）
CHECK_DAY = 13              # 每月 10 日前公布營收；13 日後第一個交易日檢查
MIN_HISTORY = 8             # 至少要有前 8 個月的年增率才算得出驚喜


def revenue_surprise(revenues):
    """
    revenues：[(月份 'YYYY-MM', 營收)]，由舊到新、逐月。
    回 {"sur", "yoy_pct", "month"}：sur = (最新月年增率 − 前 12 個月年增率平均) ÷ 前 12 個月年增率標準差。
    資料不足或標準差為 0 時 sur 為 None。
    """
    by_month = {m: float(v) for m, v in revenues if v is not None and float(v) > 0}
    months = sorted(by_month)
    if not months:
        return {"sur": None, "yoy_pct": None, "month": None}

    def prev_year(m):
        return f"{int(m[:4]) - 1}{m[4:]}"

    yoy = {m: by_month[m] / by_month[prev_year(m)] - 1 for m in months if prev_year(m) in by_month}
    last = months[-1]
    if last not in yoy:
        return {"sur": None, "yoy_pct": None, "month": last}
    past = [yoy[m] for m in months[:-1] if m in yoy][-12:]
    sur = None
    if len(past) >= MIN_HISTORY:
        sd = pstdev(past) * (len(past) / (len(past) - 1)) ** 0.5          # 樣本標準差
        if sd > 0:
            sur = round((yoy[last] - mean(past)) / sd, 2)
    return {"sur": sur, "yoy_pct": round(yoy[last] * 100, 1), "month": last}


def pick_candidates(rows, n=RULE_N):
    """rows：[{code, name, close, high_1y, sur, yoy_pct}]。回買進名單：近高且有營收驚喜值，依驚喜由高到低取前 n 檔。"""
    ok = [r for r in rows if r.get("sur") is not None and (r.get("high_1y") or 0) >= BUY_HIGH_PCT]
    return sorted(ok, key=lambda r: -r["sur"])[:n]


def sell_check(high_1y, sur):
    """持股每月檢查：回 (動作, 理由)。動作：續抱 / 賣出 / 資料不足。"""
    if high_1y is None or high_1y != high_1y:
        return "資料不足", "沒有一年高點資料"
    if high_1y < KEEP_HIGH_PCT:
        return "賣出", f"距一年高點 {high_1y:.0f}%，低於 {KEEP_HIGH_PCT:.0f}%"
    if sur is None:
        return "資料不足", "營收資料不足，無法計算營收驚喜"
    if sur < KEEP_SURPRISE:
        return "賣出", f"營收驚喜 {sur:+.2f}，轉為負值"
    return "續抱", f"距一年高點 {high_1y:.0f}%、營收驚喜 {sur:+.2f}"
