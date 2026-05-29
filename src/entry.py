"""進場類型分類：突破 / 拉回 / 區間"""


def classify_entry(df, latest, high_20, vol20):
    """
    回傳 dict:
      entry_type: 'breakout' / 'pullback' / 'base' / 'none'
      entry_label: 中文標籤
      entry_price: 建議進場價
      entry_note: 進場條件說明
    """
    close = float(latest["Close"])
    high = float(latest["High"])
    low = float(latest["Low"])
    vol = float(latest["Volume"])
    ma5 = float(latest["MA5"])
    ma10 = float(df["Close"].rolling(10).mean().iloc[-1])
    ma20 = float(latest["MA20"])

    # ---- 突破買入 ----
    rng = max(high - low, 1e-9)
    close_in_top = (close - low) / rng >= 0.7  # 收盤在當日 70% 以上
    big_volume = vol >= vol20 * 1.5
    if close > high_20 and big_volume and close_in_top:
        return {
            "entry_type": "breakout",
            "entry_label": "突破",
            "entry_price": round(close, 2),
            "entry_note": f"當日收盤 {close:.2f} > 20日高 {high_20:.2f}，量 {vol/vol20:.1f}×均量",
        }

    # ---- 拉回買入 ----
    # 條件：先前已突破 (過去 20 日內有收盤 > 20日高紀錄) + 目前回測 MA10 或 MA20
    past_20 = df.iloc[-20:]
    past_high_20 = df["High"].iloc[-41:-21].max() if len(df) >= 41 else past_20["High"].max()
    had_breakout = (past_20["Close"] > past_high_20).any()

    near_ma10 = abs(close - ma10) / max(ma10, 1e-9) < 0.03
    near_ma20 = abs(close - ma20) / max(ma20, 1e-9) < 0.03
    above_ma20 = close > ma20

    if had_breakout and above_ma20 and (near_ma10 or near_ma20):
        anchor = ma10 if near_ma10 else ma20
        return {
            "entry_type": "pullback",
            "entry_label": "拉回",
            "entry_price": round(anchor * 1.01, 2),
            "entry_note": f"曾突破後回測 MA{10 if near_ma10 else 20}={anchor:.2f}，掛 +1% 限價",
        }

    # ---- 區間突破 ----
    # 過去 20 日 std/mean < 3% 視為窄幅整理
    last_20_close = df["Close"].iloc[-21:-1]
    if len(last_20_close) >= 20:
        mean_c = last_20_close.mean()
        std_c = last_20_close.std()
        upper = last_20_close.max()
        if mean_c > 0 and std_c / mean_c < 0.03 and close > upper:
            return {
                "entry_type": "base",
                "entry_label": "區間突破",
                "entry_price": round(close, 2),
                "entry_note": f"20日窄幅整理（std/mean={std_c/mean_c*100:.1f}%）突破上緣 {upper:.2f}",
            }

    return {
        "entry_type": "none",
        "entry_label": "—",
        "entry_price": round(close, 2),
        "entry_note": "未符合明確進場劇本",
    }
