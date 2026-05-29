"""
台股強勢突破掃描器 — Streamlit GUI

啟動：
    uv run streamlit run app.py
"""
import copy
import io
import logging
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import load_config
from src.report import write_excel
from src.runner import run_backtest, run_holdings_scan, run_scan
from src.universe import fetch_twse_universe


# =====================================================
# 頁面設定
# =====================================================
st.set_page_config(
    page_title="台股強勢突破掃描器",
    page_icon="📈",
    layout="wide",
)

st.title("📈 台股強勢突破交易清單掃描器")
st.caption("加權評分 + 品質過濾 + 換手率分析")


# =====================================================
# 載入基底 config
# =====================================================
@st.cache_data
def get_base_config():
    return load_config("config.yaml")


base_cfg = get_base_config()


# =====================================================
# 側欄：上傳檔案 + 參數調整
# =====================================================
with st.sidebar:
    st.header("⚙️ 設定")

    mode = st.radio(
        "資料來源",
        ["上傳清單", "掃描全台股"],
        horizontal=True,
    )

    uploaded = None
    use_default = False
    universe_kind = "twse"

    if mode == "上傳清單":
        uploaded = st.file_uploader(
            "上傳股票清單 (xlsx)",
            type=["xlsx"],
            help="欄位需含「股票代號」與「公司名稱」",
        )
        use_default = st.checkbox(
            "使用專案內 stock_list.xlsx",
            value=not uploaded,
            disabled=bool(uploaded),
        )
    else:
        universe_kind = st.selectbox(
            "範圍",
            ["twse", "twse-common", "twse-etf"],
            format_func=lambda x: {
                "twse": "上市普通股 + ETF",
                "twse-common": "僅普通股",
                "twse-etf": "僅 ETF",
            }[x],
        )
        st.caption("⏱️ 全市場掃描首次約 5~15 分鐘；同日重跑 < 1 分鐘（快取）")

    st.divider()
    st.subheader("💰 部位管理")

    ps = base_cfg.get("position_sizing", {})
    total_capital = st.number_input(
        "總資金（元）", min_value=100_000,
        value=int(ps.get("total_capital", 1_000_000)),
        step=100_000,
    )
    risk_pct = st.slider(
        "單筆風險%", 0.5, 5.0,
        float(ps.get("risk_per_trade_pct", 0.01)) * 100, 0.25,
    ) / 100
    max_pos_pct = st.slider(
        "單檔最大佔比%", 5, 50,
        int(ps.get("max_position_pct", 0.20) * 100), 5,
    ) / 100

    st.divider()
    st.subheader("品質過濾")

    f = base_cfg["filters"]
    min_price = st.number_input(
        "最低股價", min_value=0.0, value=float(f["min_price"]), step=1.0,
    )
    min_avg_volume = st.number_input(
        "20 日均量下限（股）", min_value=0,
        value=int(f["min_avg_volume"]), step=100_000,
        help="500,000 股 = 500 張",
    )
    require_ma60 = st.checkbox(
        "必須站上 MA60", value=bool(f.get("require_above_ma60", True)),
    )
    min_risk_pct = st.slider(
        "最小停損距離（%）", 0.0, 10.0,
        float(f.get("min_risk_pct", 0.02)) * 100, 0.5,
    ) / 100

    st.divider()
    st.subheader("評分權重")

    w = base_cfg["scoring"]["weights"]
    w_breakout = st.slider("突破+量增", 0, 5, int(w["breakout_with_volume"]))
    w_ma = st.slider("MA 多頭", 0, 5, int(w["ma_bullish"]))
    w_turnover = st.slider("換手率強勢", 0, 5, int(w["turnover_strong"]))
    w_kd = st.slider("KD", 0, 5, int(w["kd"]))
    w_macd = st.slider("MACD", 0, 5, int(w["macd"]))

    max_total = w_breakout + w_ma + w_turnover + w_kd + w_macd
    st.caption(f"總分上限：**{max_total}**")

    st.divider()
    st.subheader("分級門檻")

    thr = base_cfg["scoring"]["thresholds"]
    thr_strong = st.number_input("強勢候選 ≥", 0, 20, int(thr["strong"]))
    thr_watch = st.number_input("觀察 ≥", 0, 20, int(thr["watch"]))
    thr_weak = st.number_input("偏弱觀察 ≥", 0, 20, int(thr["weak"]))

    st.divider()
    run_btn = st.button("🚀 開始掃描", type="primary", use_container_width=True)

    st.divider()
    st.subheader("🔁 回測")
    bt_lookback = st.number_input("回測天數", 30, 500, 120, 30)
    bt_hold = st.number_input("持有天數", 3, 60, 10, 1)
    bt_min_score = st.number_input("回測最低評分", 0, 20, 5, 1)
    run_bt_btn = st.button("🔁 跑回測", use_container_width=True)

    st.divider()
    st.subheader("📦 持股管理")
    holdings_file = st.file_uploader(
        "持股 Excel (holdings.xlsx)",
        type=["xlsx"], key="holdings_uploader",
        help="欄位：股票代號 / 公司名稱 / 進場價 / 進場日 / 持有張數",
    )
    use_default_holdings = st.checkbox(
        "使用 holdings.example.xlsx 範例",
        value=not holdings_file,
    )
    run_holdings_btn = st.button("📊 分析持股", use_container_width=True)


