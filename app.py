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
from src.runner import run_scan


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
    # 決定 input 路徑
    if uploaded:
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
            result = run_scan(input_path, cfg, progress_cb=on_progress)
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
# 結果顯示
# =====================================================
if "result" in st.session_state:
    result = st.session_state["result"]
    df = result["df"]
    summary = result["summary"]
    failed_df = result["failed_df"]

    st.divider()

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
    min_score_filter = fcol2.slider(
        "最低評分", 0, max_score, 0,
    )

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

    # 優先顯示的關鍵欄位
    priority_cols = [
        "股票", "公司名稱", "市場", "訊號判斷", "評分", "狀態",
        "收盤價", "停損價", "目標價", "風險%", "RR比",
        "換手率%", "20日平均換手率%",
        "MA5", "MA20", "MA60", "K", "D", "OSC",
        "成交量", "20日均量",
        "突破+量增", "MA多頭", "換手率強勢", "KD強勢", "MACD多方",
    ]
    show_cols = [c for c in priority_cols if c in filtered.columns]
    other_cols = [c for c in filtered.columns if c not in show_cols]
    display = filtered[show_cols + other_cols]

    st.dataframe(display, use_container_width=True, height=500)

    # 匯出按鈕
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

    # 失敗清單
    if failed_df is not None and len(failed_df) > 0:
        with st.expander(f"❌ 錯誤清單（{len(failed_df)} 筆）"):
            st.dataframe(failed_df, use_container_width=True)

else:
    st.info("👈 從左側設定參數後點「開始掃描」")
