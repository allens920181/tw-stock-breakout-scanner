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
from src.fetcher import fix_stock_code
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
    initial_sidebar_state="expanded",
    menu_items={
        "About": "**台股強勢突破掃描器** v0.3\n\n加權評分 + 品質過濾 + 換手率分析 + 操作建議"
    },
)


# =====================================================
# 全域 CSS
# =====================================================
st.markdown("""
<style>
    /* 隱藏 Streamlit 預設 footer/menu，視覺更乾淨 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* 縮減 block 間距 */
    .block-container {padding-top: 1.5rem; padding-bottom: 1rem;}

    /* metric 卡片美化 */
    [data-testid="stMetric"] {
        background: #FFFFFF;
        padding: 12px 16px;
        border-radius: 8px;
        border: 1px solid #E5E7EB;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    [data-testid="stMetricLabel"] {color: #64748B; font-size: 0.85rem;}
    [data-testid="stMetricValue"] {font-size: 1.5rem; font-weight: 600;}

    /* 強勢候選卡片 */
    .candidate-card {
        background: #FFFFFF;
        border-left: 4px solid #16A34A;
        border-radius: 6px;
        padding: 14px 18px;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .candidate-card.watch {border-left-color: #F59E0B;}
    .candidate-card.skip {border-left-color: #94A3B8;}

    .card-title {font-size: 1rem; font-weight: 700; margin-bottom: 4px;}
    .card-meta {color: #64748B; font-size: 0.85rem; margin-bottom: 8px;}
    .card-row {display: flex; gap: 16px; font-size: 0.9rem;}
    .card-row span b {color: #0F172A;}

    /* 大盤橫幅 */
    .market-banner {
        padding: 12px 16px;
        border-radius: 8px;
        margin: 0 0 16px 0;
        font-weight: 500;
    }
    .market-bull {background: #DCFCE7; color: #15803D; border-left: 4px solid #16A34A;}
    .market-bear {background: #FEE2E2; color: #B91C1C; border-left: 4px solid #DC2626;}
    .market-neutral {background: #FEF3C7; color: #B45309; border-left: 4px solid #F59E0B;}
    .market-unknown {background: #F1F5F9; color: #475569; border-left: 4px solid #94A3B8;}

    /* tabs 樣式 */
    .stTabs [data-baseweb="tab"] {font-size: 1rem; font-weight: 500;}

    /* 表格圓角 */
    [data-testid="stDataFrame"] {border-radius: 6px;}
</style>
""", unsafe_allow_html=True)


# =====================================================
# 頁首
# =====================================================
header_left, header_right = st.columns([3, 1])
with header_left:
    st.markdown(
        "<h1 style='margin-bottom: 0;'>📈 台股強勢突破掃描器</h1>"
        "<p style='color:#64748B; margin-top: 4px;'>加權評分 · 換手率分析 · 操作建議</p>",
        unsafe_allow_html=True,
    )
with header_right:
    st.markdown(
        "<p style='text-align:right; color:#94A3B8; font-size:0.85rem; margin-top:24px;'>"
        f"📅 {pd.Timestamp.today().strftime('%Y-%m-%d %A')}</p>",
        unsafe_allow_html=True,
    )


# =====================================================
# 載入基底 config
# =====================================================
@st.cache_data
def get_base_config():
    return load_config("config.yaml")


base_cfg = get_base_config()