# =====================================================
# 組裝 effective config
# =====================================================
def build_cfg():
    cfg = copy.deepcopy(base_cfg)
    cfg["filters"]["min_price"] = min_price
    cfg["filters"]["min_avg_volume"] = int(min_avg_volume)
    cfg["filters"]["require_above_ma60"] = require_ma60
    cfg["filters"]["min_risk_pct"] = min_risk_pct
    cfg["scoring"]["weights"] = {
        "breakout_with_volume": w_breakout,
        "ma_bullish": w_ma,
        "turnover_strong": w_turnover,
        "kd": w_kd,
        "macd": w_macd,
    }
    cfg["scoring"]["thresholds"] = {
        "strong": thr_strong, "watch": thr_watch, "weak": thr_weak,
    }
    cfg["position_sizing"] = {
        "total_capital": int(total_capital),
        "risk_per_trade_pct": risk_pct,
        "lot_size": 1000,
        "max_position_pct": max_pos_pct,
    }
    return cfg


# =====================================================
# Log handler → streamlit
# =====================================================
class StListHandler(logging.Handler):
    def __init__(self, buf):
        super().__init__()
        self.buf = buf

    def emit(self, record):
        self.buf.append(self.format(record))


# =====================================================
# 執行掃描
# =====================================================
if run_btn:
    input_path = None
    items = None

    if mode == "掃描全台股":
        try:
            with st.spinner("抓取全台股清單 ..."):
                raw = fetch_twse_universe(
                    include_common=universe_kind in ("twse", "twse-common"),
                    include_etf=universe_kind in ("twse", "twse-etf"),
                )
            items = [{"code": x["code"], "company_name": x["company_name"]} for x in raw]
            st.info(f"📌 將掃描 **{len(items)}** 檔")
        except Exception as e:
            st.error(f"抓取全台股清單失敗：{e}")
            st.stop()
    elif uploaded:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        tmp.write(uploaded.getvalue())
        tmp.close()
        input_path = tmp.name
    elif use_default and Path("stock_list.xlsx").exists():
        input_path = "stock_list.xlsx"
    else:
        st.error("請上傳股票清單，或勾選『使用專案內 stock_list.xlsx』")
        st.stop()

    cfg = build_cfg()

    # 進度顯示
    progress_bar = st.progress(0.0, text="準備中 ...")
    log_expander = st.expander("📋 執行記錄", expanded=True)
    log_area = log_expander.empty()
    log_buffer = []

    # 接 logger
    handler = StListHandler(log_buffer)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s",
                                            datefmt="%H:%M:%S"))
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    def on_progress(stage, pct, msg):
        progress_bar.progress(min(pct, 1.0), text=f"{stage} — {msg}")
        log_area.code("\n".join(log_buffer[-30:]) or "（執行中...）")

    try:
        with st.spinner("掃描中 ..."):
            result = run_scan(
                input_path=input_path, cfg=cfg,
                progress_cb=on_progress, items=items,
            )
    except Exception as e:
        st.error(f"執行失敗：{e}")
        st.exception(e)
        st.stop()
    finally:
        root_logger.removeHandler(handler)
        log_area.code("\n".join(log_buffer[-30:]))

    progress_bar.progress(1.0, text=f"完成（{result['elapsed_sec']:.1f} 秒）")

    # 存入 session 供後續篩選互動
    st.session_state["result"] = result
    st.session_state["cfg"] = cfg


