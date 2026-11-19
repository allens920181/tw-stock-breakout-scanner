"""📈 買入掃描分頁。"""
import io
import logging
import tempfile
from datetime import datetime

import pandas as pd
import streamlit as st

from twscanner.core.tz import now_tw, today_tw
from twscanner.data.universe import fetch_twse_universe
from twscanner.reporting.excel import write_excel
from twscanner.services import run_adaptive_recommend, run_scan
from twscanner.storage import cloud as store
from twscanner.storage.history import cleanup_old, save_scan
from twscanner.ui.components.common import make_progress_block, render_onboarding
from twscanner.ui.components.signals import action_class
from twscanner.ui.glossary import HELP
from twscanner.ui.settings import build_cfg
from twscanner.ui.state import (
    cloud_owner,
    get_base_config,
    get_prefs,
    persist_calibration_date,
)


def render_results_table(df, key_prefix=""):
    # ===== Row 1：訊號 / 進場類型 / 最低評分 / 搜尋 =====
    fcol1, fcol2, fcol3, fcol4 = st.columns([2, 2, 1.5, 1.5])

    signal_options = ["進場", "觀察", "不操作"]
    available_signals = [
        s for s in signal_options
        if "訊號判斷" in df.columns and (df["訊號判斷"] == s).any()
    ]
    default_signals = [s for s in ["進場", "觀察"] if s in available_signals]
    sel_signals = fcol1.multiselect(
        "訊號", options=available_signals,
        default=default_signals or available_signals,
        key=f"{key_prefix}sig", help=HELP["signal"],
    )

    entry_type_options = []
    if "進場類型" in df.columns:
        entry_type_options = sorted(
            [x for x in df["進場類型"].dropna().unique() if x and x != "—"]
        )
    sel_entry_types = fcol2.multiselect(
        "進場類型", options=entry_type_options,
        default=entry_type_options,
        key=f"{key_prefix}etype",
        disabled=len(entry_type_options) == 0,
        help=HELP["entry_type"],
    )

    _top = pd.to_numeric(df["評分"], errors="coerce").max() if len(df) and "評分" in df.columns else 8
    # 全部 0 分（如大盤空頭）或全空值時，滑桿上下限相同會讓 Streamlit 拋例外 → 至少 1
    max_score = max(int(_top), 1) if pd.notna(_top) else 8
    min_score_filter = fcol3.slider(
        "最低評分", 0, max_score, 0, key=f"{key_prefix}minsc",
        help=HELP["score"],
    )
    keyword = fcol4.text_input("搜尋", placeholder="股票或公司名",
                                key=f"{key_prefix}kw")

    # ===== Row 2：風險% / 換手率% / 建議張數 / 顯示全欄 =====
    fr1, fr2, fr3, fr4 = st.columns([2, 2, 1.5, 1.5])

    if "風險%" in df.columns and df["風險%"].notna().any():
        risk_max = float(df["風險%"].max())
        risk_range = fr1.slider(
            "風險% 範圍", 0.0, max(risk_max, 50.0), (0.0, max(risk_max, 50.0)),
            step=1.0, key=f"{key_prefix}risk", help=HELP["risk_pct_signal"],
        )
    else:
        risk_range = None

    if "換手率%" in df.columns and df["換手率%"].notna().any():
        tr_max = float(df["換手率%"].max())
        tr_range = fr2.slider(
            "換手率% 範圍", 0.0, max(tr_max, 30.0), (0.0, max(tr_max, 30.0)),
            step=0.5, key=f"{key_prefix}tr", help=HELP["turnover_rate"],
        )
    else:
        tr_range = None

    lots_min = fr3.number_input(
        "最少建議張數", min_value=0, value=0, step=1,
        key=f"{key_prefix}lots",
        help=HELP["suggested_lots"],
    )
    show_full = fr4.toggle("顯示全欄", value=False, key=f"{key_prefix}full")

    # ===== 套用所有篩選（AND）=====
    filtered = df.copy()
    if "訊號判斷" in filtered.columns and sel_signals:
        filtered = filtered[filtered["訊號判斷"].isin(sel_signals)]
    if "進場類型" in filtered.columns and sel_entry_types and entry_type_options:
        # 「—」或空值視為不限
        mask = filtered["進場類型"].isin(sel_entry_types) | filtered["進場類型"].isna() | (filtered["進場類型"] == "—")
        if set(sel_entry_types) != set(entry_type_options):
            # 使用者有手動取消，才嚴格篩選
            mask = filtered["進場類型"].isin(sel_entry_types)
        filtered = filtered[mask]
    if "評分" in filtered.columns:
        filtered = filtered[filtered["評分"] >= min_score_filter]
    if keyword:
        k = keyword.strip()
        mask = (
            filtered.get("股票", pd.Series(dtype=str)).astype(str).str.contains(k, case=False, na=False)
            | filtered.get("公司名稱", pd.Series(dtype=str)).astype(str).str.contains(k, case=False, na=False)
        )
        filtered = filtered[mask]
    if risk_range is not None and "風險%" in filtered.columns:
        filtered = filtered[
            (filtered["風險%"].fillna(0) >= risk_range[0])
            & (filtered["風險%"].fillna(0) <= risk_range[1])
        ]
    if tr_range is not None and "換手率%" in filtered.columns:
        filtered = filtered[
            (filtered["換手率%"].fillna(0) >= tr_range[0])
            & (filtered["換手率%"].fillna(0) <= tr_range[1])
        ]
    if lots_min > 0 and "建議張數" in filtered.columns:
        filtered = filtered[filtered["建議張數"].fillna(0) >= lots_min]

    st.caption(f"顯示 {len(filtered)} / {len(df)} 筆")

    # 精簡欄位（預設）
    minimal_cols = [
        "股票", "公司名稱", "綜合評級", "啟動標籤", "啟動就緒度", "評級理由",
        "操作建議", "評分顯示",
        "目前現價", "進場參考價", "現價偏離%", "停損價", "目標價1(+1R半倉)",
        "風險%", "建議張數", "換手率%", "籌碼確認", "營收動能", "相對強度RS%",
    ]
    full_priority = minimal_cols + [
        "進場類型", "進場條件", "進場成本", "佔資金%", "部位提示",
        "法人連買天數", "法人買賣超(張)", "外資買賣超(張)", "法人5日累計(張)",
        "融資券提示", "融資增減%", "券資比%",
        "月營收YoY%", "月營收MoM%", "營收月份",
        "財報日", "距財報日",
        "產業", "族群同步", "族群強勢檔數",
        "相對強度RS%", "趨勢確認", "ADX", "乖離MA20%", "大盤確認(FTD)",
        "市場", "訊號判斷", "評分", "收盤價",
        "目標價2(+2R出清)", "RR比", "ATR14",
        "20日平均換手率%", "MA5", "MA20", "MA60", "K", "D", "OSC",
        "成交量", "20日均量", "50日均量",
        "突破+量增", "MA多頭", "換手率強勢", "KD強勢", "MACD多方", "相對強度",
        "大盤狀態", "狀態",
    ]
    target_cols = full_priority if show_full else minimal_cols
    show_cols = [c for c in target_cols if c in filtered.columns]
    if show_full:
        other_cols = [c for c in filtered.columns if c not in show_cols]
        show_cols += other_cols
    display = filtered[show_cols]

    col_cfg = {}
    col_help_map = {
        "風險%": HELP["risk_pct_signal"],
        "佔資金%": HELP["cost_pct"],
        "換手率%": HELP["turnover_rate"],
        "20日平均換手率%": HELP["turnover_rate"],
        "現價偏離%": "目前現價相對進場參考價的偏離；>+5% 會降為觀察（追高風險）",
        "相對強度RS%": HELP["weight_rel_strength"],
        "乖離MA20%": "進場參考價相對 MA20 的乖離；≥+10% 視為過度延伸（追高）降為觀察",
        "ADX": "趨勢強度指標；>20 視為趨勢成形，>40 強勁",
        "ATR14": "14 日平均真實波幅；停損 = 進場價 - ATR×倍數，使各股風險距離一致",
    }
    for c, h in col_help_map.items():
        if c in display.columns:
            col_cfg[c] = st.column_config.NumberColumn(c, format="%.2f%%", help=h)
    if "進場成本" in display.columns:
        col_cfg["進場成本"] = st.column_config.NumberColumn("進場成本", format="%d")
    if "操作建議" in display.columns:
        col_cfg["操作建議"] = st.column_config.TextColumn("操作建議", help=HELP["action"])
    if "綜合評級" in display.columns:
        col_cfg["綜合評級"] = st.column_config.TextColumn(
            "綜合評級", help="A=強力進場 / B=可進場 / C=觀察 / 避開。綜合技術+籌碼+RS+風險的一眼結論。")
    if "啟動就緒度" in display.columns:
        col_cfg["啟動就緒度"] = st.column_config.ProgressColumn(
            "啟動就緒度", min_value=0, max_value=100, format="%d",
            help="潛伏標的『即將啟動』的程度(0~100)：波動收斂+逼近突破+法人吸籌+量縮。越高越接近發動，點欄位標題可排序。")
    if "啟動標籤" in display.columns:
        col_cfg["啟動標籤"] = st.column_config.TextColumn(
            "啟動標籤", help="⚡已啟動/即將啟動 > 🔋蓄勢中 > 🌱醞釀早期")
    if "評分顯示" in display.columns:
        col_cfg["評分顯示"] = st.column_config.TextColumn("評分顯示", help=HELP["score"])
    if "RR比" in display.columns:
        col_cfg["RR比"] = st.column_config.NumberColumn("RR比", help=HELP["rr_ratio"])
    if "建議張數" in display.columns:
        col_cfg["建議張數"] = st.column_config.NumberColumn("建議張數", format="%d", help=HELP["suggested_lots"])
    if "進場類型" in display.columns:
        col_cfg["進場類型"] = st.column_config.TextColumn("進場類型", help=HELP["entry_type"])
    if "停損價" in display.columns:
        col_cfg["停損價"] = st.column_config.NumberColumn("停損價", format="%.2f", help=HELP["stop_loss"])
    if "目標價1(+1R半倉)" in display.columns:
        col_cfg["目標價1(+1R半倉)"] = st.column_config.NumberColumn("目標價1(+1R半倉)", format="%.2f", help=HELP["target_1r"])
    if "目標價2(+2R出清)" in display.columns:
        col_cfg["目標價2(+2R出清)"] = st.column_config.NumberColumn("目標價2(+2R出清)", format="%.2f", help=HELP["target_2r"])
    if "籌碼確認" in display.columns:
        col_cfg["籌碼確認"] = st.column_config.TextColumn("籌碼確認", help=HELP["chip_confirm"])
    for cc in ("法人買賣超(張)", "外資買賣超(張)", "法人5日累計(張)"):
        if cc in display.columns:
            col_cfg[cc] = st.column_config.NumberColumn(
                cc, format="%d",
                help=HELP["chip_foreign"] if "外資" in cc else HELP["chip_inst"],
            )
    if "法人連買天數" in display.columns:
        col_cfg["法人連買天數"] = st.column_config.NumberColumn(
            "法人連買天數", format="%d", help=HELP["chip_streak"])
    if "融資券提示" in display.columns:
        col_cfg["融資券提示"] = st.column_config.TextColumn("融資券提示", help=HELP["margin_flag"])
    if "融資增減%" in display.columns:
        col_cfg["融資增減%"] = st.column_config.NumberColumn("融資增減%", format="%.2f%%", help=HELP["margin_chg"])
    if "券資比%" in display.columns:
        col_cfg["券資比%"] = st.column_config.NumberColumn("券資比%", format="%.2f%%", help=HELP["short_ratio"])
    if "族群同步" in display.columns:
        col_cfg["族群同步"] = st.column_config.TextColumn("族群同步", help=HELP["group_sync"])
    if "族群強勢檔數" in display.columns:
        col_cfg["族群強勢檔數"] = st.column_config.NumberColumn("族群強勢檔數", format="%d", help=HELP["group_sync"])
    if "財報日" in display.columns:
        col_cfg["財報日"] = st.column_config.TextColumn("財報日", help=HELP["earnings_blackout"])
    if "距財報日" in display.columns:
        col_cfg["距財報日"] = st.column_config.NumberColumn("距財報日", format="%d", help=HELP["earnings_blackout"])

    # 訊號燈號（列底色）— 用「操作建議」分類，永遠存在於 display
    def _row_style(row):
        action = str(row.get("操作建議", ""))
        cls = action_class(action)
        if cls == "go":
            return ["background-color: #DCFCE7"] * len(row)
        if cls == "watch":
            return ["background-color: #FEF3C7"] * len(row)
        return [""] * len(row)

    # column_config 的 ProgressColumn 會接管 cell 渲染導致 Styler 失效，
    # 同時使用 Styler 時改用純 NumberColumn 顯示評分
    col_cfg_styled = {k: v for k, v in col_cfg.items() if k != "評分"}

    try:
        styled = display.style.apply(_row_style, axis=1)
        st.dataframe(
            styled, use_container_width=True, height=500,
            column_config=col_cfg_styled, hide_index=True,
        )
    except Exception as e:
        st.warning(f"列底色失效：{e}")
        st.dataframe(
            display, use_container_width=True, height=500,
            column_config=col_cfg, hide_index=True,
        )

    return filtered


