"""回測 / 壓力測試 / 自動校準 / 進階驗證（策略驗證頁的「回測」分頁）。"""
import io
import logging
import tempfile
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from twscanner.core.tz import today_tw
from twscanner.data.universe import fetch_twse_universe
from twscanner.services import (
    run_adaptive_recommend,
    run_backtest,
    run_factor_eval,
    run_plateau,
    run_sensitivity,
    run_stress_test,
)
from twscanner.ui.components.blocks import conclusion, kpi_row, signed_value
from twscanner.ui.components.charts import (
    render_drawdown_chart,
    render_edge_meter,
    render_monthly_returns,
)
from twscanner.ui.components.common import fmt_int, make_progress_block
from twscanner.ui.format import clean_stock_col, colors, strip_icon
from twscanner.ui.glossary import HELP
from twscanner.ui.settings import apply_and_rescan, build_cfg
from twscanner.ui.state import get_base_config, persist_calibration_date, seed


def render(sb):
    """回測 / 研究"""
    base_cfg = get_base_config()
    mode, uploaded, universe_kind = sb.mode, sb.uploaded, sb.universe_kind
    st.markdown("### 回測設定")
    bt_c1, bt_c2, bt_c3, bt_c4 = st.columns([1, 1, 1, 1.2])
    bt_lookback = bt_c1.number_input("回測天數", 30, 500, 120, 30, help=HELP["bt_lookback"])
    bt_hold = bt_c2.number_input("持有天數", 3, 60, 10, 1, help=HELP["bt_hold"])
    bt_min_score = bt_c3.number_input("最低評分", 0, 20, 5, 1, help=HELP["bt_min_score"])
    bt_c4.markdown("")
    run_bt_btn = bt_c4.button("跑回測", type="primary", use_container_width=True)

    _bc = base_cfg.get("costs", {})
    with st.expander("交易成本（讓回測說真話）", expanded=False):
        st.caption("台股來回成本約 0.45–0.6%：未計成本的期望值是虛胖的。")
        cc1, cc2, cc3, cc4 = st.columns(4)
        cc1.checkbox("計入交易成本", key=seed("cost_enabled", bool(_bc.get("enabled", True))))
        cc2.number_input("手續費率 %", 0.0, 0.5, step=0.01,
                         key=seed("cost_fee", float(_bc.get("fee_rate", 0.001425) * 100)))
        cc3.number_input("券商折數", 0.1, 1.0, step=0.05, key=seed("cost_disc", float(_bc.get("fee_discount", 1.0))))
        cc4.number_input("證交稅 %", 0.0, 0.5, step=0.05, key=seed("cost_tax", float(_bc.get("tax_rate", 0.003) * 100)))
        st.slider(
            "滑價（單邊 %）", 0.0, 0.5, step=0.05,
            key=seed("cost_slip", float(_bc.get("slippage_pct", 0.0015) * 100)),
            help="小型股突破成交常偏離訊號價；買貴/賣便宜各扣此%。讓回測/壓力測試更誠實。",
        )
        st.checkbox("因子驗證也扣成本", key=seed("cost_apply_fe", bool(_bc.get("apply_to_factor_eval", False))),
                    help="預設關閉，避免因子 lift 與回測雙重成本口徑混淆")
        _rt = (st.session_state.get("cost_fee", 0.1425) / 100
               * st.session_state.get("cost_disc", 1.0) * 2
               + st.session_state.get("cost_tax", 0.3) / 100)
        st.caption(f"估計來回成本率 ≈ {_rt*100:.2f}%（買賣手續費 + 賣出證交稅）")

    if run_bt_btn:
        bt_items = None
        bt_input = None
        if mode == "掃描全台股":
            try:
                with st.spinner("抓清單 …"):
                    raw = fetch_twse_universe(
                        include_common=universe_kind in ("twse", "twse-common"),
                        include_etf=universe_kind in ("twse", "twse-etf"),
                    )
                bt_items = [{"code": x["code"], "company_name": x["company_name"]} for x in raw]
            except Exception as e:
                st.error(f"抓清單失敗：{e}")
                st.stop()
        elif uploaded:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            tmp.write(uploaded.getvalue())
            tmp.close()
            bt_input = tmp.name
        else:
            st.error("請先到「找標的」頁上方選擇範圍（上傳清單或全台股）")
            st.stop()

        cfg = build_cfg()
        bar, log_area, buf, handler = make_progress_block("回測")
        logging.getLogger().addHandler(handler)

        def bt_progress_cb(stage, pct, msg):
            bar.progress(min(pct, 1.0), text=f"{stage} — {msg}")
            log_area.code("\n".join(buf[-30:]) or "（執行中…）")

        try:
            with st.spinner("回測中 …"):
                bt_result = run_backtest(
                    bt_input, cfg,
                    lookback_days=int(bt_lookback),
                    hold_days=int(bt_hold),
                    min_score=int(bt_min_score),
                    items=bt_items, progress_cb=bt_progress_cb,
                )
            st.session_state["backtest_result"] = bt_result
        except Exception as e:
            st.error(f"回測失敗：{e}")
        finally:
            logging.getLogger().removeHandler(handler)
        bar.progress(1.0, text="回測完成")
        # 今日決策在前面的分頁已經畫完了，重跑一次讓它用到新的回測統計
        if "backtest_result" in st.session_state:
            st.rerun()

    st.divider()

    if "backtest_result" not in st.session_state:
        conclusion("還沒有回測結果",
                   "設定天數後按「跑回測」。回測會用「找標的」的策略與「設定」頁的參數，模擬過去每一天照系統進出場的結果。",
                   "info")
    else:
        bt = st.session_state["backtest_result"]
        s = bt["summary"]
        oos_split = bt.get("oos_split")
        oos = oos_split["oos"] if oos_split and oos_split.get("n_oos", 0) > 0 else None
        key = oos or s
        e, n = key["期望值R"], key["總交易數"]
        src = "樣本外" if oos else "全體"
        if key.get("顯著正Edge"):
            conclusion(f"有統計上顯著的優勢：{src}期望值 {e:+.2f}R（{n} 筆）",
                       "照這套規則長期操作，平均每筆賺得比賠得多。仍要用實戰紀錄持續驗證。", "go")
        elif e > 0:
            conclusion(f"可能有優勢但還不能確定：{src}期望值 {e:+.2f}R（{n} 筆）",
                       "信賴區間跨過 0，賺錢可能只是運氣。用小部位或模擬累積更多樣本。", "wait")
        else:
            conclusion(f"目前沒有證據顯示能賺錢：{src}期望值 {e:+.2f}R（{n} 筆）",
                       "先不要用真錢照這組參數操作。可試其他策略模式、等大盤轉多，或用自動校準找穩定參數。", "stop")
        render_edge_meter(s["期望值R"])
        kpi_row([
            ("交易筆數", fmt_int(s["總交易數"]), f"平均每筆 {s['平均報酬%']:+.2f}%"),
            ("勝率", f"{s['勝率%']:.1f}%", f"最大單筆 {s['最大單筆%']:+.2f}%"),
            ("期望值", signed_value(s["期望值R"], f"{s['期望值R']:+.2f}R"), "每筆平均賺幾倍風險"),
            ("最大回撤", f"{s['最大回撤R']:.2f}R", "連續虧損最深的累積"),
        ])

        st.markdown("### 這個結果可信嗎")
        notes = []
        if "期望值R_CI下界" in s:
            notes.append(f"期望值 95% 信賴區間 [{s['期望值R_CI下界']}, {s['期望值R_CI上界']}]"
                         + ("：下界 > 0，達顯著。" if s.get("顯著正Edge") else "：跨過 0，未達顯著，不要據此調參數。"))
        notes.append(f"樣本可信度：{s.get('樣本可信度', '—')}。少於 30 筆的統計雜訊很大。")
        notes.append("報酬已扣來回交易成本。" if st.session_state.get("cost_enabled", True)
                     else "未計交易成本，期望值偏樂觀。")
        notes.append("生存者偏差：只回測現在仍上市的股票，已下市的不在內，所以回測天生偏樂觀。"
                     "請搭配「實戰績效」與壓力測試交叉驗證。")
        st.markdown("\n".join(f"- {x}" for x in notes))
        if oos:
            ist, ov = oos_split["is"], oos_split["overall"]
            st.caption("樣本外 = 用前段資料決定參數、後段資料驗證，最接近真實。樣本內遠好於樣本外 = 過度擬合。")
            st.dataframe(pd.DataFrame([
                {"分組": "樣本外（最可信）", "交易數": oos["總交易數"], "勝率%": oos["勝率%"], "期望值R": oos["期望值R"]},
                {"分組": "樣本內", "交易數": ist["總交易數"], "勝率%": ist["勝率%"], "期望值R": ist["期望值R"]},
                {"分組": "全體", "交易數": ov["總交易數"], "勝率%": ov["勝率%"], "期望值R": ov["期望值R"]},
            ]), use_container_width=True, hide_index=True, column_config={
                "勝率%": st.column_config.NumberColumn(format="%.1f%%"),
                "期望值R": st.column_config.NumberColumn("期望值", format="%+.2fR")})

        by_regime = bt.get("by_regime")
        if by_regime is not None and len(by_regime):
            st.markdown("### 不同大盤環境下的表現")
            st.caption("如果空頭時期望值明顯變差，代表這個策略依賴多頭，空頭休息的規則就很重要。")
            cc = colors()
            labels = by_regime["大盤狀態"].map(strip_icon)
            fig_r = go.Figure(go.Bar(
                x=labels, y=by_regime["期望值R"],
                marker_color=[cc["up"] if v > 0 else cc["down"] for v in by_regime["期望值R"]],
                text=[f"{v:+.2f}R（{int(nn)} 筆）" for v, nn in zip(by_regime["期望值R"], by_regime["總交易數"])],
                textposition="outside", marker_line_width=0,
            ))
            fig_r.add_hline(y=0, line=dict(color="#CBD5E1", width=1))
            fig_r.update_layout(
                height=260, margin=dict(l=8, r=8, t=16, b=8), plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                showlegend=False, yaxis=dict(visible=False),
                font=dict(family="Inter, Noto Sans TC, sans-serif", size=12))
            fig_r.update_xaxes(showgrid=False)
            st.plotly_chart(fig_r, use_container_width=True, config={"displayModeBar": False})

        if len(bt["trades"]):
            st.markdown("### 累積損益（R）與回撤")
            render_drawdown_chart(bt["trades"])

            st.markdown("### 每月損益（R）")
            render_monthly_returns(bt["trades"])

            tcol1, tcol2 = st.columns(2)
            with tcol1:
                st.markdown("### 表現最好的 10 檔")
                st.dataframe(
                    clean_stock_col(bt["by_symbol"].head(10)),
                    use_container_width=True, hide_index=True,
                )
            with tcol2:
                st.markdown("### 表現最差的 10 檔")
                st.dataframe(
                    clean_stock_col(bt["by_symbol"].tail(10).sort_values("期望值R")),
                    use_container_width=True, hide_index=True,
                )

            with st.expander("交易明細"):
                st.dataframe(bt["trades"], use_container_width=True,
                              height=400, hide_index=True)

            buf_bt = io.BytesIO()
            with pd.ExcelWriter(buf_bt, engine="openpyxl") as writer:
                pd.DataFrame([s]).to_excel(writer, sheet_name="摘要", index=False)
                bt["trades"].to_excel(writer, sheet_name="交易明細", index=False)
                if len(bt["by_symbol"]):
                    bt["by_symbol"].to_excel(writer, sheet_name="個股統計", index=False)
            buf_bt.seek(0)
            st.download_button(
                "下載回測報告", data=buf_bt.getvalue(),
                file_name="回測報告.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            # ===== 敏感度（收合）=====
            st.divider()
            with st.expander("敏感度分析：不同最低評分下的期望值", expanded=False):
                st.caption("跑 min_score 4–7 各一次，比較不同門檻的 edge。需要先跑過一次回測。")
                if st.button("跑敏感度", key="sens_btn"):
                    cfg = build_cfg()
                    resolved = bt.get("resolved")
                    if not resolved:
                        st.error("缺少回測資料 — 請重跑回測")
                    else:
                        bar2 = st.progress(0.0, text="敏感度分析中 …")
                        def sens_progress(pct, sc):
                            bar2.progress(min(pct, 1.0), text=f"min_score={sc}")
                        try:
                            sens_df = run_sensitivity(
                                resolved, cfg, [4, 5, 6, 7],
                                int(bt_lookback), int(bt_hold),
                                progress_cb=sens_progress,
                            )
                            st.session_state["sensitivity"] = sens_df
                        except Exception as e:
                            st.error(f"敏感度失敗：{e}")

                if "sensitivity" in st.session_state:
                    sens_df = st.session_state["sensitivity"]
                    st.dataframe(sens_df, use_container_width=True, hide_index=True)
                    fig_s = go.Figure(go.Bar(
                        x=sens_df["min_score"], y=sens_df["期望值R"],
                        marker_color=[colors()["up"] if v > 0 else colors()["down"]
                                       for v in sens_df["期望值R"]],
                        text=[f"{v:.2f}" for v in sens_df["期望值R"]],
                        textposition="outside", marker_line_width=0,
                    ))
                    fig_s.update_layout(
                        height=260, margin=dict(l=8, r=8, t=8, b=8),
                        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                        showlegend=False,
                        xaxis_title="min_score", yaxis_title="期望值 R",
                        font=dict(family="Inter, sans-serif", size=11),
                    )
                    fig_s.update_xaxes(showgrid=False)
                    fig_s.update_yaxes(showgrid=True, gridcolor="#F1F5F9")
                    st.plotly_chart(fig_s, use_container_width=True,
                                     config={"displayModeBar": False})

            # ===== 壓力情境回測（滑價 ×N）=====
            st.divider()
            st.markdown("### 壓力測試：成交價變差時還賺錢嗎")
            st.caption(
                "平常滑價是「常態假設」；但小型股**跳空/漲停打開**時可能滑 1~3%。"
                "把滑價放大重跑，看 edge 在**最壞成交**下是否還活著——存活才敢放大部位。"
            )
            sc1, sc2 = st.columns([2, 1])
            stress_mult = sc1.select_slider(
                "滑價放大倍數", options=[2, 3, 5, 8], key=seed("stress_mult", 3),
            )
            if sc2.button("跑壓力測試", key="stress_btn", use_container_width=True):
                resolved = bt.get("resolved")
                if not resolved:
                    st.error("缺少回測資料 — 請重跑回測")
                else:
                    cfg = build_cfg()
                    with st.spinner(f"滑價 ×{stress_mult} 重跑回測 …"):
                        try:
                            st.session_state["stress_result"] = run_stress_test(
                                resolved, cfg, mult=float(stress_mult),
                                lookback_days=int(bt_lookback), hold_days=int(bt_hold),
                            )
                        except Exception as e:
                            st.error(f"壓力測試失敗：{e}")
            if "stress_result" in st.session_state:
                sr = st.session_state["stress_result"]
                b, ss = sr["base"], sr["stress"]

                def _g(d, k):
                    return d.get(k)
                srows = [
                    {"指標": "期望值R", "常態": _g(b, "期望值R"), f"壓力×{int(sr['mult'])}": _g(ss, "期望值R")},
                    {"指標": "勝率%", "常態": _g(b, "勝率%"), f"壓力×{int(sr['mult'])}": _g(ss, "勝率%")},
                    {"指標": "平均R", "常態": _g(b, "平均R"), f"壓力×{int(sr['mult'])}": _g(ss, "平均R")},
                    {"指標": "最大回撤R", "常態": _g(b, "最大回撤R"), f"壓力×{int(sr['mult'])}": _g(ss, "最大回撤R")},
                ]
                st.dataframe(pd.DataFrame(srows), use_container_width=True, hide_index=True)
                be, se = _g(b, "期望值R") or 0, _g(ss, "期望值R") or 0
                st.caption(f"滑價 {sr['base_slippage_pct']*100:.2f}% → {sr['stress_slippage_pct']*100:.2f}%")
                if se > 0:
                    st.success(f"最壞成交下期望值仍為正（{se:.3f}R）— edge 穩健，可正常部位。")
                elif be > 0:
                    st.warning(f"期望值由正（{be:.3f}R）轉為 {se:.3f}R — edge 對成本敏感，"
                               "宜降部位/只做高流動性標的。")
                else:
                    st.error("常態與壓力下期望值皆非正 — 此設定無穩健 edge，勿放大部位。")

            # ===== 自動校準（建議模式）=====
            st.divider()
            st.markdown("### 自動校準")
            st.caption(
                "把回測**回饋**到選股參數：系統算出建議值，**你一鍵套用**（不自動改）。"
                "取「參數高原中心」非最高峰、避免過擬合；每項附 **OOS 同向檢核**——"
                "樣本內決定、樣本外驗證，通過的才建議套用。"
            )
            _lastcal = st.session_state.get("last_calibrated_date")
            if _lastcal:
                try:
                    _days = (today_tw()
                             - datetime.fromisoformat(_lastcal).date()).days
                    if _days < 20:
                        st.warning(
                            f"上次校準在 {_days} 天前。**建議每月校準一次即可**——"
                            "校準太頻繁、反覆用同一段歷史挑參數，OOS 會被你看到失效（慢性過擬合）。")
                    else:
                        st.caption(f"上次校準 {_days} 天前（建議每月一次）。")
                except Exception:
                    pass
            ac1, ac2 = st.columns([2, 1])
            ac_targets = ac1.multiselect(
                "校準對象",
                ["thresholds", "weights", "regime"],
                default=["thresholds", "weights", "regime"],
                format_func=lambda x: {"thresholds": "進場門檻(min_score/atr/tp)",
                                       "weights": "評分權重(7因子)",
                                       "regime": "隨大盤切門檻"}[x],
                key="adapt_targets",
            )
            run_adapt = ac2.button("跑自動校準", key="adapt_btn",
                                   use_container_width=True)
            if run_adapt:
                resolved = bt.get("resolved")
                if not resolved:
                    st.error("缺少回測資料 — 請重跑回測")
                elif not ac_targets:
                    st.warning("請至少選一個校準對象")
                else:
                    cfg = build_cfg()
                    fe_cached = st.session_state.get("factor_eval")
                    bar_a = st.progress(0.0, text="自動校準中 …")

                    def _ac_cb(p, msg):
                        try:
                            bar_a.progress(min(p, 1.0), text=f"校準：{msg}")
                        except Exception:
                            pass
                    try:
                        st.session_state["adapt_result"] = run_adaptive_recommend(
                            resolved, cfg, lookback_days=int(bt_lookback),
                            hold_days=int(bt_hold), targets=tuple(ac_targets),
                            fe_result=fe_cached, progress_cb=_ac_cb,
                        )
                        persist_calibration_date()
                    except Exception as e:
                        st.error(f"自動校準失敗：{e}")
                    bar_a.progress(1.0, text="完成")

            if "adapt_result" in st.session_state:
                ar = st.session_state["adapt_result"]

                # --- 進場門檻 ---
                if ar.get("params"):
                    _pl = {"min_score": "最低評分 min_score", "atr_mult": "ATR停損倍數",
                           "tp_mult": "停利倍數 tp_mult"}
                    rows = []
                    for p in ar["params"]:
                        oos = p.get("oos_ok")
                        rows.append({
                            "參數": _pl.get(p["param"], p["param"]),
                            "目前": p.get("current"),
                            "建議": p.get("recommended") if p.get("recommended") is not None else "—（無明顯高原）",
                            "OOS同向": "✓ 是" if oos else ("✗ 否" if oos is False else "—"),
                        })
                    st.markdown("**進場門檻建議**（高原中心）")
                    st.dataframe(pd.DataFrame(rows), use_container_width=True,
                                 hide_index=True)
                    msc = next((p for p in ar["params"] if p["param"] == "min_score"), None)
                    atrp = next((p for p in ar["params"] if p["param"] == "atr_mult"), None)
                    if st.button("套用門檻建議並重掃", key="apply_adapt_thr",
                                 type="primary"):
                        applied = []
                        if msc and msc.get("recommended") is not None:
                            st.session_state["thr_enter"] = int(msc["recommended"])
                            applied.append(f"進場門檻={int(msc['recommended'])}")
                        if atrp and atrp.get("recommended") is not None:
                            st.session_state["f_atr_mult"] = float(atrp["recommended"])
                            applied.append(f"ATR×{atrp['recommended']}")
                        apply_and_rescan("已套用門檻：" + "、".join(applied) if applied else "無可套用建議")
                    st.caption("ℹ️ tp_mult 為回測停利框架參數，僅供回測參考，不影響即時掃描。")

                # --- 評分權重 ---
                w = ar.get("weights")
                if w and w.get("recommended"):
                    st.markdown("**評分權重建議**（因子 lift）")
                    _wl = {"breakout_with_volume": "突破+量", "ma_bullish": "均線多頭",
                           "turnover_strong": "換手率", "kd": "KD", "macd": "MACD",
                           "rel_strength": "相對強度", "trend_confirm": "趨勢確認"}
                    wrows = [{"因子": _wl.get(k, k), "目前": w["current"].get(k),
                              "建議": w["recommended"].get(k)} for k in w["recommended"]]
                    st.dataframe(pd.DataFrame(wrows), use_container_width=True,
                                 hide_index=True)
                    if w.get("note"):
                        st.caption(w["note"])
                    if st.button("套用權重建議並重掃", key="apply_adapt_w",
                                 type="primary"):
                        _m = {"breakout_with_volume": "w_breakout", "ma_bullish": "w_ma",
                              "turnover_strong": "w_turnover", "kd": "w_kd", "macd": "w_macd",
                              "rel_strength": "w_rs", "trend_confirm": "w_trend"}
                        for sc_key, ss_key in _m.items():
                            if sc_key in w["recommended"]:
                                st.session_state[ss_key] = int(w["recommended"][sc_key])
                        apply_and_rescan("已套用權重建議")

                # --- 隨大盤切門檻 ---
                rg = ar.get("regime")
                if rg and rg.get("by_regime"):
                    st.markdown("**隨大盤切門檻建議**（各盤勢最佳 min_score）")
                    lbl = rg.get("labels", {})
                    rrows = []
                    for k in ("bull", "neutral", "bear"):
                        v = rg["by_regime"].get(k, {})
                        rrows.append({
                            "大盤": lbl.get(k, k),
                            "建議進場門檻": v.get("recommended"),
                            "期望值R": v.get("expectancy") if not v.get("fallback") else "樣本不足→回退整體",
                            "樣本數": v.get("n"),
                        })
                    st.dataframe(pd.DataFrame(rrows), use_container_width=True,
                                 hide_index=True)
                    st.caption("套用後，每次掃描會**依當前大盤狀態自動選用**對應門檻（即時生效）。")
                    if st.button("套用『隨大盤切門檻』並重掃", key="apply_adapt_regime",
                                 type="primary"):
                        st.session_state["regime_thresholds"] = {
                            k: int(rg["by_regime"][k]["recommended"])
                            for k in ("bull", "neutral", "bear")
                            if rg["by_regime"].get(k, {}).get("recommended") is not None
                        }
                        apply_and_rescan("已啟用隨大盤切門檻")
                if st.session_state.get("regime_thresholds"):
                    _rt = st.session_state["regime_thresholds"]
                    st.success(f"隨大盤切門檻已啟用：{_rt}")
                    if st.button("停用隨大盤切門檻", key="clear_adapt_regime"):
                        st.session_state.pop("regime_thresholds", None)
                        st.rerun()

            # ===== 進階驗證工具（選用）=====
            st.divider()
            st.markdown("### 進階驗證工具（點按鈕才執行）")
            st.caption("日常只需上方『績效＋OOS＋壓力測試＋自動校準』；以下為深入研究用。")

            st.markdown("#### 參數高原圖")
            st.caption("掃一維參數看期望值曲線：**高原（一段都不錯）= 穩健**；**尖峰（只有一點好）= 過擬合**。建議取高原中點，別挑尖峰。")
            pl_param = st.radio(
                "掃描參數", ["min_score", "atr_mult", "tp_mult"],
                format_func=lambda x: {"min_score": "最低評分", "atr_mult": "ATR停損倍數", "tp_mult": "停利倍數"}[x],
                horizontal=True, key="plateau_param",
            )
            if st.button("跑高原圖", key="plateau_btn"):
                cfg = build_cfg()
                resolved = bt.get("resolved")
                if not resolved:
                    st.error("缺少回測資料 — 請重跑回測")
                else:
                    pcfg = base_cfg.get("sensitivity", {}).get("plateau", {})
                    grid = {
                        "min_score": pcfg.get("min_score_grid", [4, 5, 6, 7, 8]),
                        "atr_mult": pcfg.get("atr_mult_grid", [1.0, 1.5, 2.0, 2.5, 3.0]),
                        "tp_mult": pcfg.get("tp_mult_grid", [1.5, 2.0, 2.5, 3.0]),
                    }[pl_param]
                    bar4 = st.progress(0.0, text="高原掃描中 …")
                    def pl_cb(i, n, v):
                        bar4.progress(min(i / n, 1.0), text=f"{pl_param}={v}")
                    try:
                        st.session_state["plateau"] = run_plateau(
                            resolved, cfg, pl_param, grid,
                            int(bt_lookback), int(bt_hold), progress_cb=pl_cb,
                        )
                    except Exception as e:
                        st.error(f"高原圖失敗：{e}")

            if "plateau" in st.session_state:
                pl = st.session_state["plateau"]
                ptab = pl["table"]
                pinfo = pl["plateau"]
                fig_p = go.Figure()
                fig_p.add_trace(go.Scatter(
                    x=ptab["param_value"], y=ptab["期望值R"], mode="lines+markers",
                    name="期望值R", line=dict(color="#2563EB"),
                ))
                fig_p.add_trace(go.Scatter(
                    x=ptab["param_value"], y=pinfo["neighbor_min"], mode="lines",
                    name="鄰域最小", line=dict(color="#94A3B8", dash="dot"),
                ))
                if pinfo["plateau"]:
                    lo, hi, center = pinfo["plateau"]
                    fig_p.add_vrect(x0=lo, x1=hi, fillcolor="#2563EB", opacity=0.10, line_width=0)
                for pk in pinfo["peaks"]:
                    fig_p.add_trace(go.Scatter(
                        x=[ptab["param_value"].iloc[pk]], y=[ptab["期望值R"].iloc[pk]],
                        mode="markers", marker=dict(color="#B45309", size=12, symbol="x"),
                        name="尖峰(過擬合)", showlegend=False,
                    ))
                fig_p.update_layout(
                    height=300, margin=dict(l=8, r=8, t=8, b=8),
                    plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                    xaxis_title=pl["param_name"], yaxis_title="期望值 R",
                    font=dict(family="Inter, sans-serif", size=11),
                )
                fig_p.update_yaxes(showgrid=True, gridcolor="#F1F5F9")
                st.plotly_chart(fig_p, use_container_width=True, config={"displayModeBar": False})
                if pinfo["recommended"] is not None:
                    st.success(f"建議穩健參數（高原中點）：**{pinfo['recommended']}**（藍色區段）")
                else:
                    st.warning("找不到明顯高原 — 曲線可能過於起伏（樣本不足或策略不穩），勿挑單一尖峰")
                st.dataframe(ptab, use_container_width=True, hide_index=True)

            # ===== 因子增量貢獻驗證 =====
            st.markdown("#### 因子驗證：每個條件的貢獻")
            st.caption("逐棒比較「因子成立 vs 不成立」的未來平均 R；lift(R) > 0 才代表該因子真的提升期望值。減法用：lift ≈ 0 或負的因子可考慮砍掉或降權。")
            if st.button("跑因子驗證", key="factor_btn"):
                cfg = build_cfg()
                resolved = bt.get("resolved")
                if not resolved:
                    st.error("缺少回測資料 — 請重跑回測")
                else:
                    bar3 = st.progress(0.0, text="因子驗證中 …")
                    def fe_cb(stage, pct, msg):
                        bar3.progress(min(pct, 1.0), text=f"{stage}：{msg}")
                    try:
                        fe = run_factor_eval(
                            None, cfg, lookback_days=int(bt_lookback),
                            hold_days=int(bt_hold), resolved=resolved,
                            progress_cb=fe_cb,
                        )
                        st.session_state["factor_eval"] = fe
                    except Exception as e:
                        st.error(f"因子驗證失敗：{e}")

            if "factor_eval" in st.session_state:
                fe = st.session_state["factor_eval"]
                base = fe.get("base", {})
                if base:
                    fc = st.columns(3)
                    fc[0].metric("樣本數", fmt_int(base.get("樣本數", 0)))
                    fc[1].metric("整體平均 R", base.get("整體平均R", "—"))
                    fc[2].metric("整體勝率 %", f"{base.get('整體勝率%', '—')}%")
                tbl = fe.get("table")
                if tbl is not None and len(tbl):
                    st.dataframe(
                        tbl, use_container_width=True, hide_index=True,
                        column_config={
                            "lift(R)": st.column_config.NumberColumn(
                                "lift(R)", format="%.3f",
                                help="成立平均R − 不成立平均R；正值=該因子提升期望值"),
                        },
                    )
                    fig_f = go.Figure(go.Bar(
                        x=tbl["因子"], y=tbl["lift(R)"],
                        marker_color=[colors()["up"] if v > 0 else colors()["down"]
                                       for v in tbl["lift(R)"]],
                        text=[f"{v:.3f}" for v in tbl["lift(R)"]],
                        textposition="outside", marker_line_width=0,
                    ))
                    fig_f.update_layout(
                        height=260, margin=dict(l=8, r=8, t=8, b=8),
                        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                        showlegend=False, yaxis_title="lift(R)",
                        font=dict(family="Inter, sans-serif", size=11),
                    )
                    fig_f.update_xaxes(showgrid=False)
                    fig_f.update_yaxes(showgrid=True, gridcolor="#F1F5F9")
                    st.plotly_chart(fig_f, use_container_width=True,
                                     config={"displayModeBar": False})
                st.caption(fe.get("note", ""))

                # 套用 lift 建議權重（減法用）
                from twscanner.services import run_weight_suggest
                cfg = build_cfg()
                try:
                    sug = run_weight_suggest(cfg, fe_result=fe)
                except Exception:
                    sug = None
                if sug and sug.get("detail"):
                    st.markdown("#### 依 lift 建議權重")
                    st.dataframe(pd.DataFrame(sug["detail"]),
                                 use_container_width=True, hide_index=True)
                    st.caption(sug.get("note", ""))
                    if st.button("套用建議權重並重掃", key="apply_lift_weights",
                                 type="primary"):
                        _map = {
                            "breakout_with_volume": "w_breakout", "ma_bullish": "w_ma",
                            "turnover_strong": "w_turnover", "kd": "w_kd", "macd": "w_macd",
                            "rel_strength": "w_rs", "trend_confirm": "w_trend",
                        }
                        for sc_key, ss_key in _map.items():
                            if sc_key in sug["weights"]:
                                st.session_state[ss_key] = int(sug["weights"][sc_key])
                        apply_and_rescan("已套用建議權重")

                # 因子相關性矩陣
                corr = fe.get("corr")
                if corr is not None and len(corr):
                    st.markdown("#### 因子相關性矩陣")
                    st.caption("phi 接近 ±1 = 兩因子高度重複（資訊冗餘）。重複群只需保留一個。")
                    fig_h = go.Figure(go.Heatmap(
                        z=corr.values, x=list(corr.columns), y=list(corr.index),
                        colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
                        text=[[f"{v:.2f}" for v in row] for row in corr.values],
                        texttemplate="%{text}", showscale=True,
                    ))
                    fig_h.update_layout(height=340, margin=dict(l=8, r=8, t=8, b=8),
                                        font=dict(family="Inter, sans-serif", size=10))
                    st.plotly_chart(fig_h, use_container_width=True,
                                     config={"displayModeBar": False})
                    if fe.get("groups"):
                        for g in fe["groups"]:
                            st.info(f"重複群 {g['成員']} → 建議保留 **{g['建議保留']}**，"
                                    f"合併/降權：{', '.join(g['建議合併'])}")
                    else:
                        st.caption("未發現高度重複因子群（門檻內）。")
        else:
            st.warning("回測無任何交易產生 — 試試降低「最低評分」門檻")
