"""側欄 UI。回傳 SidebarState 給需要「資料來源 / 開始掃描」的分頁使用。"""
from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from twscanner.storage import cloud as store
from twscanner.storage.preferences import save_prefs
from twscanner.ui.components.common import make_stock_list_template
from twscanner.ui.glossary import HELP
from twscanner.ui.settings import apply_preset
from twscanner.ui.state import cloud_passcode, get_base_config


@dataclass
class SidebarState:
    """側欄中「不是 session_state 設定值」而是本次互動的結果，給分頁使用。"""
    mode: str                 # "掃描全台股" / "上傳清單"
    uploaded: object          # st.file_uploader 回傳值（或 None）
    universe_kind: str        # twse / twse-common / twse-etf
    run_btn: bool             # 本次是否按下「開始掃描」
    mode_labels: dict = field(default_factory=dict)   # 策略模式代碼 → 中文



def render_sidebar():
    """側欄：資料來源 / 策略模式 / 風格 / 風控 / 過濾 / 權重 / 雲端 / 偏好 / 待處理。"""
    base_cfg = get_base_config()
    with st.sidebar:
        # ① 資料來源（掃哪些股）
        st.markdown("### ① 資料來源")
        source_options = {
            "upload": "上傳清單",
            "universe": "全台股",
        }
        source = st.segmented_control(
            "資料來源",
            options=list(source_options.keys()),
            format_func=lambda k: source_options[k],
            default="universe",
            label_visibility="collapsed",
        )

        uploaded = None
        universe_kind = "twse"
        mode = "掃描全台股" if source == "universe" else "上傳清單"

        if source == "upload":
            upl_c1, upl_c2 = st.columns([3, 2])
            with upl_c1:
                uploaded = st.file_uploader(
                    "上傳 xlsx", type=["xlsx"], label_visibility="collapsed",
                )
            upl_c2.download_button(
                "下載模板",
                data=make_stock_list_template(),
                file_name="股票清單_模板.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            if not uploaded:
                st.caption("欄位需含：股票代號 / 公司名稱")
        else:  # universe
            universe_kind = st.selectbox(
                "範圍",
                ["twse", "twse-common", "twse-etf"],
                format_func=lambda x: {
                    "twse": "上市普通股 + ETF",
                    "twse-common": "僅普通股",
                    "twse-etf": "僅 ETF",
                }[x],
                label_visibility="collapsed",
            )
            st.caption("首次 5–15 分鐘；同日重跑 < 1 分鐘")

        # ② 策略模式（怎麼獵）— 最常切換
        st.markdown("### ② 策略模式")
        _mode_opts = {
            "breakout": "強勢突破",
            "early": "早期突破",
            "ambush": "潛伏起漲前",
        }
        _mode_help = {
            "breakout": "追強勢：突破創高＋量增＋法人買。買已在漲的（追動能）。",
            "early": "只抓剛突破、未追高的：收緊延伸度＋拒絕非新鮮突破。",
            "ambush": "起漲前埋伏：窄幅整理＋量縮＋站穩均線＋接近未突破＋法人吸籌。",
        }
        strategy_mode = st.segmented_control(
            "策略模式",
            options=list(_mode_opts.keys()),
            format_func=lambda k: _mode_opts[k],
            default=st.session_state.get("strategy_mode", "breakout"),
            key="strategy_mode",
            label_visibility="collapsed",
        )
        st.caption(_mode_help.get(strategy_mode or "breakout", ""))

        # ③ 風格 Preset（多積極）— 門檻/風險微調
        st.markdown("### ③ 風格（微調）")
        preset_options = {
            "conservative": base_cfg["presets"]["conservative"]["label"],
            "balanced": base_cfg["presets"]["balanced"]["label"],
            "aggressive": base_cfg["presets"]["aggressive"]["label"],
        }
        current_preset = st.session_state.get("preset", "balanced")
        selected_preset = st.segmented_control(
            "風格 Preset",
            options=list(preset_options.keys()),
            format_func=lambda k: preset_options[k],
            default=current_preset,
            label_visibility="collapsed",
        )
        st.caption("調整進場門檻嚴格度與單筆風險（保守=嚴、積極=寬）")
        if selected_preset and selected_preset != current_preset:
            apply_preset(selected_preset)
            st.rerun()

        st.markdown("")
        run_btn = st.button("🔍 開始掃描", type="primary", use_container_width=True)

        st.divider()

        with st.expander("部位與風控", expanded=True):
            st.number_input(
                "總資金（元）", min_value=100_000,
                value=int(base_cfg.get("position_sizing", {}).get("total_capital", 1_000_000)),
                step=100_000, key="total_capital", help=HELP["total_capital"],
            )
            st.slider(
                "單筆風險 %", 0.5, 5.0,
                st.session_state.get("risk_pct", 1.0), 0.25, key="risk_pct",
                help=HELP["risk_per_trade"],
            )
            st.slider(
                "單檔最大佔比 %", 5, 50,
                st.session_state.get("max_pos_pct", 20), 5, key="max_pos_pct",
                help=HELP["max_pos_pct"],
            )
            st.slider(
                "ATR 停損倍數", 1.0, 4.0,
                float(st.session_state.get("f_atr_mult", base_cfg["filters"].get("atr_mult", 1.5))),
                0.5, key="f_atr_mult",
                help="停損 = 進場價 − ATR14 × 此倍數。建議模式可自動校準到高原中心。",
            )
            st.slider(
                "流動性上限（部位 ≤ 此%×20日均量）", 0, 30,
                int(st.session_state.get(
                    "max_adv_pct",
                    base_cfg.get("position_sizing", {}).get("max_adv_pct", 0.10) * 100)),
                5, key="_max_adv_pct_pct",
                help="避免小型股算出『進得去出不來』的部位。0=關閉。例如 10% = 部位不超過一日均量的 10%。",
            )
            st.session_state["max_adv_pct"] = st.session_state["_max_adv_pct_pct"] / 100

        with st.expander("選股過濾", expanded=False):
            st.number_input(
                "最低股價", min_value=0.0,
                value=st.session_state.get("min_price", 10.0), step=1.0, key="min_price",
                help=HELP["min_price"],
            )
            st.number_input(
                "20 日均量下限（股）", min_value=0,
                value=st.session_state.get("min_avg_volume", 500_000), step=100_000,
                key="min_avg_volume", help=HELP["min_avg_volume"],
            )
            st.checkbox(
                "必須站上 MA60",
                value=st.session_state.get("require_ma60", True), key="require_ma60",
                help=HELP["require_ma60"],
            )
            st.slider(
                "最小停損距離 %", 0.0, 10.0,
                st.session_state.get("min_risk_pct", 0.02) * 100, 0.5,
                key="min_risk_pct_slider", help=HELP["min_risk_pct"],
            )
            _amba = base_cfg.get("strategy", {}).get("ambush", {})
            st.checkbox(
                "潛伏模式：RS 硬門檻（排除弱於大盤）",
                value=bool(st.session_state.get("amb_rs_gate", _amba.get("require_positive_rs", True))),
                key="amb_rs_gate",
                help="開啟後，相對強度 RS < 門檻的弱勢股即使蓄勢成立也只給「觀察·弱於大盤」，不給進場。",
            )
            st.slider(
                "RS 門檻（%）", -5.0, 10.0,
                float(st.session_state.get("amb_min_rs", _amba.get("min_rs", 0.0))),
                0.5, key="amb_min_rs",
                help="個股 60 日報酬須 ≥ 大盤 + 此值。0=只要不輸大盤；正值=要明顯強過大盤。",
            )

        with st.expander("評分權重 / 門檻", expanded=False):
            w = base_cfg["scoring"]["weights"]
            w_breakout = st.slider("突破 + 量增", 0, 5,
                                     st.session_state.get("w_breakout", int(w["breakout_with_volume"])),
                                     key="w_breakout", help=HELP["weight_breakout"])
            w_ma = st.slider("MA 多頭", 0, 5,
                              st.session_state.get("w_ma", int(w["ma_bullish"])),
                              key="w_ma", help=HELP["weight_ma_bullish"])
            w_turnover = st.slider("換手率強勢", 0, 5,
                                     st.session_state.get("w_turnover", int(w["turnover_strong"])),
                                     key="w_turnover", help=HELP["weight_turnover_strong"])
            w_kd = st.slider("KD", 0, 5, st.session_state.get("w_kd", int(w["kd"])),
                              key="w_kd", help=HELP["weight_kd"])
            w_macd = st.slider("MACD", 0, 5, st.session_state.get("w_macd", int(w["macd"])),
                                key="w_macd", help=HELP["weight_macd"])
            w_rs = st.slider("相對強度 RS", 0, 5,
                              st.session_state.get("w_rs", int(w.get("rel_strength", 1))),
                              key="w_rs", help=HELP["weight_rel_strength"])
            w_trend = st.slider("趨勢確認", 0, 5,
                                 st.session_state.get("w_trend", int(w.get("trend_confirm", 1))),
                                 key="w_trend", help=HELP["weight_trend_confirm"])
            max_total = w_breakout + w_ma + w_turnover + w_kd + w_macd + w_rs + w_trend
            st.caption(f"總分上限：{max_total}")

            st.number_input(
                "進場 ≥", 0, 20,
                st.session_state.get("thr_enter", 6), key="thr_enter",
                help=HELP["thr_enter"],
            )
            st.number_input(
                "觀察 ≥", 0, 20,
                st.session_state.get("thr_watch", 5), key="thr_watch",
                help=HELP["thr_watch"],
            )

        st.divider()
        if store.is_enabled():
            _owner = st.session_state.get("cloud_owner")
            _icon = "☁ 已登入" if _owner else "☁ 雲端空間"
            with st.expander(_icon, expanded=True):
                if _owner:
                    ok, msg = store.ping()
                    if ok:
                        st.success("🔗 雲端連線正常")
                        try:
                            _n = len(store.load_holdings(_owner) or [])
                        except Exception:
                            _n = 0
                        st.caption(f"雲端持股：{_n} 筆")
                    else:
                        st.error(f"⚠ 雲端連線失敗：{msg}")
                        st.caption("→ 多半是 DATABASE_URL 連線字串有誤（見下方提示）。持股暫存本機。")
                    cb1, cb2 = st.columns(2)
                    if cb1.button("⬆ 立即存雲端", use_container_width=True):
                        _df = st.session_state.get("holdings_df")
                        if store.save_holdings(_owner, _df):
                            st.session_state["_hold_sig"] = _df.to_json() if _df is not None else ""
                            st.toast("已存到雲端", icon="✅")
                        else:
                            st.error(f"存雲端失敗：{store.last_error}")
                    if cb2.button("⬇ 從雲端載入", use_container_width=True):
                        _cd = store.load_holdings(_owner)
                        if _cd is not None:
                            st.session_state["holdings_df"] = _cd
                            st.session_state["_hold_sig"] = _cd.to_json()
                            st.toast(f"已載入 {len(_cd)} 筆", icon="✅")
                            st.rerun()
                        else:
                            st.info("雲端尚無持股資料")
                    if st.button("登出雲端", use_container_width=True):
                        for k in ("cloud_owner", "_cloud_loaded", "_hold_sig"):
                            st.session_state.pop(k, None)
                        st.rerun()
                else:
                    st.caption("輸入密碼登入，持股與訊號日誌將永久保存於雲端。")
                    _pw = st.text_input("密碼", type="password", key="cloud_pw")
                    if st.button("登入雲端", type="primary", use_container_width=True):
                        _pc = cloud_passcode()
                        if _pc and _pw == _pc:
                            st.session_state["cloud_owner"] = "me"
                            st.session_state.pop("_cloud_loaded", None)
                            st.rerun()
                        else:
                            st.error("密碼錯誤或未設定 APP_PASSCODE")

        with st.expander("偏好設定", expanded=False):
            st.caption("儲存後下次啟動會自動套用")
            if st.button("儲存目前設定", use_container_width=True):
                ok = save_prefs({
                    "preset": st.session_state.get("preset", "balanced"),
                    "total_capital": int(st.session_state.get("total_capital", 1_000_000)),
                    "onboarded": True,
                })
                if ok:
                    st.success("已儲存")
                else:
                    st.error("儲存失敗")

        # 待處理 chip
        if st.session_state["watchlist"]:
            st.divider()
            st.markdown("### 待處理")
            codes = " ".join(
                [f"<span class='watch-chip'>{w['code']}</span>"
                 for w in st.session_state["watchlist"]]
            )
            st.markdown(f"<div class='watch-chips'>{codes}</div>",
                         unsafe_allow_html=True)
            st.caption(f"{len(st.session_state['watchlist'])} 檔待加入持股")
            if st.button("→ 加入持股", use_container_width=True):
                # 把 watchlist 內容轉成持股 DataFrame
                if "holdings_df" not in st.session_state:
                    st.session_state["holdings_df"] = pd.DataFrame(columns=[
                        "股票代號", "公司名稱", "成本價", "持有股數",
                    ])
                new_rows = []
                for w in st.session_state["watchlist"]:
                    new_rows.append({
                        "股票代號": w["code"],
                        "公司名稱": w.get("name", ""),
                        "成本價": w.get("entry", 0.0),
                        "持有股數": int(w.get("lots", 1)) * 1000,
                    })
                new_df = pd.DataFrame(new_rows)
                st.session_state["holdings_df"] = pd.concat(
                    [st.session_state["holdings_df"], new_df], ignore_index=True,
                )
                st.session_state["watchlist"] = []
                st.success(f"已加入 {len(new_rows)} 檔到持股管理")
                st.rerun()

    return SidebarState(
        mode=mode, uploaded=uploaded, universe_kind=universe_kind,
        run_btn=run_btn, mode_labels=_mode_opts,
    )
