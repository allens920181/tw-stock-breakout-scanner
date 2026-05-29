"""
持股管理：對持有部位產生賣出建議

holdings.xlsx 欄位：
  股票代號 | 公司名稱(可空) | 進場價 | 進場日(YYYY-MM-DD) | 持有股數(可空)
"""
import logging
from datetime import datetime

import pandas as pd

from .fetcher import fix_stock_code
from .indicators import add_indicators

log = logging.getLogger(__name__)


def load_holdings(file_path, etf_fix_map):
    df = pd.read_excel(file_path)
    items = []
    for _, row in df.iterrows():
        code = fix_stock_code(row["股票代號"], etf_fix_map)
        if code is None:
            continue
        try:
            entry_price = float(row["進場價"])
        except Exception:
            continue
        entry_date = row["進場日"]
        if isinstance(entry_date, pd.Timestamp):
            entry_date = entry_date.date()
        elif isinstance(entry_date, str):
            try:
                entry_date = pd.to_datetime(entry_date).date()
            except Exception:
                entry_date = None
        # 支援新欄名「持有股數」與舊欄名「持有張數」（張數 × 1000 = 股數）
        shares_val = None
        if "持有股數" in row and pd.notna(row.get("持有股數")):
            shares_val = int(row["持有股數"])
        elif "持有張數" in row and pd.notna(row.get("持有張數")):
            shares_val = int(row["持有張數"]) * 1000
        items.append({
            "code": code,
            "company_name": str(row.get("公司名稱", "")).strip(),
            "entry_price": entry_price,
            "entry_date": entry_date,
            "shares": shares_val,
        })
    return items


def analyze_holding(symbol, name, market, df, entry_price, entry_date, shares=None,
                    time_stop_days=10, profit_taking_at_1r=True):
    """
    產生持股賣出建議。
    """
    if df is None or df.empty or len(df) < 60:
        return _row(symbol, name, market, entry_price, entry_date, shares,
                    None, None, None, None, "資料不足", "保留", "")

    df = add_indicators(df).dropna()
    if len(df) < 5:
        return _row(symbol, name, market, entry_price, entry_date, shares,
                    None, None, None, None, "指標資料不足", "保留", "")

    latest = df.iloc[-1]
    close = float(latest["Close"])
    ma10 = float(df["Close"].rolling(10).mean().iloc[-1])
    ma20 = float(latest["MA20"])
    k = float(latest["K"])
    d = float(latest["D"])

    # ===== 計算與進場日相關的指標 =====
    held_days = None
    if entry_date is not None:
        try:
            df_after = df[df.index.date >= entry_date]
            held_days = len(df_after)
        except Exception:
            held_days = None

    profit = close - entry_price
    profit_pct = profit / entry_price * 100 if entry_price > 0 else 0

    # 1R / 2R 估算（以進場價到 MA20 之距離視為 risk）
    estimated_stop = max(ma20, float(df["Low"].iloc[-10:].min()))
    risk = entry_price - estimated_stop if entry_price > estimated_stop else 0
    r_multiple = profit / risk if risk > 0 else None

    # ===== 出場規則 =====
    # 規則優先順序：停損 > 技術轉弱 > 目標達成 > 時間停損 > 移動停利 > 保留
    actions = []

    # 1. 停損：跌破 MA20 且跌破近期 swing low
    swing_low = float(df["Low"].iloc[-10:].min())
    if close < ma20 and close < swing_low * 1.01:
        actions.append(("⛔ 停損出清", "全出", "跌破 MA20 + 近期低點"))

    # 2. 技術轉弱
    elif k < d and k > 50 and close < ma20:
        actions.append(("🔴 技術轉弱", "全出", f"KD 死叉 (K={k:.1f}<D={d:.1f}) + 跌破 MA20"))

    # 3. 目標達成（+2R）
    elif r_multiple is not None and r_multiple >= 2:
        actions.append(("🟢 達 +2R 出清", "全出", f"+{r_multiple:.1f}R 報酬 {profit_pct:.1f}%"))

    # 4. +1R 半倉
    elif r_multiple is not None and r_multiple >= 1 and profit_taking_at_1r:
        actions.append(("🟢 達 +1R 半倉鎖利", "賣半", f"+{r_multiple:.1f}R 報酬 {profit_pct:.1f}%"))

    # 5. 時間停損：持有 N 日仍 < 1R
    elif held_days is not None and held_days >= time_stop_days and (r_multiple is None or r_multiple < 1):
        actions.append(("⌛ 時間停損", "全出",
                        f"持有 {held_days} 日仍未達 +1R（{profit_pct:.1f}%）"))

    # 6. 移動停利：曾達 +1R 後跌破 MA10
    elif close < ma10 and profit_pct > 5:
        actions.append(("🟡 移動停利", "全出", f"跌破 MA10={ma10:.2f} 鎖利 {profit_pct:.1f}%"))

    # 7. 保留
    else:
        actions.append(("✅ 續抱", "保留", f"未觸發出場條件 報酬 {profit_pct:.1f}%"))

    label, qty, note = actions[0]
    return _row(symbol, name, market, entry_price, entry_date, shares,
                close, profit_pct, r_multiple, held_days, "成功", label, note, qty)


def _row(symbol, name, market, entry_price, entry_date, shares,
         close, profit_pct, r_mult, held_days, status, action, note, qty="—"):
    return {
        "股票": symbol,
        "公司名稱": name,
        "市場": market,
        "進場日": str(entry_date) if entry_date else None,
        "持有天數": held_days,
        "進場價": entry_price,
        "目前價": round(close, 2) if close is not None else None,
        "報酬%": round(profit_pct, 2) if profit_pct is not None else None,
        "R倍數": round(r_mult, 2) if r_mult is not None else None,
        "持有股數": shares,
        "操作建議": action,
        "賣出量": qty,
        "說明": note,
        "狀態": status,
    }
