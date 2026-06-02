import pandas as pd

from .entry import classify_entry
from .indicators import add_indicators
from .sizing import calc_position, calc_targets


def _clip(x, lo=0.0, hi=1.0):
    try:
        return max(lo, min(hi, float(x)))
    except Exception:
        return lo


def _ret_n(df, n):
    if len(df) <= n:
        return None
    past = float(df["Close"].iloc[-(n + 1)])
    if past <= 0:
        return None
    return (float(df["Close"].iloc[-1]) / past - 1) * 100


def _slope(series, n):
    """近 n 期變化（簡單斜率）。"""
    s = series.dropna()
    if len(s) <= n:
        return None
    return float(s.iloc[-1]) - float(s.iloc[-1 - n])


def _empty_result(symbol, name, market, status):
    return {
        "股票": symbol, "公司名稱": name, "市場": market,
        "狀態": status, "訊號判斷": "無法分析",
        "評分": 0, "換手率%": None, "RR比": None,
    }


def analyze_stock(symbol, company_name, market, df, shares, cfg,
                  market_state=None, current_price=None, chips=None, margin=None,
                  earnings_date=None, revenue=None):
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
    vol50 = df["Volume"].rolling(50).mean().iloc[-1]
    if pd.isna(vol50):
        vol50 = vol20

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

    # ============ 條件（連續強度 0~1，避免臨界值斷崖）============
    vol_mult = filters.get("vol_multiple", 1.5)  # 量增門檻（對 50 日均量）
    close_v = float(latest["Close"])
    vol_v = float(latest["Volume"])
    ma5 = float(latest["MA5"])
    ma20 = float(latest["MA20"])
    ma60 = float(latest["MA60"])
    k_v = float(latest["K"])
    d_v = float(latest["D"])
    osc_v = float(latest["OSC"])

    # 突破 + 量增：站上 20 日高給基礎分，幅度與量能為加分（避免臨界斷崖）
    vol_ratio = vol_v / vol50 if vol50 > 0 else 0.0
    vol_gate = _clip((vol_ratio - 1.0) / (vol_mult - 1.0)) if vol_mult > 1.0 else float(vol_ratio >= 1)
    if high_20 and close_v > high_20:
        brk_amt = 0.9 + 0.1 * _clip((close_v / high_20 - 1) / 0.03)
        s_breakout = brk_amt * (0.5 + 0.5 * vol_gate)
    else:
        s_breakout = 0.0
    cond_breakout_with_volume = bool(close_v > high_20 and vol_ratio >= vol_mult)

    # MA 多頭：三條件平均 + 斜率連續性
    s_ma = (int(ma5 > ma20) + int(ma20 > ma60) + int(close_v > ma20)) / 3.0
    cond_ma_bullish = bool(ma5 > ma20 > ma60 and close_v > ma20)

    # 換手率強勢
    if turnover_rate is not None:
        over_one = _clip((turnover_rate - 1.0) / 2.0)        # 1%→0, 3%→1
        over_avg = 1.0 if turnover_rate > avg_turnover_20 else 0.4
        s_turnover = over_one * over_avg
        cond_turnover_strong = bool(turnover_rate > 1 and turnover_rate > avg_turnover_20)
    else:
        s_turnover = 0.0
        cond_turnover_strong = False

    # KD：K 在強勢區的程度 × 黃金交叉
    s_kd_base = _clip((k_v - 55) / 20)                       # K55→0, K75→1
    s_kd = s_kd_base if k_v > d_v else s_kd_base * 0.6
    cond_kd = bool(k_v > d_v and k_v > 70)

    # MACD：OSC > 0 給基礎分，相對股價的強度為加分
    s_macd = (0.7 + 0.3 * _clip(osc_v / (close_v * 0.005))) if osc_v > 0 else 0.0
    cond_macd = bool(osc_v > 0)

    # 相對強度 RS：個股 60 日報酬 - 大盤 60 日報酬
    twii_ret = market_state.get("ret_60d") if market_state else None
    stock_ret_60 = _ret_n(df, 60)
    if twii_ret is not None and stock_ret_60 is not None:
        rs_diff = stock_ret_60 - twii_ret
        s_rs = _clip(rs_diff / 10.0)                          # 贏大盤 10% → 滿分
        cond_rel_strength = bool(rs_diff > 0)
    else:
        rs_diff = None
        s_rs = 0.0
        cond_rel_strength = False

    # 趨勢確認：ADX > 20 或 MA60 斜率 > 0
    adx_v = float(latest["ADX14"]) if pd.notna(latest.get("ADX14")) else None
    ma60_slope = _slope(df["MA60"], 5)
    adx_s = _clip((adx_v - 15) / 15) if adx_v is not None else 0.0
    slope_s = 0.6 if (ma60_slope is not None and ma60_slope > 0) else 0.0
    s_trend = max(adx_s, slope_s)
    cond_trend_confirm = bool(
        (adx_v is not None and adx_v > 20) or (ma60_slope is not None and ma60_slope > 0)
    )

    strengths = {
        "breakout_with_volume": s_breakout,
        "ma_bullish": s_ma,
        "turnover_strong": s_turnover,
        "kd": s_kd,
        "macd": s_macd,
        "rel_strength": s_rs,
        "trend_confirm": s_trend,
    }
    score_raw = sum(weights.get(k, 0) * v for k, v in strengths.items())
    score = round(score_raw)

    # ============ 進出場（ATR 停損，使風險距離一致）============
    atr_mult = filters.get("atr_mult", 1.5)
    atr_v = float(latest["ATR14"]) if pd.notna(latest.get("ATR14")) else None
    if atr_v is not None and atr_v > 0:
        stop = entry - atr_v * atr_mult
    else:
        stop = max(ma20, float(df["Low"].iloc[-10:].min()))
    # 結構防呆：停損不可高於 MA20（避免設在壓力之上）
    stop = min(stop, ma20) if stop > ma20 else stop
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

    # 三級訊號：進場 / 觀察 / 不操作
    enter_thr = thr.get("enter", thr.get("strong", 6))
    watch_thr = thr.get("watch", 5)

    if rr is None and score >= enter_thr:
        signal = "觀察"
        status = "成功（停損距離過近）"
    else:
        if score >= enter_thr:
            signal = "進場"
        elif score >= watch_thr:
            signal = "觀察"
        else:
            signal = "不操作"
        status = "成功"

    # ============ 現價偏離（追高判斷）============
    entry_ref = entry_info["entry_price"]
    if current_price is not None and entry_ref and entry_ref > 0:
        price_dev_pct = (current_price - entry_ref) / entry_ref * 100
    else:
        price_dev_pct = None

    chase_warn = None
    if price_dev_pct is not None:
        if price_dev_pct >= 5:
            chase_warn = f"現價追高 +{price_dev_pct:.1f}%"
            if signal == "進場":
                signal = "觀察"
                status = "成功（現價追高）"
        elif price_dev_pct >= 3:
            chase_warn = f"現價偏離 +{price_dev_pct:.1f}%"
        elif price_dev_pct <= -3:
            chase_warn = f"現價低於參考 {price_dev_pct:.1f}%"

    # ============ 延伸度（進場價相對 MA20 過熱）============
    strat = cfg.get("strategy", {})
    mode = strat.get("mode", "breakout")
    early_cfg = strat.get("early", {})
    # 早期模式：收緊延伸度門檻
    ext_threshold = (early_cfg.get("ext_threshold", 1.06)
                     if mode == "early" else filters.get("ext_threshold", 1.10))
    ext_ratio = (entry_ref / ma20) if (entry_ref and ma20 > 0) else None
    ext_warn = None
    if ext_ratio is not None and ext_ratio >= ext_threshold:
        ext_warn = f"乖離 MA20 +{(ext_ratio - 1) * 100:.0f}%"
        if signal == "進場":
            signal = "觀察"
            status = "成功（過度延伸）"

    # 早期模式：突破必須「新鮮」（剛突破，未漲一大段），否則視為追高降級
    if mode == "early" and entry_info["entry_type"] == "breakout" and high_20:
        above_high_pct = (entry_ref / high_20 - 1) * 100 if entry_ref else 0
        max_fresh = early_cfg.get("max_above_high20_pct", 3.0)
        if above_high_pct > max_fresh:
            ext_warn = (ext_warn + " · " if ext_warn else "") + f"非新鮮突破(+{above_high_pct:.0f}%)"
            if signal == "進場":
                signal = "觀察"
                status = "成功（非新鮮突破）"

    # ============ 籌碼面（三大法人 / 外資）確認與否決 ============
    chip_cfg = cfg.get("chips", {})
    sell_downgrade = chip_cfg.get("sell_downgrade", True)
    inst_lots = chips.get("inst_net_lots") if chips else None
    foreign_lots = chips.get("foreign_net_lots") if chips else None
    buy_streak = chips.get("inst_buy_streak") if chips else None
    net_5d = chips.get("inst_net_5d_lots") if chips else None
    chip_confirm = "—"
    chip_warn = None
    if inst_lots is not None:
        if inst_lots > 0 and (foreign_lots is None or foreign_lots >= 0):
            if buy_streak and buy_streak >= 2:
                chip_confirm = f"法人連買{buy_streak}日"
            else:
                chip_confirm = "法人買超"
        elif inst_lots > 0:
            chip_confirm = "投信買外資賣"  # 法人合計買超但外資在賣
        elif inst_lots < 0:
            chip_confirm = "法人賣超"
            chip_warn = f"法人賣超 {abs(inst_lots):,}張"
            # 進場訊號上法人卻在賣 → 出貨疑慮，降為觀察
            if sell_downgrade and signal == "進場":
                signal = "觀察"
                status = "成功（法人賣超）"

    # ============ 融資券（散戶槓桿 / 券資比）============
    mgn_cfg = cfg.get("margin", {})
    surge_thr = mgn_cfg.get("surge_pct", 10.0)        # 融資單日增幅警示門檻
    ratio_flag = mgn_cfg.get("short_ratio_flag", 20.0)  # 券資比軋空參考門檻
    surge_downgrade = mgn_cfg.get("surge_downgrade", False)
    margin_chg = margin.get("margin_chg_pct") if margin else None
    short_ratio = margin.get("short_margin_ratio") if margin else None
    margin_warn = None
    margin_flag = "—"
    if margin_chg is not None and margin_chg >= surge_thr:
        margin_warn = f"融資爆增 +{margin_chg:.0f}%"
        margin_flag = "融資爆增"
        # 散戶追高槓桿 = 反指標；可選擇把進場降為觀察
        if surge_downgrade and signal == "進場":
            signal = "觀察"
            status = "成功（融資爆增）"
    elif short_ratio is not None and short_ratio >= ratio_flag:
        margin_flag = "高券資比"

    # ============ 財報避雷（blackout）============
    from .earnings import days_to_earnings
    earn_cfg = cfg.get("earnings", {})
    pre_days = earn_cfg.get("pre_days", 3)
    post_days = earn_cfg.get("post_days", 1)
    d2e = days_to_earnings(earnings_date)
    earn_warn = None
    if d2e is not None and -post_days <= d2e <= pre_days:
        if d2e >= 0:
            earn_warn = f"財報臨近{d2e}日"
        else:
            earn_warn = f"財報剛過{-d2e}日"
        # 財報前後波動風險高，進場降為觀察
        if earn_cfg.get("blackout_downgrade", True) and signal == "進場":
            signal = "觀察"
            status = "成功（財報避雷）"

    # ============ 月營收動能（基本面催化劑）============
    from .revenue import classify_revenue
    rev_cfg = cfg.get("revenue", {})
    rev_confirm, rev_warn, rev_strong, rev_weak = classify_revenue(revenue, rev_cfg)
    if rev_weak and rev_cfg.get("downgrade_on_weak", True) and signal == "進場":
        signal = "觀察"
        status = "成功（營收衰退）"

    extra_warns = " · ".join(
        [w for w in (chase_warn, ext_warn, chip_warn, margin_warn, earn_warn, rev_warn) if w]
    )

    # ============ 綜合操作建議（簡短）============
    if market_state and market_state["regime"] == "bear":
        action = "大盤空頭 暫停"
    elif signal == "進場" and pos["suggested_lots"] == 0:
        action = "資金不足"
    elif signal == "進場" and entry_info["entry_type"] in ("breakout", "pullback", "base"):
        action = f"進場 · {entry_info['entry_label']}"
    elif signal == "進場":
        action = "進場 · 無劇本"
    elif signal == "觀察":
        action = "觀察"
    else:
        action = "不操作"

    # 評分顯示 X/Y（涵蓋所有已設權重的條件）
    max_score_total = round(sum(weights.get(k, 0) for k in strengths))
    score_display = f"{score} / {max_score_total}"

    # ============ 綜合評級（A / B / C / 避開）+ 一行理由 ============
    red_flags = [w for w in (
        (chip_warn if chip_confirm == "法人賣超" else None),
        earn_warn, ext_warn, rev_warn,
        (margin_warn if margin_flag == "融資爆增" else None),
    ) if w]
    chip_positive = chip_confirm.startswith("法人") and "賣" not in chip_confirm
    if market_state and market_state["regime"] == "bear":
        grade, reason = "避開", "大盤空頭"
    elif signal == "進場" and pos["suggested_lots"] == 0:
        grade, reason = "避開", "資金不足"
    elif signal not in ("進場", "觀察"):
        grade, reason = "避開", (red_flags[0] if red_flags else "未達訊號")
    else:
        pos_reasons = []
        if entry_info["entry_type"] in ("breakout", "pullback", "base"):
            pos_reasons.append(entry_info["entry_label"])
        if chip_positive:
            pos_reasons.append(chip_confirm)
        if cond_rel_strength:
            pos_reasons.append("RS強")
        if rev_strong:
            pos_reasons.append(rev_confirm)
        if cond_trend_confirm:
            pos_reasons.append("趨勢確認")
        rev_known = bool(revenue and revenue.get("yoy_pct") is not None)
        if (signal == "進場" and chip_positive and cond_rel_strength
                and (rev_strong or not rev_known) and not red_flags):
            grade = "A"
        elif signal == "進場":
            grade = "B"
        else:
            grade = "C"
        reason = "＋".join(pos_reasons[:3]) if pos_reasons else "訊號成立"
        if red_flags:
            reason = reason + "（注意：" + "、".join(red_flags) + "）"

    return {
        "股票": symbol, "公司名稱": company_name, "市場": market,
        "狀態": status, "訊號判斷": signal, "評分": score, "評分顯示": score_display,

        "操作建議": action,
        "綜合評級": grade,
        "評級理由": reason,
        "進場類型": entry_info["entry_label"],
        "進場條件": entry_info["entry_note"],

        "收盤價": round(entry, 2),
        "目前現價": round(current_price, 2) if current_price is not None else None,
        "現價偏離%": round(price_dev_pct, 2) if price_dev_pct is not None else None,
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
        "部位提示": " · ".join([w for w in (pos["warning"], extra_warns) if w]),
        "大盤狀態": market_label,
        "大盤確認(FTD)": bool(market_state.get("ftd_recent")) if market_state else None,

        "籌碼確認": chip_confirm,
        "法人買賣超(張)": inst_lots,
        "外資買賣超(張)": foreign_lots,
        "法人連買天數": buy_streak,
        "法人5日累計(張)": net_5d,
        "融資券提示": margin_flag,
        "融資增減%": margin_chg,
        "券資比%": short_ratio,
        "財報日": earnings_date,
        "距財報日": d2e,

        "營收動能": rev_confirm,
        "月營收YoY%": round(revenue["yoy_pct"], 1) if (revenue and revenue.get("yoy_pct") is not None) else None,
        "月營收MoM%": round(revenue["mom_pct"], 1) if (revenue and revenue.get("mom_pct") is not None) else None,
        "營收月份": revenue.get("month") if revenue else None,

        "ATR14": round(atr_v, 2) if atr_v is not None else None,
        "相對強度RS%": round(rs_diff, 2) if rs_diff is not None else None,
        "ADX": round(adx_v, 1) if adx_v is not None else None,
        "乖離MA20%": round((ext_ratio - 1) * 100, 1) if ext_ratio is not None else None,

        "MA5": round(latest["MA5"], 2),
        "MA20": round(latest["MA20"], 2),
        "MA60": round(latest["MA60"], 2),

        "K": round(latest["K"], 2),
        "D": round(latest["D"], 2),
        "OSC": round(latest["OSC"], 2),

        "20日高點": round(high_20, 2),
        "成交量": int(latest["Volume"]),
        "20日均量": int(vol20),
        "50日均量": int(vol50) if pd.notna(vol50) else None,

        "流通股數(近似)": int(shares) if shares is not None else None,
        "換手率%": round(turnover_rate, 2) if turnover_rate is not None else None,
        "20日平均換手率%": round(avg_turnover_20, 2) if avg_turnover_20 is not None else None,

        "突破+量增": cond_breakout_with_volume,
        "MA多頭": cond_ma_bullish,
        "換手率強勢": cond_turnover_strong,
        "KD強勢": cond_kd,
        "MACD多方": cond_macd,
        "相對強度": cond_rel_strength,
        "趨勢確認": cond_trend_confirm,
    }