# =====================================================
# 持股分析
# =====================================================
if run_holdings_btn:
    if holdings_file:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        tmp.write(holdings_file.getvalue())
        tmp.close()
        h_path = tmp.name
    elif use_default_holdings and Path("holdings.example.xlsx").exists():
        h_path = "holdings.example.xlsx"
    else:
        st.error("請上傳持股 Excel")
        st.stop()

    cfg = build_cfg()

    h_progress = st.progress(0.0, text="持股分析準備中 ...")
    h_log_area = st.expander("📋 持股分析記錄", expanded=False).empty()
    h_buffer = []
    h_handler = StListHandler(h_buffer)
    h_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s",
                                              datefmt="%H:%M:%S"))
    logging.getLogger().addHandler(h_handler)

    def h_progress_cb(stage, pct, msg):
        h_progress.progress(min(pct, 1.0), text=f"{stage} — {msg}")
        h_log_area.code("\n".join(h_buffer[-30:]) or "（執行中...）")

    try:
        with st.spinner("持股分析中 ..."):
            h_result = run_holdings_scan(h_path, cfg, progress_cb=h_progress_cb)
        st.session_state["holdings_result"] = h_result
    except Exception as e:
        st.error(f"持股分析失敗：{e}")
        st.exception(e)
    finally:
        logging.getLogger().removeHandler(h_handler)
    h_progress.progress(1.0, text="持股分析完成")


# =====================================================
# 回測
# =====================================================
if run_bt_btn:
    bt_items = None
    bt_input = None

    if mode == "掃描全台股":
        try:
            with st.spinner("抓清單 ..."):
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
    elif use_default and Path("stock_list.xlsx").exists():
        bt_input = "stock_list.xlsx"
    else:
        st.error("請先設定股票來源（左側）")
        st.stop()

    cfg = build_cfg()
    bt_progress = st.progress(0.0, text="回測準備中 ...")
    bt_log_area = st.expander("📋 回測記錄", expanded=False).empty()
    bt_buffer = []
    bt_handler = StListHandler(bt_buffer)
    bt_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s",
                                               datefmt="%H:%M:%S"))
    logging.getLogger().addHandler(bt_handler)

    def bt_progress_cb(stage, pct, msg):
        bt_progress.progress(min(pct, 1.0), text=f"{stage} — {msg}")
        bt_log_area.code("\n".join(bt_buffer[-30:]) or "（執行中...）")

    try:
        with st.spinner("回測中 ..."):
            bt_result = run_backtest(
                bt_input, cfg,
                lookback_days=int(bt_lookback),
                hold_days=int(bt_hold),
                min_score=int(bt_min_score),
                items=bt_items,
                progress_cb=bt_progress_cb,
            )
        st.session_state["backtest_result"] = bt_result
    except Exception as e:
        st.error(f"回測失敗：{e}")
        st.exception(e)
    finally:
        logging.getLogger().removeHandler(bt_handler)
    bt_progress.progress(1.0, text="回測完成")


# =====================================================
# 結果顯示
# =====================================================
tab1, tab2, tab3 = st.tabs(["🔍 買入掃描", "📦 持股管理", "🔁 回測"])

