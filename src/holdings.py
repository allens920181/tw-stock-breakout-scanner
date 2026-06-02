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


def _holding_alerts(chips, revenue, market_state):
    """持股期間主動警示：籌碼翻空 / 營收變臉 / 大盤·大資金轉空。回 list[str]。"""
    alerts = []
    if chips:
        inst = chips.get("inst_net_lots")
        foreign = chips.get("foreign_net_lots")
        if inst is not None and inst < 0:
            alerts.append(f"法人轉賣超{abs(inst):,}張")
        elif foreign is not None and foreign < 0:
            alerts.append(f"外資轉賣{abs(foreign):,}張")
    if revenue and revenue.get("yoy_pct") is not None and revenue["yoy_pct"] <= -20:
        alerts.append(f"營收年減{abs(revenue['yoy_pct']):.0f}%")
    if market_state:
        if market_state.get("regime") == "bear":
            alerts.append("大盤轉空")
        big = market_state.get("big_state")
        if big and big.get("position_factor", 1.0) <= 0.5:
            alerts.append("大資金轉空")
    return alerts


def analyze_holding(symbol, name, market, df, entry_price, entry_date, shares=None,
                    time_stop_days=10, profit_taking_at_1r=True,
                    atr_trail_mult=3.0, chips=None, revenue=None, market_state=None):
    """
    產生持股賣出建議。
    atr_trail_mult: Chandelier 移動停利 = 進場後最高價 - ATR14 × 此倍數
    chips/revenue/market_state: 持股期間主動示警（籌碼翻空/營收變臉/大盤轉空）
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
    atr = float(latest["ATR14"]) if "ATR14" in df.columns and pd.notna(latest.get("ATR14")) else None

    # ===== 計算與進場日相關的指標 =====
    held_days = None
    highest_since_entry = float(df["High"].max())
    if entry_date is not None:
        try:
            df_after = df[df.index.date >= entry_date]
            held_days = len(df_after)
            if len(df_after):
                highest_since_entry = float(df_after["High"].max())
        except Exception:
            held_days = None

    # ===== Chandelier ATR 移動停利（與進場 ATR 框架一致）=====
    chandelier = None
    if atr is not None and atr > 0:
        chandelier = highest_since_entry - atr * atr_trail_mult

    profit = close - entry_price
    profit_pct = profit / entry_price * 100 if entry_price > 0 else 0

    # 1R / 2R 估算（以進場價到 MA20 之距離視為 risk）
    estimated_stop = max(ma20, float(df["Low"].iloc[-10:].min()))
    risk = entry_price - estimated_stop if entry_price > estimated_stop else 0
    r_multiple = profit / risk if risk > 0 else None

    # ===== 出場規則 =====
    # 優先順序：停損 > 技術轉弱 > +2R > +1R > 移動停利(ATR) > 時間停損 > 移動停利(MA10) > 保留
    # 移動停利排在時間停損之前：獲利部位跌破波段高就鎖利，不應被時間停損誤判
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

    # 5. 移動停利（ATR Chandelier）：獲利中跌破「波段高 - ATR×倍數」
    elif chandelier is not None and profit_pct > 0 and close < chandelier:
        actions.append(("🟡 移動停利(ATR)", "全出",
                        f"跌破 Chandelier={chandelier:.2f}"
                        f"（波段高 {highest_since_entry:.2f} - {atr_trail_mult:.0f}×ATR）鎖利 {profit_pct:.1f}%"))

    # 6. 時間停損：持有 N 日仍 < 1R
    elif held_days is not None and held_days >= time_stop_days and (r_multiple is None or r_multiple < 1):
        actions.append(("⌛ 時間停損", "全出",
                        f"持有 {held_days} 日仍未達 +1R（{profit_pct:.1f}%）"))

    # 7. 移動停利（MA10）：較緊的備援，曾獲利後跌破 MA10
    elif close < ma10 and profit_pct > 5:
        actions.append(("🟡 移動停利", "全出", f"跌破 MA10={ma10:.2f} 鎖利 {profit_pct:.1f}%"))

    # 8. 保留
    else:
        actions.append(("✅ 續抱", "保留", f"未觸發出場條件 報酬 {profit_pct:.1f}%"))

    # ===== 出場策略階梯（無論觸發與否，都計算給使用者參考）=====
    target_1r = round(entry_price + risk, 2) if risk > 0 else None
    target_2r = round(entry_price + 2 * risk, 2) if risk > 0 else None
    trail_stop = round(ma10, 2)  # 移動停利線：MA10
    if entry_date is not None:
        try:
            from datetime import timedelta
            # 10 個交易日 ≈ 14 自然日
            time_stop_dt = entry_date + timedelta(days=14)
            time_stop_str = time_stop_dt.strftime("%Y-%m-%d")
        except Exception:
            time_stop_str = None
    else:
        time_stop_str = None

    exit_plan = {
        "停損價": round(estimated_stop, 2),
        "目標1(+1R半倉)": target_1r,
        "目標2(+2R出清)": target_2r,
        "移動停利MA10": trail_stop,
        "移動停利(ATR)": round(chandelier, 2) if chandelier is not None else None,
        "時間停損日": time_stop_str,
        "技術轉弱觸發": f"K<D 且 收盤<MA20({ma20:.2f})",
    }

    label, qty, note = actions[0]

    # ===== 持股期間主動警示（籌碼翻空 / 營收變臉 / 大盤·大資金轉空）=====
    alerts = _holding_alerts(chips, revenue, market_state)
    alert_str = " · ".join(alerts) if alerts else "—"
    # 若目前判定「續抱」但出現警示 → 升級為「留意減碼」（讓利潤奔跑也要設防）
    if alerts and label.startswith("✅ 續抱"):
        label = "⚠ 續抱·留意減碼"
        note = note + f"（警示：{alert_str}）"

    row = _row(symbol, name, market, entry_price, entry_date, shares,
               close, profit_pct, r_multiple, held_days, "成功", label, note, qty,
               exit_plan=exit_plan)
    row["主動警示"] = alert_str
    return row


def _row(symbol, name, market, entry_price, entry_date, shares,
         close, profit_pct, r_mult, held_days, status, action, note, qty="—",
         exit_plan=None):
    base = {
        "股票": symbol,
        "公司名稱": name,
        "市場": market,
        "進場日": str(entry_date) if entry_date else None,
        "持有天數": held_days,
        "成本價": entry_price,
        "目前價": round(close, 2) if close is not None else None,
        "報酬%": round(profit_pct, 2) if profit_pct is not None else None,
        "R倍數": round(r_mult, 2) if r_mult is not None else None,
        "持有股數": shares,
        "操作建議": action,
        "賣出量": qty,
        "說明": note,
        "狀態": status,
    }
    if exit_plan:
        base.update(exit_plan)
    return base
