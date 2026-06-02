# -*- coding: utf-8 -*-
"""
潛伏模式（起漲前埋伏）：抓「還沒噴出」的標的，與強勢突破相反。

選股邏輯（蓄勢待發）：
  - 窄幅整理（近 20 日 std/mean 低）= 籌碼沉澱
  - 量縮（近 5 日均量 < 20 日均量）= 賣壓枯竭、蓄勢
  - 站穩 MA20 但乖離不大 = 守住支撐又不過熱
  - 接近 20 日高但「尚未突破」= 在邊緣等發動
  - KD 在中位（40~70）且 K>D = 有上漲空間、剛轉強
  - 法人默默吸籌（三大法人買超）= 大戶低檔布局

輸出與 scoring.analyze_stock 相容（同欄位），可共用前端卡片/表格/部位/籌碼否決。
"""
import pandas as pd

from .earnings import days_to_earnings
from .indicators import add_indicators
from .sizing import calc_position, calc_targets


def _empty(symbol, name, market, status):
    return {
        "股票": symbol, "公司名稱": name, "市場": market,
        "狀態": status, "訊號判斷": "無法分析",
        "評分": 0, "換手率%": None, "RR比": None,
    }


def analyze_ambush(symbol, company_name, market, df, shares, cfg,
                   market_state=None, current_price=None, chips=None,
                   margin=None, earnings_date=None, revenue=None):
    filters = cfg["filters"]
    amb = cfg.get("strategy", {}).get("ambush", {})

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.empty or len(df) < 80:
        return _empty(symbol, company_name, market, "資料不足")
    df = add_indicators(df).dropna()
    if len(df) < 30:
        return _empty(symbol, company_name, market, "指標資料不足")

    latest = df.iloc[-1]
    close = float(latest["Close"])
    ma20 = float(latest["MA20"])
    ma60 = float(latest["MA60"])
    k_v, d_v = float(latest["K"]), float(latest["D"])
    high_20 = float(df["High"].iloc[-21:-1].max())
    low_20 = float(df["Low"].iloc[-21:-1].min())
    vol20 = float(df["Volume"].rolling(20).mean().iloc[-1])
    vol5 = float(df["Volume"].iloc[-5:].mean())

    if close < filters["min_price"]:
        return _empty(symbol, company_name, market, f"股價<{filters['min_price']}")
    if vol20 < filters["min_avg_volume"]:
        return _empty(symbol, company_name, market, "流動性不足")

    # 換手率
    if shares and shares > 0:
        turnover_rate = latest["Volume"] / shares * 100
        avg_turnover_20 = vol20 / shares * 100
    else:
        turnover_rate = avg_turnover_20 = None

    # ===== 潛伏條件（蓄勢彈簧）=====
    def _clip(x, lo=0.0, hi=1.0):
        return max(lo, min(hi, float(x)))

    last20 = df["Close"].iloc[-21:-1]
    mean_c, std_c = float(last20.mean()), float(last20.std())
    base_vol = std_c / mean_c if mean_c > 0 else 1.0
    cond_base = base_vol <= amb.get("base_max_volatility", 0.05)

    cond_vol_dry = vol5 < vol20 * amb.get("vol_contraction", 0.85)

    # 波動「收斂中」：近 10 日區間 < 前 10 日區間（彈簧越壓越緊 = 越接近爆發）
    recent_rng = float(df["High"].iloc[-10:].max() - df["Low"].iloc[-10:].min())
    prior_rng = float(df["High"].iloc[-20:-10].max() - df["Low"].iloc[-20:-10].min())
    squeeze_ratio = recent_rng / prior_rng if prior_rng > 0 else 1.0
    cond_squeeze = squeeze_ratio < amb.get("squeeze_ratio", 0.9)

    above_ma20_pct = (close / ma20 - 1) * 100 if ma20 > 0 else 99
    cond_hold = close > ma20 and above_ma20_pct <= amb.get("max_above_ma20_pct", 8.0)

    dist_high_pct = (high_20 - close) / high_20 * 100 if high_20 > 0 else 99
    cond_kd_room = (40 <= k_v <= 70) and (k_v > d_v)

    inst_lots = chips.get("inst_net_lots") if chips else None
    buy_streak = chips.get("inst_buy_streak") if chips else None
    foreign_lots = chips.get("foreign_net_lots") if chips else None
    min_streak = amb.get("accum_min_streak", 3)
    cond_accum = bool(inst_lots is not None and inst_lots > 0)
    strong_accum = bool(cond_accum and (buy_streak or 0) >= min_streak)

    # 蓄勢品質分（描述「彈簧」好不好，10 分）
    weights = {"base": 2, "squeeze": 2, "vol_dry": 1, "hold": 2, "kd_room": 1, "accum": 2}
    conds = {"base": cond_base, "squeeze": cond_squeeze, "vol_dry": cond_vol_dry,
             "hold": cond_hold, "kd_room": cond_kd_room, "accum": cond_accum}
    score = sum(weights[k] * int(conds[k]) for k in weights)
    max_total = sum(weights.values())

    # ===== 觸發：是否「帶量突破箱頂」= 啟動確認 =====
    broke = bool(close > high_20 and latest["Volume"] > vol20 * 1.2)

    # ===== 啟動就緒度（0~100，讓你直覺挑「即將啟動」）=====
    sq_s = _clip((1 - squeeze_ratio) / 0.5)                 # 收斂越緊越高
    dry_s = _clip((1 - vol5 / vol20) / 0.3) if vol20 else 0  # 量越縮越高
    near_s = _clip(1 - dist_high_pct / max(amb.get("near_high_pct", 8.0), 1e-9)) if dist_high_pct >= 0 else 0.3
    acc_s = _clip((buy_streak or 0) / 5) + (0.2 if (foreign_lots or 0) > 0 else 0)
    acc_s = _clip(acc_s)
    base_q = 0.6 + 0.4 * (1 if cond_base else 0.3)
    readiness = (30 * sq_s + 25 * near_s + 25 * acc_s + 20 * dry_s) * base_q
    if broke:
        readiness = max(readiness, 80.0)
    readiness = round(readiness, 0)
    if broke:
        launch_label = "⚡ 已啟動"
    elif readiness >= 70:
        launch_label = "⚡ 即將啟動"
    elif readiness >= 45:
        launch_label = "🔋 蓄勢中"
    else:
        launch_label = "🌱 醞釀早期"

    # ===== 進出場（埋伏現價、停損在箱底）=====
    atr = float(latest["ATR14"]) if pd.notna(latest.get("ATR14")) else None
    entry = close
    box_stop = low_20
    atr_stop = entry - atr * 2 if atr else box_stop
    stop = max(box_stop, atr_stop)        # 取較高者（較緊）但不高於進場
    if stop >= entry:
        stop = entry * 0.95
    risk = entry - stop
    risk_pct = risk / entry if entry > 0 else 0
    min_box_risk = amb.get("min_risk_pct", 0.03)
    if 0 < risk_pct < min_box_risk:
        stop = entry * (1 - min_box_risk)
        risk = entry - stop
        risk_pct = min_box_risk
    target_1r, target_2r = calc_targets(entry, stop)
    rr = 2.0 if risk > 0 else None

    # ===== 訊號（兩段式：未突破=觀察待發、帶量突破=進場啟動）=====
    require_confirm = amb.get("require_breakout_confirm", True)
    enter_thr = amb.get("enter_score", 6)
    watch_thr = amb.get("watch_score", 4)
    pending = False
    if rr is None and score >= enter_thr:
        signal, status = "觀察", "成功（停損距離過近）"
    elif score >= enter_thr:
        if require_confirm and not broke:
            signal, status, pending = "觀察", "成功（蓄勢待突破）", True
        else:
            signal, status = "進場", "成功（突破確認）" if broke else "成功"
    elif score >= watch_thr:
        signal, status = "觀察", "成功"
    else:
        signal, status = "不操作", "成功"

    # ===== 相對強度（顯示用）=====
    rs_diff = None
    if market_state and market_state.get("ret_60d") is not None and len(df) > 60:
        past = float(df["Close"].iloc[-61])
        if past > 0:
            rs_diff = (close / past - 1) * 100 - market_state["ret_60d"]

    # ===== 相對強度硬門檻：落後大盤的弱勢股不給進場（降為觀察）=====
    # 潛伏起漲最大陷阱＝撈到「便宜但沒人要」的落後股；RS<門檻者啟動機率明顯偏低。
    rs_downgrade = False
    if amb.get("require_positive_rs", True) and rs_diff is not None:
        if rs_diff < amb.get("min_rs", 0.0) and signal == "進場":
            signal, rs_downgrade = "觀察", True

    # ===== 現價偏離 =====
    if current_price is not None and entry > 0:
        price_dev = (current_price - entry) / entry * 100
    else:
        price_dev = None

    # ===== 籌碼確認 / 否決 =====
    chip_confirm, chip_warn = "—", None
    foreign_lots = chips.get("foreign_net_lots") if chips else None
    if inst_lots is not None:
        if inst_lots > 0 and (foreign_lots is None or foreign_lots >= 0):
            chip_confirm = f"法人連買{buy_streak}日" if (buy_streak and buy_streak >= 2) else "法人買超"
        elif inst_lots > 0:
            chip_confirm = "投信買外資賣"
        elif inst_lots < 0:
            chip_confirm = "法人賣超"
            chip_warn = f"法人賣超 {abs(inst_lots):,}張"
            if cfg.get("chips", {}).get("sell_downgrade", True) and signal == "進場":
                signal = "觀察"

    # ===== 融資券 =====
    margin_chg = margin.get("margin_chg_pct") if margin else None
    short_ratio = margin.get("short_margin_ratio") if margin else None
    margin_flag, margin_warn = "—", None
    surge = cfg.get("margin", {}).get("surge_pct", 10.0)
    if margin_chg is not None and margin_chg >= surge:
        margin_flag, margin_warn = "融資爆增", f"融資爆增 +{margin_chg:.0f}%"

    # ===== 財報避雷 =====
    earn_cfg = cfg.get("earnings", {})
    d2e = days_to_earnings(earnings_date)
    earn_warn = None
    if d2e is not None and -earn_cfg.get("post_days", 1) <= d2e <= earn_cfg.get("pre_days", 3):
        earn_warn = f"財報臨近{d2e}日" if d2e >= 0 else f"財報剛過{-d2e}日"
        if earn_cfg.get("blackout_downgrade", True) and signal == "進場":
            signal = "觀察"

    # ===== 月營收動能（基本面催化劑）=====
    from .revenue import classify_revenue
    rev_confirm, rev_warn, rev_strong, rev_weak = classify_revenue(
        revenue, cfg.get("revenue", {}))
    if rev_weak and cfg.get("revenue", {}).get("downgrade_on_weak", True) and signal == "進場":
        signal = "觀察"

    # ===== 部位 =====
    ps = cfg.get("position_sizing", {})
    position_factor = market_state["position_factor"] if market_state else 1.0
    pos = calc_position(
        entry=entry, stop=stop,
        total_capital=ps.get("total_capital", 1_000_000),
        risk_pct=ps.get("risk_per_trade_pct", 0.01),
        position_factor=position_factor,
        lot_size=ps.get("lot_size", 1000),
        max_position_pct=ps.get("max_position_pct", 0.20),
    )

    # ===== 操作建議 / 綜合評級 =====
    if market_state and market_state["regime"] == "bear":
        action, grade, reason = "大盤空頭 暫停", "避開", "大盤空頭"
    elif signal == "進場" and pos["suggested_lots"] == 0:
        action, grade, reason = "資金不足", "避開", "資金不足"
    elif signal == "進場":
        action = "進場 · 突破確認" if broke else "埋伏 · 潛伏"
        red = [w for w in (chip_warn, margin_warn, earn_warn, rev_warn) if w]
        pos_r = []
        if broke:
            pos_r.append("帶量突破")
        if cond_squeeze:
            pos_r.append("波動收斂")
        if cond_base:
            pos_r.append("窄幅整理")
        if strong_accum:
            pos_r.append(chip_confirm)
        elif cond_accum:
            pos_r.append("法人買超")
        if rev_strong:
            pos_r.append(rev_confirm)
        grade = "A" if ((broke or readiness >= 70) and strong_accum and not red) else "B"
        reason = "＋".join(pos_r[:3]) if pos_r else "蓄勢"
        if red:
            reason += "（注意：" + "、".join(red) + "）"
    elif signal == "觀察":
        grade = "C"
        if rs_downgrade:
            action = "觀察 · 弱於大盤"
            reason = f"RS{rs_diff:+.1f}% 落後大盤（蓄勢{int(readiness)}，待轉強）"
        elif pending:
            action = "觀察 · 待突破"
            reason = f"{launch_label}（{int(readiness)}）"
        else:
            action = "觀察"
            reason = "蓄勢未足"
    else:
        action, grade, reason = "不操作", "避開", "未達潛伏條件"

    warns = " · ".join([w for w in (pos["warning"], chip_warn, margin_warn, earn_warn, rev_warn) if w])

    return {
        "股票": symbol, "公司名稱": company_name, "市場": market,
        "狀態": status, "訊號判斷": signal, "評分": score,
        "評分顯示": f"{score} / {max_total}",
        "操作建議": action, "綜合評級": grade, "評級理由": reason,
        "啟動就緒度": int(readiness), "啟動標籤": launch_label,
        "進場類型": "潛伏",
        "進場條件": f"窄幅{base_vol*100:.1f}% 量縮{vol5/vol20:.2f}× 距高{dist_high_pct:.1f}%",
        "收盤價": round(close, 2),
        "目前現價": round(current_price, 2) if current_price is not None else None,
        "現價偏離%": round(price_dev, 2) if price_dev is not None else None,
        "進場參考價": round(entry, 2),
        "停損價": round(stop, 2),
        "目標價1(+1R半倉)": target_1r,
        "目標價2(+2R出清)": target_2r,
        "風險": round(risk, 2),
        "風險%": round(risk_pct * 100, 2),
        "RR比": round(rr, 2) if rr is not None else None,
        "建議張數": pos["suggested_lots"],
        "進場成本": pos["cost"],
        "佔資金%": pos["cost_pct"],
        "部位提示": warns,
        "大盤狀態": market_state["label"] if market_state else "⚪",
        "籌碼確認": chip_confirm,
        "法人買賣超(張)": inst_lots,
        "外資買賣超(張)": foreign_lots,
        "法人連買天數": buy_streak,
        "融資券提示": margin_flag,
        "融資增減%": margin_chg,
        "券資比%": short_ratio,
        "財報日": earnings_date,
        "距財報日": d2e,
        "營收動能": rev_confirm,
        "月營收YoY%": round(revenue["yoy_pct"], 1) if (revenue and revenue.get("yoy_pct") is not None) else None,
        "月營收MoM%": round(revenue["mom_pct"], 1) if (revenue and revenue.get("mom_pct") is not None) else None,
        "營收月份": revenue.get("month") if revenue else None,
        "相對強度RS%": round(rs_diff, 2) if rs_diff is not None else None,
        "ATR14": round(atr, 2) if atr is not None else None,
        "20日高點": round(high_20, 2),
        "成交量": int(latest["Volume"]),
        "20日均量": int(vol20),
        "5日均量": int(vol5),
        "換手率%": round(turnover_rate, 2) if turnover_rate is not None else None,
        "MA20": round(ma20, 2), "MA60": round(ma60, 2),
        "K": round(k_v, 2), "D": round(d_v, 2),
        # 潛伏條件布林
        "窄幅整理": cond_base, "波動收斂": cond_squeeze, "量縮蓄勢": cond_vol_dry,
        "站穩MA20": cond_hold, "KD有空間": cond_kd_room,
        "法人吸籌": cond_accum, "帶量突破": broke,
        "距20日高%": round(dist_high_pct, 1),
    }