with tab3:
    if "backtest_result" not in st.session_state:
        st.info("👈 從左側「跑回測」啟動")
    else:
        bt = st.session_state["backtest_result"]
        s = bt["summary"]

        st.subheader("📊 回測摘要")
        c = st.columns(4)
        c[0].metric("總交易數", s["總交易數"])
        c[1].metric("勝率%", s["勝率%"])
        c[2].metric("平均報酬%", s["平均報酬%"])
        c[3].metric("期望值R", s["期望值R"])
        c2 = st.columns(3)
        c2[0].metric("平均R", s["平均R"])
        c2[1].metric("最大單筆%", s["最大單筆%"])
        c2[2].metric("最大回撤R", s["最大回撤R"])

        if len(bt["by_symbol"]):
            st.subheader("🏆 個股期望值排序")
            st.dataframe(bt["by_symbol"], use_container_width=True, height=300)

        if len(bt["trades"]):
            st.subheader("📋 交易明細")
            st.dataframe(bt["trades"], use_container_width=True, height=400)

            buf_bt = io.BytesIO()
            with pd.ExcelWriter(buf_bt, engine="openpyxl") as writer:
                pd.DataFrame([s]).to_excel(writer, sheet_name="摘要", index=False)
                bt["trades"].to_excel(writer, sheet_name="交易明細", index=False)
                if len(bt["by_symbol"]):
                    bt["by_symbol"].to_excel(writer, sheet_name="個股統計", index=False)
            buf_bt.seek(0)
            st.download_button(
                "⬇️ 下載回測報告",
                data=buf_bt.getvalue(),
                file_name="回測報告.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

with tab2:
    if "holdings_result" not in st.session_state:
        st.info("👈 從左側上傳 holdings.xlsx 後點「分析持股」")
    else:
        h_df = st.session_state["holdings_result"]["df"]

        # 摘要：各類建議檔數
        action_counts = h_df["操作建議"].value_counts() if "操作建議" in h_df.columns else {}
        st.subheader("📊 持股操作摘要")
        cols = st.columns(min(len(action_counts), 6) or 1)
        for i, (action, cnt) in enumerate(action_counts.items()):
            cols[i % len(cols)].metric(action, cnt)

        st.subheader("📋 持股清單")
        st.dataframe(h_df, use_container_width=True, height=400)

        # 下載
        h_buf = io.BytesIO()
        with pd.ExcelWriter(h_buf, engine="openpyxl") as writer:
            h_df.to_excel(writer, sheet_name="持股賣出建議", index=False)
        h_buf.seek(0)
        st.download_button(
            "⬇️ 下載持股報告",
            data=h_buf.getvalue(),
            file_name="持股賣出建議.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

with tab1:
    if "result" not in st.session_state:
        st.info("👈 從左側設定參數後點「開始掃描」")
    else:
        result = st.session_state["result"]
        df = result["df"]
        summary = result["summary"]
        failed_df = result["failed_df"]
        market_state = result.get("market_state")

        # 大盤狀態橫幅
        if market_state:
            regime = market_state["regime"]
            if regime == "bull":
                st.success(f"**大盤：{market_state['label']}** — {market_state['detail']}")
            elif regime == "bear":
                st.error(f"**大盤：{market_state['label']}** — {market_state['detail']}")
            else:
                st.warning(f"**大盤：{market_state['label']}** — {market_state['detail']}")

        # 摘要
        st.subheader("📊 摘要")
        cols = st.columns(6)
        s = summary.iloc[0]
        cols[0].metric("掃描", s["掃描股票數"])
        cols[1].metric("成功", s["成功分析檔數"])
        cols[2].metric("強勢候選", s["強勢候選檔數"])
        cols[3].metric("觀察", s["觀察檔數"])
        cols[4].metric("偏弱", s["偏弱觀察檔數"])
        cols[5].metric("耗時(秒)", s["執行秒數"])

        # 篩選列
        st.subheader("📋 分析結果")
        fcol1, fcol2, fcol3 = st.columns([2, 2, 1])

        signal_options = ["強勢候選", "觀察", "偏弱觀察", "不符合", "無法分析"]
        available_signals = [
            s for s in signal_options
            if "訊號判斷" in df.columns and (df["訊號判斷"] == s).any()
        ]
        default_signals = [s for s in ["強勢候選", "觀察"] if s in available_signals]

        sel_signals = fcol1.multiselect(
            "訊號判斷", options=available_signals, default=default_signals or available_signals,
        )

        max_score = int(df["評分"].max()) if len(df) and "評分" in df.columns else 8
        min_score_filter = fcol2.slider("最低評分", 0, max_score, 0)
        keyword = fcol3.text_input("搜尋股票/公司")

        filtered = df.copy()
        if "訊號判斷" in filtered.columns and sel_signals:
            filtered = filtered[filtered["訊號判斷"].isin(sel_signals)]
        if "評分" in filtered.columns:
            filtered = filtered[filtered["評分"] >= min_score_filter]
        if keyword:
            k = keyword.strip()
            mask = (
                filtered.get("股票", pd.Series(dtype=str)).astype(str).str.contains(k, case=False, na=False)
                | filtered.get("公司名稱", pd.Series(dtype=str)).astype(str).str.contains(k, case=False, na=False)
            )
            filtered = filtered[mask]

        st.caption(f"顯示 {len(filtered)} / {len(df)} 筆")

        priority_cols = [
            "股票", "公司名稱", "市場", "操作建議", "訊號判斷", "評分",
            "進場類型", "進場條件",
            "建議張數", "進場成本", "佔資金%", "部位提示",
            "收盤價", "進場參考價", "停損價",
            "目標價1(+1R半倉)", "目標價2(+2R出清)",
            "風險%", "RR比",
            "換手率%", "20日平均換手率%",
            "MA5", "MA20", "MA60", "K", "D", "OSC",
            "成交量", "20日均量",
            "突破+量增", "MA多頭", "換手率強勢", "KD強勢", "MACD多方",
            "大盤狀態", "狀態",
        ]
        show_cols = [c for c in priority_cols if c in filtered.columns]
        other_cols = [c for c in filtered.columns if c not in show_cols]
        display = filtered[show_cols + other_cols]

        st.dataframe(display, use_container_width=True, height=500)

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
            "⬇️ 下載 Excel 報告",
            data=buf.getvalue(),
            file_name="台股分析報告.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        if dl_col2.button("💾 寫入專案目錄", use_container_width=True):
            cfg = st.session_state.get("cfg", base_cfg)
            out = cfg["output"]
            path = write_excel(df, summary, failed_df, out["dir"], out["prefix"])
            st.success(f"已輸出：{path}")

        if failed_df is not None and len(failed_df) > 0:
            with st.expander(f"❌ 錯誤清單（{len(failed_df)} 筆）"):
                st.dataframe(failed_df, use_container_width=True)