# =====================================================
# 側欄：分組
# =====================================================
with st.sidebar:
    st.markdown("### ⚙️ 設定")

    # —— 資料來源 ——
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
                "twse": "上市普通股 + ETF (~1180檔)",
                "twse-common": "僅普通股 (~1030)",
                "twse-etf": "僅 ETF (~150)",
            }[x],
        )
        st.caption("⏱️ 首次約 5~15 分鐘；同日重跑 < 1 分鐘")

    st.markdown("")
    run_btn = st.button(
        "🚀 開始掃描", type="primary", use_container_width=True,
    )

    st.divider()

    # —— 部位管理 ——
    with st.expander("💰 部位管理", expanded=True):
        ps = base_cfg.get("position_sizing", {})
        total_capital = st.number_input(
            "總資金（元）", min_value=100_000,
            value=int(ps.get("total_capital", 1_000_000)),
            step=100_000,
        )
        risk_pct = st.slider(
            "單筆風險%", 0.5, 5.0,
            float(ps.get("risk_per_trade_pct", 0.01)) * 100, 0.25,
            help="每筆交易最大可接受虧損 = 總資金 × 此比例",
        ) / 100
        max_pos_pct = st.slider(
            "單檔最大佔比%", 5, 50,
            int(ps.get("max_position_pct", 0.20) * 100), 5,
        ) / 100

    # —— 過濾 ——
    with st.expander("🔍 品質過濾", expanded=False):
        f = base_cfg["filters"]
        min_price = st.number_input(
            "最低股價", min_value=0.0,
            value=float(f["min_price"]), step=1.0,
        )
        min_avg_volume = st.number_input(
            "20日均量下限（股）", min_value=0,
            value=int(f["min_avg_volume"]), step=100_000,
            help="500,000 股 = 500 張",
        )
        require_ma60 = st.checkbox(
            "必須站上 MA60",
            value=bool(f.get("require_above_ma60", True)),
        )
        min_risk_pct = st.slider(
            "最小停損距離（%）", 0.0, 10.0,
            float(f.get("min_risk_pct", 0.02)) * 100, 0.5,
        ) / 100

    # —— 評分 ——
    with st.expander("⚖️ 評分權重 / 門檻", expanded=False):
        w = base_cfg["scoring"]["weights"]
        w_breakout = st.slider("突破 + 量增", 0, 5, int(w["breakout_with_volume"]))
        w_ma = st.slider("MA 多頭", 0, 5, int(w["ma_bullish"]))
        w_turnover = st.slider("換手率強勢", 0, 5, int(w["turnover_strong"]))
        w_kd = st.slider("KD", 0, 5, int(w["kd"]))
        w_macd = st.slider("MACD", 0, 5, int(w["macd"]))

        max_total = w_breakout + w_ma + w_turnover + w_kd + w_macd
        st.caption(f"總分上限：**{max_total}**")

        thr = base_cfg["scoring"]["thresholds"]
        thr_strong = st.number_input("🟢 強勢候選 ≥", 0, 20, int(thr["strong"]))
        thr_watch = st.number_input("🟡 觀察 ≥", 0, 20, int(thr["watch"]))
        thr_weak = st.number_input("⚪ 偏弱觀察 ≥", 0, 20, int(thr["weak"]))

    # —— 回測 ——
    with st.expander("🔁 回測設定", expanded=False):
        bt_lookback = st.number_input("回測天數", 30, 500, 120, 30)
        bt_hold = st.number_input("持有天數", 3, 60, 10, 1)
        bt_min_score = st.number_input("最低評分", 0, 20, 5, 1)
        run_bt_btn = st.button("🔁 跑回測", use_container_width=True)


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
# Log handler
# =====================================================
class StListHandler(logging.Handler):
    def __init__(self, buf):
        super().__init__()
        self.buf = buf

    def emit(self, record):
        self.buf.append(self.format(record))


def make_progress_block(title):
    """建立 progress bar + log expander"""
    bar = st.progress(0.0, text=f"{title} 準備中 ...")
    log_area = st.expander("📋 執行記錄", expanded=False).empty()
    buf = []
    handler = StListHandler(buf)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S",
    ))
    return bar, log_area, buf, handler


