import pandas as pd

from .indicators import add_indicators


def _empty_result(symbol, name, market, status):
    return {
        "股票": symbol, "公司名稱": name, "市場": market,
        "狀態": status, "訊號判斷": "無法分析",
        "評分": 0, "換手率%": None, "RR比": None,
    }


def analyze_stock(symbol, company_name, market, df, shares, cfg):
    """
    依 config 進行品質過濾 + 加權評分。
    回傳 dict（一筆結果）。
    """
    filters = cfg["filters"]
    weights = cfg["scoring"]["weights"]
    thr = cfg["scoring"]["thresholds"]

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if df.empty or len(df) < 80:
        return _empty_result(symbol, company_name, market, "資料不足")

    df = add_indicators(df).dropna()
    if len(df) < 30:
        return _empty_result(symbol, company_name, market, "指標資料不足")

    latest = df.iloc[-1]
    high_20 = df["High"].iloc[-21:-1].max()
    vol20 = df["Volume"].rolling(20).mean().iloc[-1]

    entry = float(latest["Close"])

    # ============ 品質前置過濾 ============
    if entry < filters["min_price"]:
        return _empty_result(symbol, company_name, market, f"股價<{filters['min_price']}")
    if vol20 < filters["min_avg_volume"]:
        return _empty_result(symbol, company_name, market, "流動性不足")
    if filters.get("require_above_ma60", False) and latest["Close"] <= latest["MA60"]:
        return _empty_result(symbol, company_name, market, "未站上MA60")

    # ============ 換手率 ============
    if shares is not None and shares > 0:
        turnover_rate = latest["Volume"] / shares * 100
        avg_turnover_20 = vol20 / shares * 100
    else:
        turnover_rate = None
        avg_turnover_20 = None

    # ============ 條件 ============
    breakout = latest["Close"] > high_20
    vol_ok = latest["Volume"] > vol20 * 1.2
    cond_breakout_with_volume = bool(breakout and vol_ok)

    cond_ma_bullish = bool(
        latest["MA5"] > latest["MA20"] > latest["MA60"]
        and latest["Close"] > latest["MA20"]
    )

    if turnover_rate is not None:
        cond_turnover_strong = bool(turnover_rate > 1 and turnover_rate > avg_turnover_20)
    else:
        cond_turnover_strong = False

    cond_kd = bool(latest["K"] > latest["D"] and latest["K"] > 70)
    cond_macd = bool(latest["OSC"] > 0)

    score = (
        weights["breakout_with_volume"] * cond_breakout_with_volume
        + weights["ma_bullish"] * cond_ma_bullish
        + weights["turnover_strong"] * cond_turnover_strong
        + weights["kd"] * cond_kd
        + weights["macd"] * cond_macd
    )

    # ============ 進出場 ============
    stop = max(float(latest["MA20"]), float(df["Low"].iloc[-10:].min()))
    risk = entry - stop
    risk_pct = risk / entry if entry > 0 else 0

    min_risk_pct = filters.get("min_risk_pct", 0)
    if risk > 0 and risk_pct >= min_risk_pct:
        target = entry + 2 * risk
        rr = (target - entry) / risk
    else:
        target = None
        rr = None

    # 停損距離不合理 → 訊號降級為觀察
    if rr is None and score >= thr["strong"]:
        signal = "觀察"
        status = "成功（停損距離過近）"
    else:
        if score >= thr["strong"]:
            signal = "強勢候選"
        elif score >= thr["watch"]:
            signal = "觀察"
        elif score >= thr["weak"]:
            signal = "偏弱觀察"
        else:
            signal = "不符合"
        status = "成功"

    return {
        "股票": symbol, "公司名稱": company_name, "市場": market,
        "狀態": status, "訊號判斷": signal, "評分": score,

        "收盤價": round(entry, 2),
        "進場參考價": round(entry, 2),
        "停損價": round(stop, 2),
        "目標價": round(target, 2) if target is not None else None,
        "風險": round(risk, 2),
        "風險%": round(risk_pct * 100, 2),
        "RR比": round(rr, 2) if rr is not None else None,

        "MA5": round(latest["MA5"], 2),
        "MA20": round(latest["MA20"], 2),
        "MA60": round(latest["MA60"], 2),

        "K": round(latest["K"], 2),
        "D": round(latest["D"], 2),
        "OSC": round(latest["OSC"], 2),

        "20日高點": round(high_20, 2),
        "成交量": int(latest["Volume"]),
        "20日均量": int(vol20),

        "流通股數(近似)": int(shares) if shares is not None else None,
        "換手率%": round(turnover_rate, 2) if turnover_rate is not None else None,
        "20日平均換手率%": round(avg_turnover_20, 2) if avg_turnover_20 is not None else None,

        "突破+量增": cond_breakout_with_volume,
        "MA多頭": cond_ma_bullish,
        "換手率強勢": cond_turnover_strong,
        "KD強勢": cond_kd,
        "MACD多方": cond_macd,
    }
