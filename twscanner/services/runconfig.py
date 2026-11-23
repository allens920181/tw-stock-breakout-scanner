"""設定值 → 掃描 cfg（純函式）。UI 的設定頁與排程工作共用。"""
import copy


def build_run_config(base_cfg, ss):
    """
    純函式：base config + 設定值（session_state 或任何 Mapping）→ 本次掃描用 cfg。
    不依賴 Streamlit，可單元測試。設定頁與掃描列 widget 的 key 即為 ss 的 key。
    """
    cfg = copy.deepcopy(base_cfg)
    f, sc = base_cfg["filters"], base_cfg["scoring"]
    w = sc["weights"]
    amb = base_cfg.get("strategy", {}).get("ambush", {})
    ps = base_cfg.get("position_sizing", {})

    cfg["filters"]["min_price"] = ss.get("min_price", f["min_price"])
    cfg["filters"]["min_avg_volume"] = int(ss.get("min_avg_volume", f["min_avg_volume"]))
    cfg["filters"]["require_above_ma60"] = ss.get("require_ma60", f["require_above_ma60"])
    cfg["filters"]["min_risk_pct"] = ss.get("min_risk_pct_slider", f["min_risk_pct"] * 100) / 100
    cfg["scoring"]["weights"] = {
        "breakout_with_volume": ss.get("w_breakout", int(w["breakout_with_volume"])),
        "ma_bullish": ss.get("w_ma", int(w["ma_bullish"])),
        "turnover_strong": ss.get("w_turnover", int(w["turnover_strong"])),
        "kd": ss.get("w_kd", int(w["kd"])),
        "macd": ss.get("w_macd", int(w["macd"])),
        "rel_strength": ss.get("w_rs", int(w.get("rel_strength", 1))),
        "trend_confirm": ss.get("w_trend", int(w.get("trend_confirm", 1))),
    }
    cfg["scoring"]["thresholds"] = {
        "enter": ss.get("thr_enter", sc["thresholds"]["enter"]),
        "watch": ss.get("thr_watch", sc["thresholds"]["watch"]),
    }
    # 建議模式：依大盤切門檻（套用後存於 session）
    rg_thr = ss.get("regime_thresholds")
    if rg_thr:
        cfg["scoring"]["regime_thresholds"] = rg_thr
    # ATR 停損倍數（建議模式可校準）
    cfg["filters"]["atr_mult"] = float(ss.get("f_atr_mult", f.get("atr_mult", 1.5)))
    # 潛伏 RS 硬門檻（設定頁可調）
    cfg.setdefault("strategy", {}).setdefault("ambush", {})
    cfg["strategy"]["ambush"]["require_positive_rs"] = bool(
        ss.get("amb_rs_gate", amb.get("require_positive_rs", True)))
    cfg["strategy"]["ambush"]["min_rs"] = float(ss.get("amb_min_rs", amb.get("min_rs", 0.0)))
    cfg["position_sizing"] = {
        "total_capital": int(ss.get("total_capital", ps.get("total_capital", 1_000_000))),
        "risk_per_trade_pct": ss.get("risk_pct", ps.get("risk_per_trade_pct", 0.01) * 100) / 100,
        "lot_size": 1000,
        "max_position_pct": ss.get("max_pos_pct", ps.get("max_position_pct", 0.2) * 100) / 100,
        "max_adv_pct": float(ss.get("max_adv_pct", ps.get("max_adv_pct", 0.10))),
    }
    cfg["strategy"]["mode"] = ss.get("strategy_mode", "breakout")
    base_costs = base_cfg.get("costs", {})
    cfg["costs"] = {
        "enabled": bool(ss.get("cost_enabled", base_costs.get("enabled", True))),
        "fee_rate": float(ss.get("cost_fee", base_costs.get("fee_rate", 0.001425) * 100)) / 100,
        "fee_discount": float(ss.get("cost_disc", base_costs.get("fee_discount", 1.0))),
        "tax_rate": float(ss.get("cost_tax", base_costs.get("tax_rate", 0.003) * 100)) / 100,
        "slippage_pct": float(ss.get("cost_slip", base_costs.get("slippage_pct", 0.0015) * 100)) / 100,
        "apply_to_factor_eval": bool(ss.get("cost_apply_fe", base_costs.get("apply_to_factor_eval", False))),
    }
    return cfg