def render_market_banner(market_state):
    if not market_state:
        return
    regime = market_state["regime"]
    cls = {
        "bull": "market-bull",
        "bear": "market-bear",
        "neutral": "market-neutral",
    }.get(regime, "market-unknown")
    st.markdown(
        f"<div class='market-banner {cls}'>"
        f"<b>大盤狀態：{market_state['label']}</b> &nbsp;·&nbsp; {market_state['detail']}"
        f"</div>",
        unsafe_allow_html=True,
    )


# =====================================================
# 執行買入掃描
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
    bar, log_area, buf, handler = make_progress_block("掃描")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    def on_progress(stage, pct, msg):
        bar.progress(min(pct, 1.0), text=f"{stage} — {msg}")
        log_area.code("\n".join(buf[-30:]) or "（執行中...）")

    try:
        with st.spinner("掃描中 ..."):
            result = run_scan(
                input_path=input_path, cfg=cfg,
                progress_cb=on_progress, items=items,
            )
        st.session_state["result"] = result
        st.session_state["cfg"] = cfg
    except Exception as e:
        st.error(f"掃描失敗：{e}")
        st.exception(e)
        st.stop()
    finally:
        root.removeHandler(handler)
    bar.progress(1.0, text=f"完成（{result['elapsed_sec']:.1f} 秒）")


# =====================================================
# 執行回測
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
    bar, log_area, buf, handler = make_progress_block("回測")
    logging.getLogger().addHandler(handler)

    def bt_progress_cb(stage, pct, msg):
        bar.progress(min(pct, 1.0), text=f"{stage} — {msg}")
        log_area.code("\n".join(buf[-30:]) or "（執行中...）")

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
        logging.getLogger().removeHandler(handler)
    bar.progress(1.0, text="回測完成")


# =====================================================
# 大盤狀態橫幅（永久顯示在頂部）
# =====================================================
if "result" in st.session_state:
    render_market_banner(st.session_state["result"].get("market_state"))


# =====================================================
# 主分頁
# =====================================================
tab1, tab2, tab3 = st.tabs([
    "🔍 買入掃描",
    "📦 持股管理",
    "🔁 回測",
])


