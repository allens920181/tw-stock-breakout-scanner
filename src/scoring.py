import pandas as pd

from .entry import classify_entry
from .indicators import add_indicators
from .sizing import calc_position, calc_targets


def _empty_result(symbol, name, market, status):
    return {
        "股票": symbol, "公司名稱": name, "市場": market,
        "狀態": status, "訊號判斷": "無法分析",
        "評分": 0, "換手率%": None, "RR比": None,
    }


def analyze_stock(symbol, company_name, market, df, shares, cfg, market_state=None):
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

    target_1r, target_2r = calc_targets(entry, stop)

    min_risk_pct = filters.get("min_risk_pct", 0)
    risk_ok = risk > 0 and risk_pct >= min_risk_pct

    if risk_ok:
        rr = 2.0  # 固定吃 2R
    else:
        rr = None

    # ============ 進場分類 ============
    entry_info = classify_entry(df, latest, high_20, vol20)

    # ============ 大盤調整 ============
    position_factor = market_state["position_factor"] if market_state else 1.0
    market_label = market_state["label"] if market_state else "⚪"

    # ============ 部位管理 ============
    ps = cfg.get("position_sizing", {})
    pos = calc_position(
        entry=entry, stop=stop,
        total_capital=ps.get("total_capital", 1_000_000),
        risk_pct=ps.get("risk_per_trade_pct", 0.01),
        position_factor=position_factor,
        lot_size=ps.get("lot_size", 1000),
        max_position_pct=ps.get("max_position_pct", 0.20),
    )

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

    # ============ 綜合操作建議 ============
    if market_state and market_state["regime"] == "bear":
        action = "⛔ 大盤空頭 暫不買入"
    elif pos["suggested_lots"] == 0:
        action = "⚠️ 不足 1 張 跳過"
    elif signal == "強勢候選" and entry_info["entry_type"] in ("breakout", "pullback", "base"):
        action = f"🟢 買入（{entry_info['entry_label']}）"
    elif signal == "強勢候選":
        action = "🟡 強勢但無明確進場點"
    elif signal == "觀察":
        action = "🟡 觀察"
    else:
        action = "🔴 不操作"

    return {
        "股票": symbol, "公司名稱": company_name, "市場": market,
        "狀態": status, "訊號判斷": signal, "評分": score,

        "操作建議": action,
        "進場類型": entry_info["entry_label"],
        "進場條件": entry_info["entry_note"],

        "收盤價": round(entry, 2),
        "進場參考價": entry_info["entry_price"],
        "停損價": round(stop, 2),
        "目標價1(+1R半倉)": target_1r,
        "目標價2(+2R出清)": target_2r,
        "風險": round(risk, 2),
        "風險%": round(risk_pct * 100, 2),
        "RR比": round(rr, 2) if rr is not None else None,

        "建議張數": pos["suggested_lots"],
        "進場成本": pos["cost"],
        "佔資金%": pos["cost_pct"],
        "部位提示": pos["warning"],
        "大盤狀態": market_label,

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