def render(sb):
    """📈 買入掃描"""
    base_cfg = get_base_config()
    mode, uploaded, universe_kind = sb.mode, sb.uploaded, sb.universe_kind
    run_btn, _mode_opts = sb.run_btn, sb.mode_labels
    prefs = get_prefs()
    # ===== 今日三步引導列（降低首步迷路）=====
    st.markdown(
        "<div class='today-steps'>"
        "<span class='step'><b>①</b> 看上方大盤燈（🔴空頭別買）</span>"
        "<span class='arrow'>→</span>"
        "<span class='step'><b>②</b> 側欄選模式/來源，點「開始掃描」</span>"
        "<span class='arrow'>→</span>"
        "<span class='step'><b>③</b> 進場後到「💼 持股管理」追蹤出場</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ===== 執行掃描（進度條 / log 顯示在 tab1 內）=====
    if run_btn:
        input_path = None
        items = None

        if mode == "掃描全台股":
            try:
                with st.spinner("抓取全台股清單 …"):
                    raw = fetch_twse_universe(
                        include_common=universe_kind in ("twse", "twse-common"),
                        include_etf=universe_kind in ("twse", "twse-etf"),
                    )
                items = [{"code": x["code"], "company_name": x["company_name"]} for x in raw]
                st.info(f"將掃描 {len(items)} 檔")
            except Exception as e:
                st.error(f"抓取全台股清單失敗：{e}")
                st.stop()
        elif uploaded:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            tmp.write(uploaded.getvalue())
            tmp.close()
            input_path = tmp.name
        else:
            st.error("請從側欄選擇資料來源（上傳清單或全台股）")
            st.stop()

        cfg = build_cfg()
        bar, log_area, buf, handler = make_progress_block("掃描")
        logging.getLogger().setLevel(logging.INFO)
        logging.getLogger().addHandler(handler)

        def on_progress(stage, pct, msg):
            bar.progress(min(pct, 1.0), text=f"{stage} — {msg}")
            log_area.code("\n".join(buf[-30:]) or "（執行中…）")

        try:
            with st.spinner("掃描中 …"):
                result = run_scan(
                    input_path=input_path, cfg=cfg,
                    progress_cb=on_progress, items=items,
                )
            st.session_state["result"] = result
            st.session_state["scan_cache"] = result.get("scan_cache")
            st.session_state["cfg"] = cfg
            st.session_state["_result_mode"] = st.session_state.get("strategy_mode", "breakout")
            st.session_state["last_scan_at"] = now_tw().strftime("%H:%M:%S")
            try:
                save_scan(result, market_state=result.get("market_state"),
                          label=mode)
                cleanup_old(keep_n=30)
            except Exception as e:
                logging.getLogger("main").warning("存歷史失敗：%s", e)
            # 前向訊號日誌（live OOS）：記錄本次進場清單
            try:
                from twscanner.portfolio.journal import load_journal as _ld_jrn
                from twscanner.portfolio.journal import log_signals
                _added = log_signals(
                    result["df"], today_tw().isoformat(),
                    mode=mode, signals=("進場",))
                if _added:
                    st.toast(f"已記錄 {_added} 筆進場到訊號日誌（可在『歷史』追蹤實戰績效）",
                             icon="📓")
                    if cloud_owner():          # 鏡像到雲端（永久保存）
                        store.save_journal(cloud_owner(), _ld_jrn())
            except Exception as e:
                logging.getLogger("main").warning("訊號日誌記錄失敗：%s", e)
        except Exception as e:
            st.error(f"掃描失敗：{e}")
            st.exception(e)
            st.stop()
        finally:
            logging.getLogger().removeHandler(handler)
        bar.progress(1.0, text=f"完成（{result['elapsed_sec']:.1f} 秒）")

    if "result" not in st.session_state:
        if not prefs.get("onboarded", False):
            render_onboarding()
        else:
            st.info("從側欄選擇資料來源後點「**開始掃描**」")
    else:
        # ===== 切換策略模式 → 自動用快取即時重算（免重抓）=====
        _cur_mode = st.session_state.get("strategy_mode", "breakout")
        if (st.session_state.get("scan_cache")
                and st.session_state.get("_result_mode") not in (None, _cur_mode)):
            cfg = build_cfg()
            try:
                with st.spinner(f"切換為「{_mode_opts.get(_cur_mode, _cur_mode)}」，即時重算（免重抓）…"):
                    new_result = run_scan(cfg=cfg, cached=st.session_state["scan_cache"])
                new_result["scan_cache"] = st.session_state["scan_cache"]
                st.session_state["result"] = new_result
                st.session_state["cfg"] = cfg
                st.session_state["_result_mode"] = _cur_mode
                st.rerun()
            except Exception as e:
                st.session_state["_result_mode"] = _cur_mode   # 避免反覆重試
                st.error(f"即時切換失敗：{e}")

        result = st.session_state["result"]
        df = result["df"]
        summary = result["summary"]
        failed_df = result["failed_df"]

        # ===== 換風格/權重後免重抓、手動重新評估 =====
        if st.session_state.get("scan_cache"):
            rc1, rc2 = st.columns([3, 1.4])
            rc1.caption(f"目前資料：{st.session_state.get('last_scan_at', '')} 抓取。"
                        f"**策略模式切換已即時生效**；換「風格 Preset / 權重」後按右鈕重評估。")
            if rc2.button("⚡ 套用設定重評估（免重抓）", use_container_width=True):
                cfg = build_cfg()
                try:
                    with st.spinner("用現有資料重新分析 …"):
                        new_result = run_scan(cfg=cfg, cached=st.session_state["scan_cache"])
                    # 保留快取（重評估不改原始資料）
                    new_result["scan_cache"] = st.session_state["scan_cache"]
                    st.session_state["result"] = new_result
                    st.session_state["cfg"] = cfg
                    st.session_state["_result_mode"] = _cur_mode
                    st.toast("已用現有資料重新評估", icon="⚡")
                    st.rerun()
                except Exception as e:
                    st.error(f"重評估失敗：{e}")

            # ===== 一鍵：自動校準（依回測最佳參數）並重掃 =====
            with st.expander("🚀 一鍵自動校準並重掃（依回測最佳參數）", expanded=False):
                _res = st.session_state["scan_cache"].get("resolved", [])
                _n = len(_res)
                st.caption(
                    f"用現有 {_n} 檔資料：跑回測網格 → 取參數高原中心/lift權重/各盤勢最佳門檻 → "
                    f"**只自動套用 OOS 通過(✅) 的建議** → 立即重掃。免重抓、免逐步操作。"
                )
                if _n > 400:
                    st.warning(
                        f"⚠ 目前 {_n} 檔較多，校準需跑多輪全清單回測，可能要**數分鐘**。"
                        "建議先用較精簡的清單，或縮短回測天數。"
                    )
                _lc = st.session_state.get("last_calibrated_date")
                if _lc:
                    try:
                        _d = (today_tw() - datetime.fromisoformat(_lc).date()).days
                        if _d < 20:
                            st.warning(f"🕒 上次校準 {_d} 天前。建議每月一次即可，"
                                       "太頻繁會慢性過擬合（OOS 失去意義）。")
                        else:
                            st.caption(f"🕒 上次校準 {_d} 天前。")
                    except Exception:
                        pass
                oc1, oc2 = st.columns([2, 1])
                ac_lookback = oc1.slider("校準回測天數", 60, 250,
                                         int(st.session_state.get("ac_lookback", 120)),
                                         30, key="ac_lookback")
                go_auto = oc2.button("🚀 一鍵校準並重掃",
                                     type="primary", use_container_width=True)
                if go_auto:
                    from twscanner.research.adaptive import pick_applicable
                    cfg = build_cfg()
                    bar_o = st.progress(0.0, text="自動校準中 …")

                    def _oc_cb(p, msg):
                        try:
                            bar_o.progress(min(p * 0.8, 0.8), text=f"校準：{msg}")
                        except Exception:
                            pass
                    try:
                        ar = run_adaptive_recommend(
                            _res, cfg, lookback_days=int(ac_lookback),
                            hold_days=int(st.session_state.get("ac_hold", 10)),
                            targets=("thresholds", "weights", "regime"),
                            progress_cb=_oc_cb,
                        )
                        plan = pick_applicable(ar, require_oos=True)
                        ap = plan["applied"]
                        # 套用到 session（與手動面板同鍵）
                        if "thr_enter" in ap:
                            st.session_state["thr_enter"] = ap["thr_enter"]
                        if "f_atr_mult" in ap:
                            st.session_state["f_atr_mult"] = ap["f_atr_mult"]
                        if "weights" in ap:
                            _m = {"breakout_with_volume": "w_breakout", "ma_bullish": "w_ma",
                                  "turnover_strong": "w_turnover", "kd": "w_kd",
                                  "macd": "w_macd", "rel_strength": "w_rs",
                                  "trend_confirm": "w_trend"}
                            for sc_key, ss_key in _m.items():
                                if sc_key in ap["weights"]:
                                    st.session_state[ss_key] = ap["weights"][sc_key]
                        if "regime_thresholds" in ap:
                            st.session_state["regime_thresholds"] = ap["regime_thresholds"]
                        st.session_state["adapt_result"] = ar
                        st.session_state["autocal_plan"] = plan
                        persist_calibration_date()
                        # 用套用後的 cfg 立即重掃（免重抓）
                        bar_o.progress(0.85, text="套用建議後重掃 …")
                        cfg2 = build_cfg()
                        new_result = run_scan(cfg=cfg2, cached=st.session_state["scan_cache"])
                        new_result["scan_cache"] = st.session_state["scan_cache"]
                        st.session_state["result"] = new_result
                        st.session_state["cfg"] = cfg2
                        bar_o.progress(1.0, text="完成")
                        st.rerun()
                    except Exception as e:
                        st.error(f"一鍵校準失敗：{e}")
                if st.session_state.get("autocal_plan"):
                    _plan = st.session_state["autocal_plan"]
                    if _plan["summary"]:
                        st.success("✅ 已自動套用並重掃：" + "、".join(_plan["summary"]))
                    else:
                        st.info("本次無 OOS 通過的建議可套用（維持原參數）。")
                    if _plan["skipped"]:
                        st.caption("未套用（安全閘）：" + "、".join(
                            f"{n}（{r}）" for n, r in _plan["skipped"]))

        # 精簡 KPI（4 個）
        s = summary.iloc[0]
        cols = st.columns(4)
        cols[0].metric("進場候選", int(s.get("進場檔數", 0)), help=HELP["signal"])
        cols[1].metric("觀察", int(s.get("觀察檔數", 0)), help=HELP["signal"])
        cols[2].metric("掃描", int(s.get("掃描股票數", 0)))
        cols[3].metric("耗時 (秒)", s.get("執行秒數", "—"))

        st.markdown("### 完整結果")
        filtered = render_results_table(df, key_prefix="scan_")

        dl_col1, dl_col2 = st.columns(2)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            filtered.to_excel(writer, sheet_name="篩選結果", index=False)
            df.to_excel(writer, sheet_name="全部分析結果", index=False)
            summary.to_excel(writer, sheet_name="Report摘要", index=False)
            if failed_df is not None and len(failed_df) > 0:
                failed_df.to_excel(writer, sheet_name="錯誤清單", index=False)
        buf.seek(0)
        dl_col1.download_button(
            "下載 Excel 報告", data=buf.getvalue(),
            file_name="台股分析報告.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        if dl_col2.button("寫入專案目錄", use_container_width=True):
            cfg = st.session_state.get("cfg", base_cfg)
            out = cfg["output"]
            path = write_excel(df, summary, failed_df, out["dir"], out["prefix"])
            st.success(f"已輸出：{path}")

        if failed_df is not None and len(failed_df) > 0:
            with st.expander(f"錯誤清單（{len(failed_df)} 筆）"):
                st.dataframe(failed_df, use_container_width=True, hide_index=True)