# =====================================================
# Tab 1：買入掃描
# =====================================================
def render_top_candidates(df, n=10):
    """卡片視圖：Top N 強勢候選"""
    if "訊號判斷" not in df.columns:
        return

    top = df[df["訊號判斷"] == "強勢候選"].head(n)
    if len(top) == 0:
        st.info("目前無強勢候選")
        return

    st.markdown("### 🏆 Top 強勢候選")

    for _, row in top.iterrows():
        action = row.get("操作建議", "")
        css_cls = "candidate-card"
        if "買入" in str(action):
            css_cls += ""  # 預設綠
        elif "觀察" in str(action):
            css_cls += " watch"
        else:
            css_cls += " skip"

        entry = row.get("進場參考價", "—")
        stop = row.get("停損價", "—")
        t1 = row.get("目標價1(+1R半倉)", "—")
        t2 = row.get("目標價2(+2R出清)", "—")
        risk_pct_val = row.get("風險%", "—")
        lots = row.get("建議張數", "—")
        cost_pct = row.get("佔資金%", 0)
        turnover = row.get("換手率%", None)
        score = row.get("評分", "—")
        entry_type = row.get("進場類型", "—")
        warning = row.get("部位提示", "")

        # 換手率呈現
        tr_str = f"{turnover}%" if turnover is not None and pd.notna(turnover) else "—"

        st.markdown(
            f"""
<div class='{css_cls}'>
  <div class='card-title'>{row['股票']} {row['公司名稱']} &nbsp;<span style='color:#64748B; font-weight:400;'>· 評分 {score} · {entry_type}</span></div>
  <div class='card-meta'>{action}{('  ⚠️ ' + warning) if warning else ''}</div>
  <div class='card-row'>
    <span>進場 <b>{entry}</b></span>
    <span>停損 <b>{stop}</b></span>
    <span>目標1 <b>{t1}</b></span>
    <span>目標2 <b>{t2}</b></span>
    <span>風險 <b>{risk_pct_val}%</b></span>
    <span>建議 <b>{lots} 張</b> ({cost_pct}%)</span>
    <span>換手 <b>{tr_str}</b></span>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )


def render_results_table(df, key_prefix=""):
    """完整結果表 + 篩選"""
    fcol1, fcol2, fcol3 = st.columns([2, 2, 1])

    signal_options = ["強勢候選", "觀察", "偏弱觀察", "不符合", "無法分析"]
    available_signals = [
        s for s in signal_options
        if "訊號判斷" in df.columns and (df["訊號判斷"] == s).any()
    ]
    default_signals = [s for s in ["強勢候選", "觀察"] if s in available_signals]

    sel_signals = fcol1.multiselect(
        "訊號判斷", options=available_signals,
        default=default_signals or available_signals,
        key=f"{key_prefix}sig",
    )
    max_score = int(df["評分"].max()) if len(df) and "評分" in df.columns else 8
    min_score_filter = fcol2.slider(
        "最低評分", 0, max_score, 0, key=f"{key_prefix}minsc",
    )
    keyword = fcol3.text_input("搜尋", placeholder="股票或公司名",
                                key=f"{key_prefix}kw")

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

    # column_config 美化
    col_cfg = {}
    if "評分" in display.columns:
        col_cfg["評分"] = st.column_config.ProgressColumn(
            "評分", format="%d", min_value=0,
            max_value=int(display["評分"].max()) if len(display) else 8,
        )
    if "風險%" in display.columns:
        col_cfg["風險%"] = st.column_config.NumberColumn(
            "風險%", format="%.2f%%",
        )
    if "佔資金%" in display.columns:
        col_cfg["佔資金%"] = st.column_config.NumberColumn(
            "佔資金%", format="%.2f%%",
        )
    if "換手率%" in display.columns:
        col_cfg["換手率%"] = st.column_config.NumberColumn(
            "換手率%", format="%.2f%%",
        )
    if "進場成本" in display.columns:
        col_cfg["進場成本"] = st.column_config.NumberColumn(
            "進場成本", format="%d",
        )

    st.dataframe(
        display, use_container_width=True, height=500,
        column_config=col_cfg, hide_index=True,
    )

    return filtered


with tab1:
    if "result" not in st.session_state:
        st.info("👈 從側欄設定資料來源後點「**🚀 開始掃描**」")
    else:
        result = st.session_state["result"]
        df = result["df"]
        summary = result["summary"]
        failed_df = result["failed_df"]

        # KPI 卡片
        s = summary.iloc[0]
        cols = st.columns(6)
        cols[0].metric("掃描", s["掃描股票數"])
        cols[1].metric("成功", s["成功分析檔數"])
        cols[2].metric("🟢 強勢候選", s["強勢候選檔數"])
        cols[3].metric("🟡 觀察", s["觀察檔數"])
        cols[4].metric("⚪ 偏弱", s["偏弱觀察檔數"])
        cols[5].metric("耗時 (秒)", s["執行秒數"])

        st.markdown("")

        # Top 候選卡片
        render_top_candidates(df, n=10)

        st.divider()

        # 詳細表格
        st.markdown("### 📋 完整結果")
        filtered = render_results_table(df, key_prefix="scan_")

        # 匯出
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
                st.dataframe(failed_df, use_container_width=True, hide_index=True)


# =====================================================
# Tab 2：持股管理
# =====================================================
with tab2:
    st.markdown("### 📦 我的持股")
    st.caption("直接在表格內編輯。儲存在瀏覽器 session，刷新會清空 → 記得「⬇️ 匯出」備份。")

    # 初始化
    if "holdings_df" not in st.session_state:
        st.session_state["holdings_df"] = pd.DataFrame([
            {"股票代號": "", "公司名稱": "", "進場價": 0.0,
             "進場日": pd.Timestamp.today().normalize(), "持有張數": 1},
        ])

    # 工具列
    tb = st.columns([1, 1, 1, 1, 2])
    if tb[0].button("➕ 新增列", use_container_width=True):
        new_row = pd.DataFrame([{
            "股票代號": "", "公司名稱": "", "進場價": 0.0,
            "進場日": pd.Timestamp.today().normalize(), "持有張數": 1,
        }])
        st.session_state["holdings_df"] = pd.concat(
            [st.session_state["holdings_df"], new_row], ignore_index=True,
        )
        st.rerun()
    if tb[1].button("📂 載入範例", use_container_width=True):
        if Path("holdings.example.xlsx").exists():
            ex = pd.read_excel("holdings.example.xlsx")
            ex["進場日"] = pd.to_datetime(ex["進場日"])
            st.session_state["holdings_df"] = ex
            st.rerun()
        else:
            st.warning("找不到 holdings.example.xlsx")
    if tb[2].button("🗑️ 清空", use_container_width=True):
        st.session_state["holdings_df"] = pd.DataFrame(columns=[
            "股票代號", "公司名稱", "進場價", "進場日", "持有張數",
        ])
        st.rerun()

    # 匯出
    e_buf = io.BytesIO()
    with pd.ExcelWriter(e_buf, engine="openpyxl") as writer:
        st.session_state["holdings_df"].to_excel(writer, sheet_name="持股", index=False)
    e_buf.seek(0)
    tb[3].download_button(
        "⬇️ 匯出", data=e_buf.getvalue(),
        file_name="my_holdings.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    uploaded_h = tb[4].file_uploader(
        "上傳覆蓋", type=["xlsx"], key="holdings_uploader",
        label_visibility="collapsed",
    )
    if uploaded_h:
        try:
            up_df = pd.read_excel(uploaded_h)
            up_df["進場日"] = pd.to_datetime(up_df["進場日"])
            st.session_state["holdings_df"] = up_df
            st.success(f"已載入 {len(up_df)} 筆")
        except Exception as e:
            st.error(f"讀取失敗：{e}")

    # 編輯器
    edited = st.data_editor(
        st.session_state["holdings_df"],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "股票代號": st.column_config.TextColumn(
                "股票代號", required=True, help="例：2330", width="small",
            ),
            "公司名稱": st.column_config.TextColumn("公司名稱", width="medium"),
            "進場價": st.column_config.NumberColumn(
                "進場價", min_value=0.0, step=0.5, format="%.2f", width="small",
            ),
            "進場日": st.column_config.DateColumn(
                "進場日", format="YYYY-MM-DD", width="small",
            ),
            "持有張數": st.column_config.NumberColumn(
                "持有張數", min_value=0, step=1, format="%d", width="small",
            ),
        },
        key="holdings_editor",
    )
    st.session_state["holdings_df"] = edited

    st.divider()

    if st.button("🚀 分析持股", type="primary", use_container_width=False):
        valid = edited.dropna(subset=["股票代號"])
        valid = valid[valid["股票代號"].astype(str).str.strip() != ""]
        if len(valid) == 0:
            st.error("請至少填入一檔持股")
        else:
            cfg = build_cfg()
            holdings_list = []
            for _, row in valid.iterrows():
                code = fix_stock_code(row["股票代號"], cfg["etf_fix_map"])
                if code is None:
                    continue
                ed = row["進場日"]
                if isinstance(ed, pd.Timestamp):
                    ed = ed.date()
                holdings_list.append({
                    "code": code,
                    "company_name": str(row.get("公司名稱", "")).strip(),
                    "entry_price": float(row["進場價"]) if pd.notna(row.get("進場價")) else 0,
                    "entry_date": ed,
                    "lots": int(row["持有張數"]) if pd.notna(row.get("持有張數")) else None,
                })

            bar, log_area, buf, handler = make_progress_block("持股分析")
            logging.getLogger().addHandler(handler)

            def h_progress(stage, pct, msg):
                bar.progress(min(pct, 1.0), text=f"{stage} — {msg}")
                log_area.code("\n".join(buf[-30:]) or "（執行中...）")

            try:
                with st.spinner("分析中 ..."):
                    h_result = run_holdings_scan(
                        cfg=cfg, holdings=holdings_list, progress_cb=h_progress,
                    )
                st.session_state["holdings_result"] = h_result
            except Exception as e:
                st.error(f"分析失敗：{e}")
                st.exception(e)
            finally:
                logging.getLogger().removeHandler(handler)
            bar.progress(1.0, text="完成")

    # 結果
    if "holdings_result" in st.session_state:
        st.divider()
        h_df = st.session_state["holdings_result"]["df"]
        action_counts = h_df["操作建議"].value_counts() if "操作建議" in h_df.columns else {}

        if len(action_counts):
            st.markdown("### 📊 操作摘要")
            cols = st.columns(min(len(action_counts), 6) or 1)
            for i, (action, cnt) in enumerate(action_counts.items()):
                cols[i % len(cols)].metric(action, int(cnt))

        # 分區：需要立即動作 / 續抱
        urgent_keywords = ["停損", "技術轉弱", "+2R", "+1R", "時間停損", "移動停利"]

        def _is_urgent(action):
            return any(k in str(action) for k in urgent_keywords)

        if "操作建議" in h_df.columns:
            urgent = h_df[h_df["操作建議"].apply(_is_urgent)]
            hold = h_df[~h_df["操作建議"].apply(_is_urgent)]
        else:
            urgent = h_df.iloc[0:0]
            hold = h_df

        if len(urgent):
            st.markdown("### ⚡ 需要動作")
            st.dataframe(urgent, use_container_width=True, hide_index=True)
        if len(hold):
            st.markdown("### ✅ 續抱")
            st.dataframe(hold, use_container_width=True, hide_index=True)

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


# =====================================================
# Tab 3：回測
# =====================================================
with tab3:
    if "backtest_result" not in st.session_state:
        st.info("👈 從側欄展開「**🔁 回測設定**」後點「**🔁 跑回測**」")
    else:
        bt = st.session_state["backtest_result"]
        s = bt["summary"]

        # KPI 區
        c = st.columns(4)
        c[0].metric("總交易數", s["總交易數"])
        c[1].metric(
            "勝率%", f"{s['勝率%']}%",
            delta=f"{s['勝率%']-50:.1f}%" if s["勝率%"] else None,
            delta_color="normal",
        )
        c[2].metric(
            "期望值R", s["期望值R"],
            delta="📈 有 edge" if s["期望值R"] > 0.2 else (
                "⚠️ 偏弱" if s["期望值R"] > 0 else "❌ 無 edge"),
            delta_color="off",
        )
        c[3].metric("平均報酬%", f"{s['平均報酬%']}%")

        c2 = st.columns(3)
        c2[0].metric("平均 R", s["平均R"])
        c2[1].metric("最大單筆%", f"{s['最大單筆%']}%")
        c2[2].metric("最大回撤 R", s["最大回撤R"])

        # 累積 R 折線
        if len(bt["trades"]):
            st.markdown("### 📈 累積 R 曲線")
            trades = bt["trades"].copy()
            trades = trades.sort_values("entry_date")
            trades["累積R"] = trades["r_multiple"].fillna(0).cumsum()
            st.line_chart(
                trades.set_index("entry_date")[["累積R"]],
                height=300,
            )

            st.markdown("### 🏆 個股期望值排序（Top）")
            st.dataframe(
                bt["by_symbol"].head(30),
                use_container_width=True, hide_index=True,
            )

            st.markdown("### 📋 交易明細")
            st.dataframe(
                bt["trades"], use_container_width=True,
                height=400, hide_index=True,
            )

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
        else:
            st.warning("回測無任何交易產生 — 試試降低「最低評分」門檻")
