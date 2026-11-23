"""設定 ↔ 掃描設定：風格 Preset、build_cfg（session_state → cfg）、套用後免重抓重掃。"""

import streamlit as st

from twscanner.services import run_scan
from twscanner.services.runconfig import build_run_config
from twscanner.ui.state import get_base_config


def apply_preset(key):
    base_cfg = get_base_config()
    p = base_cfg.get("presets", {}).get(key, {})
    if not p:
        return
    st.session_state["preset"] = key
    st.session_state["min_price"] = float(p["filters"]["min_price"])
    st.session_state["min_avg_volume"] = int(p["filters"]["min_avg_volume"])
    st.session_state["require_ma60"] = bool(p["filters"]["require_above_ma60"])
    st.session_state["min_risk_pct"] = float(p["filters"]["min_risk_pct"])
    st.session_state["min_risk_pct_slider"] = float(p["filters"]["min_risk_pct"]) * 100
    st.session_state["thr_enter"] = int(p["thresholds"]["enter"])
    st.session_state["thr_watch"] = int(p["thresholds"]["watch"])
    st.session_state["risk_pct"] = float(p["risk_per_trade_pct"]) * 100
    st.session_state["max_pos_pct"] = int(p["max_position_pct"] * 100)


def apply_and_rescan(toast_msg="已套用設定"):
    """套用設定後，若有現成掃描資料則『免重抓』立即重掃，免使用者跨分頁手動操作。"""
    if st.session_state.get("scan_cache"):
        try:
            cfg2 = build_cfg()
            new_result = run_scan(cfg=cfg2, cached=st.session_state["scan_cache"])
            new_result["scan_cache"] = st.session_state["scan_cache"]
            st.session_state["result"] = new_result
            st.session_state["cfg"] = cfg2
            st.toast(f"{toast_msg}，已用現有資料重新評估 → 到「找標的」看結果", icon="✅")
        except Exception as e:
            st.toast(f"{toast_msg}（重掃失敗：{e}）", icon="⚠")
    else:
        st.toast(f"{toast_msg}（尚無掃描資料，下次掃描生效）", icon="✅")
    st.rerun()


def build_cfg():
    """目前設定 → 本次掃描 cfg（各分頁按下執行時呼叫）。"""
    return build_run_config(get_base_config(), st.session_state)
