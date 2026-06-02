"""
台股強勢突破掃描器 — Streamlit GUI v0.4

啟動：
    uv run streamlit run app.py
"""
import copy
import io
import logging
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.chart import make_kline
from src.config import load_config
from src.fetcher import fix_stock_code
from src.glossary import HELP
from src.history import cleanup_old, list_scans, load_scan_df, save_scan
from src.macro import classify_us_market
from src.market import classify_market
from src.name_lookup import lookup_names
from src.preferences import load_prefs, save_prefs
from src.report import write_excel
from src.runner import (
    run_backtest, run_factor_eval, run_holdings_scan, run_plateau,
    run_scan, run_sensitivity,
)
from src.universe import fetch_twse_universe


# =====================================================
# Page config
# =====================================================
st.set_page_config(
    page_title="台股強勢突破掃描器",
    page_icon="·",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "**台股強勢突破掃描器** v0.4"},
)


# =====================================================
# Style
# =====================================================
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

<style>
:root {
    --bg:        #F8FAFC;
    --surface:   #FFFFFF;
    --border:    #E2E8F0;
    --border-2:  #F1F5F9;
    --text:      #0F172A;
    --muted:     #64748B;
    --subtle:    #94A3B8;
    --primary:   #4F46E5;
    --primary-2: #EEF2FF;
    --positive:  #059669;
    --positive-2:#ECFDF5;
    --warning:   #D97706;
    --warning-2: #FEF3C7;
    --negative:  #DC2626;
    --negative-2:#FEE2E2;
    --slate:     #475569;
    --slate-2:   #F1F5F9;
}

html, body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    color: var(--text);
}
.stMarkdown, .stText, p,
span:not([class*="material-symbols"]):not([class*="icon"]),
div:not([class*="material-symbols"]):not([class*="icon"]),
label, h1, h2, h3, h4, h5, h6, button {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
}
code, pre, [data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace;
}
[class*="material-symbols"],
.material-symbols-outlined, .material-symbols-rounded, .material-symbols-sharp,
[data-testid*="Icon"], [data-testid*="icon"] {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Symbols Sharp' !important;
    font-feature-settings: 'liga';
}

#MainMenu, footer { visibility: hidden; height: 0; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.2rem; padding-bottom: 1rem; max-width: 1400px; }

h1 { font-weight: 700 !important; letter-spacing: -0.02em; font-size: 1.6rem !important; }
h2 { font-weight: 600 !important; letter-spacing: -0.01em; font-size: 1.2rem !important; margin-top: 1.5rem !important; }
h3 { font-weight: 600 !important; font-size: 1.0rem !important; margin-top: 1.2rem !important; }

.app-header {
    display: flex; justify-content: space-between; align-items: baseline;
    padding-bottom: 12px; border-bottom: 1px solid var(--border-2);
    margin-bottom: 14px;
}
.app-title { font-size: 1.4rem; font-weight: 700; letter-spacing: -0.02em; }
.app-sub  { color: var(--muted); font-size: 0.85rem; }
.app-date { color: var(--subtle); font-size: 0.8rem; font-variant-numeric: tabular-nums; }

[data-testid="stMetric"] {
    background: var(--surface);
    padding: 12px 14px;
    border-radius: 8px;
    border: 1px solid var(--border);
}
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: 0.78rem !important; font-weight: 500 !important; }
[data-testid="stMetricValue"] { font-size: 1.3rem !important; font-weight: 600 !important; }
[data-testid="stMetricDelta"] { font-size: 0.75rem !important; }

/* Header 右側狀態列（取代原本的全寬 banner） */
.hdr-right {
    display: flex; flex-direction: column; align-items: flex-end; gap: 4px;
}
.hdr-chips { display: flex; gap: 6px; }
.hdr-status {
    display: flex; align-items: center; gap: 6px;
    font-size: 0.85rem; color: var(--text);
    padding: 4px 10px; border-radius: 6px;
    background: var(--surface); border: 1px solid var(--border);
}
.hdr-status .dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.hdr-status.bull    { border-left: 3px solid var(--positive); }
.hdr-status.bull .dot { background: var(--positive); }
.hdr-status.bear    { border-left: 3px solid var(--negative); }
.hdr-status.bear .dot { background: var(--negative); }
.hdr-status.neutral { border-left: 3px solid var(--warning); }
.hdr-status.neutral .dot { background: var(--warning); }
.hdr-status.unknown { border-left: 3px solid var(--subtle); }
.hdr-status.unknown .dot { background: var(--subtle); }
.hdr-status b { font-weight: 600; }
.hdr-status .sep { color: var(--border); margin: 0 4px; }
.hdr-detail { color: var(--muted); }

/* 候選卡片：完全使用 Streamlit 原生 container(border=True)，僅做最小化整體調整 */

/* 候選資料 cell（取代 st.metric 以塞入副資訊） */
.cell { line-height: 1.2; padding: 0; }
.cell-label {
    color: var(--muted); font-size: 0.7rem;
    text-transform: uppercase; letter-spacing: 0.04em;
    margin-bottom: 2px;
}
.cell-value {
    font-weight: 700; color: var(--text);
    font-size: 1.05rem;
    font-variant-numeric: tabular-nums;
    line-height: 1.15;
}
.cell-sub {
    color: var(--muted); font-size: 0.7rem;
    font-weight: 500; margin-top: 1px;
    font-variant-numeric: tabular-nums;
}

/* 標題列內的警示文字 */
.cand-warn {
    color: var(--warning); font-size: 0.75rem;
    text-align: right; padding-top: 4px;
    line-height: 1.2;
}

/* 標題列尾巴的「6/8 · 區間突破」內嵌副標 */
.cand-meta-inline {
    color: var(--muted); font-size: 0.78rem;
    margin-left: 4px; font-variant-numeric: tabular-nums;
}

/* Sidebar file uploader 緊湊化 */
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
    padding: 8px 12px !important;
    min-height: 0 !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small {
    display: none !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] svg {
    width: 18px !important; height: 18px !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] > div {
    gap: 8px !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] span {
    font-size: 0.8rem !important;
}

/* segmented control 緊湊 */
[data-testid="stSidebar"] [data-testid="stSegmentedControl"] button {
    font-size: 0.82rem !important;
    padding: 4px 10px !important;
}

/* 持股 alert banner */
.holdings-alert {
    background: var(--negative-2);
    border: 1px solid var(--negative);
    border-left: 4px solid var(--negative);
    color: var(--negative);
    padding: 12px 16px;
    border-radius: 6px;
    font-size: 0.95rem;
    margin: 8px 0 12px 0;
    font-weight: 500;
}
.holdings-alert b { font-weight: 700; font-size: 1.05rem; }
.holdings-ok {
    background: var(--positive-2);
    border: 1px solid var(--positive);
    border-left: 4px solid var(--positive);
    color: var(--positive);
    padding: 12px 16px;
    border-radius: 6px;
    font-size: 0.95rem;
    margin: 8px 0 12px 0;
    font-weight: 500;
}

/* 卡片內的 metric 拿掉邊框/底色，避免「邊框中的邊框」雙層噪音 */
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    box-shadow: none !important;
}

/* 大幅壓縮卡片內部垂直間距 */
[data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stMetric"]) {
    padding: 10px 14px 8px 14px !important;
}
/* metric 內部 label/value 間距收緊 */
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetricLabel"] {
    margin-bottom: 0 !important; padding-bottom: 0 !important;
}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetricLabel"] p {
    margin: 0 !important; font-size: 0.72rem !important;
}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetricValue"] {
    margin: 0 !important; padding: 0 !important;
}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetricValue"] div {
    line-height: 1.2 !important;
}
/* 卡片內各 row 之間（標題 → metric → caption）的間距收緊 */
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"] {
    gap: 4px !important;
}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"] {
    gap: 6px !important;
}
/* 卡片內 caption（17.3% 資金 / 偏冷 / 已限縮至…）緊貼上方 */
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCaptionContainer"] {
    margin-top: -4px !important;
}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCaptionContainer"] p {
    margin: 0 !important; line-height: 1.2 !important; font-size: 0.72rem !important;
}

.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] {
    font-size: 0.95rem !important; font-weight: 500 !important;
    padding: 8px 14px !important; color: var(--muted) !important;
}
.stTabs [aria-selected="true"] { color: var(--text) !important; font-weight: 600 !important; }

[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }
[data-testid="stSidebar"] .stMarkdown h3 { font-size: 0.85rem !important; color: var(--muted) !important; text-transform: uppercase; letter-spacing: 0.05em; }
[data-testid="stSidebar"] [data-testid="stExpander"] {
    border: 1px solid var(--border); border-radius: 6px; background: var(--bg);
    margin-bottom: 6px;
}

button[kind="primary"] {
    background: var(--primary) !important; border: 1px solid var(--primary) !important;
    border-radius: 6px !important; font-weight: 500 !important;
}
button[kind="secondary"] {
    border-radius: 6px !important; border: 1px solid var(--border) !important;
    color: var(--text) !important; background: var(--surface) !important;
}
button[kind="secondary"]:hover { border-color: var(--subtle) !important; background: var(--bg) !important; }

[data-testid="stDataFrame"] { border: 1px solid var(--border) !important; border-radius: 6px; }
[data-testid="stProgress"] > div > div > div { background-color: var(--primary) !important; }

[data-testid="stAlert"] {
    border-radius: 6px !important; border: 1px solid var(--border) !important;
    background: var(--surface) !important; color: var(--text) !important;
}

/* 待處理 chip */
.watch-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.watch-chip {
    background: var(--primary-2); color: var(--primary);
    padding: 4px 10px; border-radius: 12px;
    font-size: 0.78rem; font-family: 'JetBrains Mono', monospace;
}
</style>
""", unsafe_allow_html=True)


# Header 移到後面與大盤狀態合併渲染


# =====================================================
# Load base config & cache market state
# =====================================================
@st.cache_data
def get_base_config():
    return load_config("config.yaml")


@st.cache_data(ttl=600)
def get_market_state_cached():
    cfg = get_base_config()
    return classify_market(cfg["data"]["period"], cfg["data"]["cache_dir"])


@st.cache_data(ttl=1800)
def get_us_state_cached():
    cfg = get_base_config()
    return classify_us_market("1y", cfg["data"]["cache_dir"])


@st.cache_data(ttl=86400)
def get_code_name_map():
    """從 TWSE OpenAPI 抓代號 → 名稱 對照表（一天快取）"""
    try:
        uni = fetch_twse_universe(include_common=True, include_etf=True)
        return {x["code"]: x["company_name"] for x in uni}
    except Exception:
        return {}


base_cfg = get_base_config()


# 載入使用者偏好
if "_prefs_loaded" not in st.session_state:
    prefs = load_prefs()
    st.session_state["_prefs"] = prefs
    st.session_state["_prefs_loaded"] = True
else:
    prefs = st.session_state["_prefs"]


def fmt_int(n):
    """千分位"""
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def fmt_money(n):
    try:
        return f"{int(n):,} 元"
    except Exception:
        return str(n)


@st.cache_data
def make_stock_list_template():
    """股票清單上傳模板"""
    df = pd.DataFrame([
        {"股票代號": "2330", "公司名稱": "台積電"},
        {"股票代號": "2317", "公司名稱": "鴻海"},
        {"股票代號": "0050", "公司名稱": "元大台灣50"},
    ])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="股票清單", index=False)
    return buf.getvalue()


@st.cache_data
def make_holdings_template():
    """持股上傳模板"""
    df = pd.DataFrame([
        {"股票代號": "2330", "公司名稱": "台積電", "成本價": 1000.00, "持有股數": 1000},
        {"股票代號": "0050", "公司名稱": "元大台灣50", "成本價": 220.50, "持有股數": 2000},
    ])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="持股", index=False)
    return buf.getvalue()


# =====================================================
# Preset application logic
# =====================================================
def apply_preset(key):
    p = base_cfg.get("presets", {}).get(key, {})
    if not p:
        return
    st.session_state["preset"] = key
    st.session_state["min_price"] = float(p["filters"]["min_price"])
    st.session_state["min_avg_volume"] = int(p["filters"]["min_avg_volume"])
    st.session_state["require_ma60"] = bool(p["filters"]["require_above_ma60"])
    st.session_state["min_risk_pct"] = float(p["filters"]["min_risk_pct"])
    st.session_state["thr_enter"] = int(p["thresholds"]["enter"])
    st.session_state["thr_watch"] = int(p["thresholds"]["watch"])
    st.session_state["risk_pct"] = float(p["risk_per_trade_pct"]) * 100
    st.session_state["max_pos_pct"] = int(p["max_position_pct"] * 100)


# 初始化 session_state 預設值（套用偏好）
if "preset" not in st.session_state:
    apply_preset(prefs.get("preset", "balanced"))
    st.session_state["total_capital"] = int(prefs.get("total_capital", 1_000_000))
if "watchlist" not in st.session_state:
    st.session_state["watchlist"] = []


# =====================================================
# Sidebar
# =====================================================
with st.sidebar:
    st.markdown("### 風格 Preset")
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
    if selected_preset and selected_preset != current_preset:
        apply_preset(selected_preset)
        st.rerun()

    st.markdown("### 策略模式")
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

    st.markdown("### 資料來源")

    source_options = {
        "upload": "上傳清單",
        "universe": "全台股",
    }
    source = st.segmented_control(
        "資料來源",
        options=list(source_options.keys()),
        format_func=lambda k: source_options[k],
        default="upload",
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

    st.markdown("")
    run_btn = st.button("開始掃描", type="primary", use_container_width=True)

    st.divider()

    with st.expander("部位管理", expanded=True):
        total_capital = st.number_input(
            "總資金（元）", min_value=100_000,
            value=int(base_cfg.get("position_sizing", {}).get("total_capital", 1_000_000)),
            step=100_000, key="total_capital", help=HELP["total_capital"],
        )
        risk_pct = st.slider(
            "單筆風險 %", 0.5, 5.0,
            st.session_state.get("risk_pct", 1.0), 0.25, key="risk_pct",
            help=HELP["risk_per_trade"],
        ) / 100
        max_pos_pct = st.slider(
            "單檔最大佔比 %", 5, 50,
            st.session_state.get("max_pos_pct", 20), 5, key="max_pos_pct",
            help=HELP["max_pos_pct"],
        ) / 100

    with st.expander("品質過濾", expanded=False):
        min_price = st.number_input(
            "最低股價", min_value=0.0,
            value=st.session_state.get("min_price", 10.0), step=1.0, key="min_price",
            help=HELP["min_price"],
        )
        min_avg_volume = st.number_input(
            "20 日均量下限（股）", min_value=0,
            value=st.session_state.get("min_avg_volume", 500_000), step=100_000,
            key="min_avg_volume", help=HELP["min_avg_volume"],
        )
        require_ma60 = st.checkbox(
            "必須站上 MA60",
            value=st.session_state.get("require_ma60", True), key="require_ma60",
            help=HELP["require_ma60"],
        )
        min_risk_pct = st.slider(
            "最小停損距離 %", 0.0, 10.0,
            st.session_state.get("min_risk_pct", 0.02) * 100, 0.5,
            key="min_risk_pct_slider", help=HELP["min_risk_pct"],
        ) / 100

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

        thr_enter = st.number_input(
            "進場 ≥", 0, 20,
            st.session_state.get("thr_enter", 6), key="thr_enter",
            help=HELP["thr_enter"],
        )
        thr_watch = st.number_input(
            "觀察 ≥", 0, 20,
            st.session_state.get("thr_watch", 5), key="thr_watch",
            help=HELP["thr_watch"],
        )

    st.divider()
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
                    "股票代號", "公司名稱", "進場價", "進場日", "持有張數",
                ])
            new_rows = []
            for w in st.session_state["watchlist"]:
                new_rows.append({
                    "股票代號": w["code"],
                    "公司名稱": w.get("name", ""),
                    "進場價": w.get("entry", 0.0),
                    "進場日": pd.Timestamp.today().normalize(),
                    "持有張數": w.get("lots", 1),
                })
            new_df = pd.DataFrame(new_rows)
            st.session_state["holdings_df"] = pd.concat(
                [st.session_state["holdings_df"], new_df], ignore_index=True,
            )
            st.session_state["watchlist"] = []
            st.success(f"已加入 {len(new_rows)} 檔到持股管理")
            st.rerun()


# =====================================================
# Build cfg
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
        "rel_strength": w_rs,
        "trend_confirm": w_trend,
    }
    cfg["scoring"]["thresholds"] = {
        "enter": thr_enter, "watch": thr_watch,
    }
    cfg["position_sizing"] = {
        "total_capital": int(total_capital),
        "risk_per_trade_pct": risk_pct,
        "lot_size": 1000,
        "max_position_pct": max_pos_pct,
    }
    cfg.setdefault("strategy", {})
    cfg["strategy"]["mode"] = st.session_state.get("strategy_mode", "breakout")
    base_costs = base_cfg.get("costs", {})
    cfg["costs"] = {
        "enabled": bool(st.session_state.get("cost_enabled", base_costs.get("enabled", True))),
        "fee_rate": float(st.session_state.get("cost_fee", base_costs.get("fee_rate", 0.001425) * 100)) / 100,
        "fee_discount": float(st.session_state.get("cost_disc", base_costs.get("fee_discount", 1.0))),
        "tax_rate": float(st.session_state.get("cost_tax", base_costs.get("tax_rate", 0.003) * 100)) / 100,
        "apply_to_factor_eval": bool(st.session_state.get("cost_apply_fe", base_costs.get("apply_to_factor_eval", False))),
    }
    return cfg


# =====================================================
# Helpers
# =====================================================
class StListHandler(logging.Handler):
    def __init__(self, buf):
        super().__init__()
        self.buf = buf

    def emit(self, record):
        self.buf.append(self.format(record))


def make_progress_block(title):
    bar = st.progress(0.0, text=f"{title} 準備中 …")
    log_area = st.expander("執行記錄", expanded=False).empty()
    buf = []
    handler = StListHandler(buf)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S",
    ))
    return bar, log_area, buf, handler


def _chip_cls(regime):
    return {
        "bull": "bull", "bear": "bear", "neutral": "neutral",
        "risk_on": "bull", "risk_off": "bear",
    }.get(regime, "unknown")


def render_header(market_state, last_scan_at=None, us_state=None):
    """整合的 header：左側標題，右側大盤雙 chip + 日期/上次掃描"""
    date_str = pd.Timestamp.today().strftime('%Y / %m / %d  %A')
    chips = []

    if market_state:
        cls = _chip_cls(market_state["regime"])
        label = market_state["label"]
        for sym in ["🟢", "🔴", "🟡", "⚪"]:
            label = label.replace(sym, "")
        label = label.strip()
        tw_detail = market_state.get("detail", "")
        chips.append(
            f"<div class='hdr-status {cls}' title='{tw_detail}'>"
            f"<span class='dot'></span>"
            f"<b>台股 {label}</b>"
            f"</div>"
        )

    if us_state:
        cls = _chip_cls(us_state["regime"])
        label = us_state["label"]
        us_detail = us_state.get("detail", "")
        chips.append(
            f"<div class='hdr-status {cls}' title='{us_detail}'>"
            f"<span class='dot'></span>"
            f"<b>美股 {label}</b>"
            f"</div>"
        )

    status_html = "<div class='hdr-chips'>" + "".join(chips) + "</div>" if chips else ""
    last = f"<span class='sep'>·</span>上次掃描 {last_scan_at}" if last_scan_at else ""

    st.markdown(
        f"""
<div class='app-header'>
  <div>
    <div class='app-title'>台股強勢突破掃描器</div>
    <div class='app-sub'>加權評分 · 換手率分析 · 操作建議</div>
  </div>
  <div class='hdr-right'>
    {status_html}
    <div class='app-date'>{date_str}{last}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _action_class(action):
    s = str(action)
    if "進場" in s or "埋伏" in s:
        return "go"
    if "觀察" in s:
        return "watch"
    return "skip"


def _action_tooltip(action):
    """為操作建議提供 hover 解釋"""
    s = str(action)
    if "突破" in s:
        return "今日創 20 日新高並爆量，順勢追進"
    if "拉回" in s:
        return "曾突破後回測 MA10/MA20，於支撐上方掛限價"
    if "區間" in s:
        return "經過窄幅整理後突破上緣，量增確認"
    if "進場" in s:
        return "符合進場條件但無明確劇本，建議部位減半"
    if "觀察" in s:
        return "評分次強，列入觀察名單，明日再評估"
    if "大盤" in s:
        return "大盤位於 MA20 之下，暫停所有買入"
    if "資金" in s:
        return "依固定風險法計算結果不足 1 張，需提高風險% 或選低價標的"
    return "未達進場門檻"


def _turnover_color(val):
    """換手率% 視覺基準色"""
    if val is None or pd.isna(val):
        return "#94A3B8"
    v = float(val)
    if v < 3:
        return "#94A3B8"  # 冷
    if v < 5:
        return "#0F172A"  # 正常
    if v < 10:
        return "#D97706"  # 活絡
    return "#DC2626"      # 過熱


def _turnover_label(val):
    if val is None or pd.isna(val):
        return ""
    v = float(val)
    if v < 3:
        return "偏冷"
    if v < 5:
        return "正常"
    if v < 10:
        return "活絡"
    return "過熱"


def render_edge_meter(expectancy):
    """期望值 R 燈號條"""
    try:
        e = float(expectancy)
    except Exception:
        e = 0

    # 區間：< 0 紅、0-0.2 黃、> 0.2 綠
    val = max(min(e, 1.0), -0.5)
    pct = (val + 0.5) / 1.5 * 100  # 映射到 0-100

    if e < 0:
        label = "無 edge"
        color = "#DC2626"
    elif e < 0.2:
        label = "偏弱"
        color = "#D97706"
    elif e < 0.5:
        label = "有 edge"
        color = "#059669"
    else:
        label = "強 edge"
        color = "#15803D"

    st.markdown(
        f"""
<div style='background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:12px 16px;'>
  <div style='display:flex; justify-content:space-between; margin-bottom:8px;'>
    <span style='color:#64748B; font-size:0.78rem; font-weight:500;'>策略 Edge</span>
    <span style='color:{color}; font-size:0.85rem; font-weight:600;'>{label}（期望值 {e:.2f} R）</span>
  </div>
  <div style='background:#F1F5F9; height:8px; border-radius:4px; position:relative; overflow:hidden;'>
    <div style='position:absolute; left:{(0.5/1.5)*100:.0f}%; width:1px; height:100%; background:#94A3B8;'></div>
    <div style='position:absolute; left:0; top:0; bottom:0; width:{pct:.1f}%; background:{color}; border-radius:4px;'></div>
  </div>
  <div style='display:flex; justify-content:space-between; margin-top:4px;'>
    <span style='color:#94A3B8; font-size:0.7rem;'>-0.5</span>
    <span style='color:#94A3B8; font-size:0.7rem;'>0</span>
    <span style='color:#94A3B8; font-size:0.7rem;'>+1.0</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_drawdown_chart(trades):
    """累積 R 折線 + drawdown 區域子圖"""
    if len(trades) == 0:
        return

    trades = trades.copy().sort_values("entry_date")
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    trades["累積R"] = trades["r_multiple"].fillna(0).cumsum()
    trades["peak"] = trades["累積R"].cummax()
    trades["drawdown"] = trades["累積R"] - trades["peak"]

    from plotly.subplots import make_subplots
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.7, 0.3], vertical_spacing=0.03,
        subplot_titles=("累積 R", "Drawdown"),
    )
    fig.add_trace(
        go.Scatter(
            x=trades["entry_date"], y=trades["累積R"], mode="lines",
            line=dict(color="#4F46E5", width=2),
            fill="tozeroy", fillcolor="rgba(79, 70, 229, 0.08)",
            name="累積 R",
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=trades["entry_date"], y=trades["drawdown"], mode="lines",
            line=dict(color="#DC2626", width=1.5),
            fill="tozeroy", fillcolor="rgba(220, 38, 38, 0.15)",
            name="Drawdown",
        ),
        row=2, col=1,
    )
    fig.update_layout(
        height=380, showlegend=False,
        margin=dict(l=8, r=8, t=40, b=8),
        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
        font=dict(family="Inter, sans-serif", size=11, color="#0F172A"),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#F1F5F9")
    fig.update_yaxes(showgrid=True, gridcolor="#F1F5F9")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_monthly_returns(trades):
    """月度報酬柱狀圖"""
    if len(trades) == 0:
        return
    df = trades.copy()
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["month"] = df["entry_date"].dt.to_period("M").astype(str)
    monthly = df.groupby("month")["r_multiple"].sum().reset_index()
    colors = ["#059669" if v >= 0 else "#DC2626" for v in monthly["r_multiple"]]

    fig = go.Figure(go.Bar(
        x=monthly["month"], y=monthly["r_multiple"],
        marker_color=colors, marker_line_width=0,
    ))
    fig.update_layout(
        height=260, margin=dict(l=8, r=8, t=8, b=8),
        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
        font=dict(family="Inter, sans-serif", size=11),
        showlegend=False,
        yaxis_title="累積 R",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#F1F5F9")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_onboarding():
    """首次使用者引導"""
    st.markdown("""
<div style='background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:20px 24px; margin-bottom:14px;'>
<h3 style='margin-top:0; font-size:1rem;'>歡迎使用</h3>
<p style='color:#64748B; font-size:0.9rem; margin-bottom:12px;'>三個步驟開始：</p>
<ol style='color:#0F172A; font-size:0.9rem; margin:0; padding-left:20px; line-height:1.8;'>
  <li>左側選一個 <b>風格 Preset</b>（保守 / 平衡 / 積極）</li>
  <li>選擇資料來源（上傳清單或全台股），點 <b>開始掃描</b></li>
  <li>從進場候選卡片點「<b>詳細</b>」看 K 線，或「<b>待處理</b>」加入清單，再到側欄一鍵轉入持股管理</li>
</ol>
</div>
""", unsafe_allow_html=True)


def add_to_watchlist(code, name, entry, lots):
    existing = {w["code"] for w in st.session_state["watchlist"]}
    if code in existing:
        return False
    st.session_state["watchlist"].append({
        "code": code, "name": name, "entry": entry, "lots": lots,
    })
    return True


# =====================================================
# K 線彈窗
# =====================================================
@st.dialog("個股詳細", width="large")
def show_detail_dialog(row, ohlc_map):
    symbol = row["股票"]
    name = row["公司名稱"]
    df_ohlc = ohlc_map.get(symbol) if ohlc_map else None

    # 標題列
    action = row.get("操作建議", "—")
    cls = _action_class(action)
    st.markdown(
        f"<div style='display:flex; align-items:baseline; gap:12px;'>"
        f"<span style='font-family:JetBrains Mono; color:#64748B;'>{symbol}</span>"
        f"<span style='font-size:1.1rem; font-weight:600;'>{name}</span>"
        f"<span class='card-action {cls}' style='display:inline-block;'>{action}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # 關鍵數字
    score_d = row.get("評分顯示", row.get("評分", "—"))
    entry = row.get("進場參考價", None)
    stop = row.get("停損價", None)
    t1 = row.get("目標價1(+1R半倉)", None)
    t2 = row.get("目標價2(+2R出清)", None)
    risk_pct = row.get("風險%", "—")
    lots = row.get("建議張數", 0)
    cost_pct = row.get("佔資金%", 0)
    turnover = row.get("換手率%", None)
    entry_type = row.get("進場類型", "—")
    entry_note = row.get("進場條件", "")

    c = st.columns(7)
    c[0].metric("評分", score_d)
    c[1].metric("進場", entry if entry is not None else "—")
    c[2].metric("停損", stop if stop is not None else "—")
    c[3].metric("目標 1", t1 if t1 is not None else "—")
    c[4].metric("目標 2", t2 if t2 is not None else "—")
    c[5].metric("風險", f"{risk_pct}%")
    c[6].metric("建議", f"{lots} 張")

    if entry_note:
        st.caption(f"進場類型：{entry_type} · {entry_note}")

    # K 線
    if df_ohlc is not None and not df_ohlc.empty:
        try:
            fig = make_kline(
                df_ohlc, title=f"{symbol} {name}",
                entry=entry, stop=stop, target1=t1, target2=t2,
                recent_bars=120,
            )
            if fig:
                st.plotly_chart(fig, use_container_width=True,
                                 config={"displayModeBar": False})
        except Exception as e:
            st.error(f"無法繪製 K 線：{e}")
    else:
        st.info("無 OHLC 資料可繪圖")

    # 條件達成
    st.markdown("**條件達成**")
    cond_cols = st.columns(5)
    conditions = [
        ("突破+量增", row.get("突破+量增")),
        ("MA 多頭", row.get("MA多頭")),
        ("換手率強勢", row.get("換手率強勢")),
        ("KD 強勢", row.get("KD強勢")),
        ("MACD 多方", row.get("MACD多方")),
    ]
    for i, (label, val) in enumerate(conditions):
        v = bool(val) if val is not None and pd.notna(val) else False
        icon = "✓" if v else "·"
        color = "#059669" if v else "#94A3B8"
        cond_cols[i].markdown(
            f"<div style='text-align:center; padding:8px; border:1px solid #E2E8F0; border-radius:6px;'>"
            f"<div style='color:{color}; font-size:1.2rem; font-weight:600;'>{icon}</div>"
            f"<div style='color:#64748B; font-size:0.75rem;'>{label}</div></div>",
            unsafe_allow_html=True,
        )

    # 加入待處理
    st.markdown("")
    btn_cols = st.columns([3, 1])
    btn_cols[0].caption("確認加入「待處理」後，再到側欄一鍵轉入持股管理")
    if btn_cols[1].button("加入待處理", type="primary", use_container_width=True,
                          key=f"add_{symbol}"):
        added = add_to_watchlist(symbol, name, entry, lots if lots else 1)
        if added:
            st.success("已加入待處理")
            st.rerun()
        else:
            st.warning("已在待處理清單")


# =====================================================
# Header + Market status (整合到頁首右側)
# =====================================================
last_scan_at = st.session_state.get("last_scan_at")
market_state = None
us_state = None
if "result" in st.session_state:
    market_state = st.session_state["result"].get("market_state")
    if market_state:
        us_state = market_state.get("us_state")
if market_state is None:
    try:
        market_state = get_market_state_cached()
    except Exception:
        market_state = None
if us_state is None:
    try:
        us_state = get_us_state_cached()
    except Exception:
        us_state = None
render_header(market_state, last_scan_at, us_state=us_state)


# =====================================================
# Tabs
# =====================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["買入掃描", "持股管理", "回測", "歷史", "📖 操作教學"])


# =====================================================
# Tab 1: 買入掃描
# =====================================================
_GRADE_BADGE = {
    "A": ("🟢", "#059669", "強力進場"),
    "B": ("🟡", "#D97706", "可進場"),
    "C": ("🟠", "#EA580C", "觀察"),
    "避開": ("🔴", "#DC2626", "避開"),
}


def _pillar_lights(row):
    """回傳 5 支柱燈號 list[(名稱, emoji)]：技術/籌碼/相對強度/族群/風險。"""
    def dot(state):
        return {"g": "🟢", "y": "🟡", "r": "🔴", "n": "⚪"}[state]

    action = str(row.get("操作建議", ""))
    tech = "g" if "進場" in action else ("y" if "觀察" in action else "r")

    chip = str(row.get("籌碼確認", "—"))
    chip_s = "g" if (chip.startswith("法人") and "賣" not in chip) else (
        "r" if "賣超" in chip else "n")

    rs = row.get("相對強度RS%", None)
    rs_s = "n" if rs is None or pd.isna(rs) else ("g" if rs > 0 else "y")

    grp = str(row.get("族群同步", "—"))
    grp_s = "g" if "同步" in grp else "n"

    warn = str(row.get("部位提示", "")) + str(row.get("評級理由", ""))
    risk_s = "r" if any(k in warn for k in ("賣超", "追高", "乖離", "融資爆增", "財報")) else "g"

    return [("技術", dot(tech)), ("籌碼", dot(chip_s)), ("RS", dot(rs_s)),
            ("族群", dot(grp_s)), ("風險", dot(risk_s))]


def _price_bar_html(stop, entry, cur, t1, t2):
    """進場/停損/目標 視覺刻度條。"""
    try:
        vals = [float(stop), float(entry), float(t1), float(t2)]
        lo, hi = min(vals), max(vals)
        if hi <= lo:
            return ""
        def frac(x):
            return max(0, min(100, (float(x) - lo) / (hi - lo) * 100))
        marks = [(frac(stop), "#DC2626", "停損"), (frac(entry), "#2563EB", "進場"),
                 (frac(t1), "#059669", "T1"), (frac(t2), "#047857", "T2")]
        dots = ""
        for f, c, lab in marks:
            dots += (f"<div style='position:absolute;left:{f:.1f}%;top:-2px;transform:translateX(-50%);'>"
                     f"<div style='width:9px;height:9px;border-radius:50%;background:{c};margin:0 auto;'></div>"
                     f"<div style='font-size:9px;color:{c};white-space:nowrap;'>{lab}</div></div>")
        cur_html = ""
        if cur is not None and pd.notna(cur):
            cf = frac(cur)
            cur_html = (f"<div style='position:absolute;left:{cf:.1f}%;top:-14px;transform:translateX(-50%);"
                        f"font-size:10px;'>▼<span style='font-size:9px;'>現價</span></div>")
        return (f"<div style='position:relative;height:34px;margin:14px 4px 6px;'>"
                f"<div style='position:absolute;top:2px;left:0;right:0;height:4px;border-radius:2px;"
                f"background:linear-gradient(90deg,#FCA5A5,#FDE68A,#86EFAC);'></div>"
                f"{cur_html}{dots}</div>")
    except Exception:
        return ""


def render_top_candidates(df, ohlc_map, n=10):
    if "訊號判斷" not in df.columns:
        return

    entry_mask = df["訊號判斷"] == "進場"
    actionable_mask = df.get("操作建議", pd.Series(dtype=str)).astype(str).str.contains("進場|埋伏", na=False)
    top = df[entry_mask & actionable_mask].head(n)

    skipped = int((entry_mask & ~actionable_mask).sum())

    if len(top) == 0:
        if skipped > 0:
            st.info(f"有 {skipped} 檔達進場條件但「資金不足」 — 提高側欄「單筆風險%」或切「積極」preset")
        else:
            st.info("目前無進場候選 — 改變設定 / 風格 Preset 試試")
        return

    if skipped > 0:
        st.caption(f"另有 {skipped} 檔達進場條件但資金不足，可在表格查看")

    st.markdown("### 進場候選")

    for idx, (_, row) in enumerate(top.iterrows()):
        action = str(row.get("操作建議", ""))
        entry = row.get("進場參考價", "—")
        cur_price = row.get("目前現價", None)
        price_dev = row.get("現價偏離%", None)
        stop = row.get("停損價", "—")
        t1 = row.get("目標價1(+1R半倉)", "—")
        t2 = row.get("目標價2(+2R出清)", "—")
        risk_pct_val = row.get("風險%", "—")
        lots = row.get("建議張數", "—")
        cost_pct = row.get("佔資金%", 0)
        turnover = row.get("換手率%", None)
        score_d = row.get("評分顯示", row.get("評分", "—"))
        entry_type = row.get("進場類型", "—")
        warning = row.get("部位提示", "")

        with st.container(border=True):
            # ===== 標題列：[code 名稱 chip 評分副標] [warning] [詳細] [待處理] =====
            badge_color = _action_class(action)
            badge_token = {"go": "green", "watch": "orange", "skip": "gray"}.get(badge_color, "gray")
            title_md = (
                f"**{row['股票']}**  {row['公司名稱']}  "
                f":{badge_token}-badge[{action}]  "
                f"<span class='cand-meta-inline'>{score_d} · {entry_type}</span>"
            )

            hc1, hc_warn, hc2, hc3 = st.columns([5, 2.2, 1, 1])
            hc1.markdown(title_md, unsafe_allow_html=True)
            if warning:
                hc_warn.markdown(f"<div class='cand-warn'>⚠ {warning}</div>",
                                  unsafe_allow_html=True)
            if hc2.button("詳細", key=f"detail_{idx}_{row['股票']}",
                          use_container_width=True):
                show_detail_dialog(row, ohlc_map)
            if hc3.button("待處理", key=f"watch_{idx}_{row['股票']}",
                          use_container_width=True):
                added = add_to_watchlist(row["股票"], row["公司名稱"],
                                          row.get("進場參考價", 0),
                                          row.get("建議張數", 1))
                if added:
                    st.toast("已加入待處理", icon="·")
                    st.rerun()

            # ===== 綜合評級 + 一行理由 =====
            grade = str(row.get("綜合評級", ""))
            reason = str(row.get("評級理由", ""))
            emoji, gcolor, glabel = _GRADE_BADGE.get(grade, ("", "#64748B", grade))
            # 紅旗警示橫幅（理由含「注意：」）
            if "注意：" in reason:
                main_r, warn_r = reason.split("注意：", 1)
                st.markdown(f"<div style='background:#FEF2F2;border-left:3px solid #DC2626;"
                            f"padding:4px 8px;border-radius:4px;font-size:12px;color:#991B1B;margin-bottom:4px;'>"
                            f"⚠️ {warn_r.rstrip('）')}</div>", unsafe_allow_html=True)
                reason = main_r.rstrip("（")
            lights = _pillar_lights(row)
            lights_html = "　".join([f"{lab}{dot}" for lab, dot in lights])
            # 潛伏模式：顯示啟動就緒度
            readiness = row.get("啟動就緒度", None)
            launch_tag = str(row.get("啟動標籤", ""))
            launch_html = ""
            if readiness is not None and pd.notna(readiness):
                rc = "#059669" if readiness >= 70 else ("#D97706" if readiness >= 45 else "#94A3B8")
                launch_html = (f"<span style='font-size:12px;font-weight:700;color:{rc};'>"
                               f"{launch_tag} {int(readiness)}</span>")
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:10px;margin:2px 0 2px;'>"
                f"<span style='font-size:15px;font-weight:700;color:{gcolor};'>{emoji} {grade}級 {glabel}</span>"
                f"{launch_html}"
                f"<span style='font-size:12px;color:#475569;'>{reason}</span>"
                f"<span style='margin-left:auto;font-size:12px;'>{lights_html}</span>"
                f"</div>", unsafe_allow_html=True)

            # ===== 價格刻度條 =====
            pbar = _price_bar_html(stop, entry, cur_price, t1, t2)
            if pbar:
                st.markdown(pbar, unsafe_allow_html=True)

            # ===== 資料列：7 個自訂 cell（含內嵌副資訊）=====
            try:
                lots_int = int(lots) if lots is not None and pd.notna(lots) else 0
            except Exception:
                lots_int = lots
            tr_value = f"{turnover}%" if turnover is not None and pd.notna(turnover) else "—"
            tr_label = _turnover_label(turnover) if turnover is not None and pd.notna(turnover) else ""

            cur_val = f"{cur_price}" if cur_price is not None and pd.notna(cur_price) else "—"
            cur_sub = f"{price_dev:+.1f}%" if price_dev is not None and pd.notna(price_dev) else None
            cells = [
                ("現價",   cur_val,        cur_sub),
                ("進場",   entry,          None),
                ("停損",   stop,           None),
                ("目標 1", t1,             None),
                ("目標 2", t2,             None),
                ("風險",   f"{risk_pct_val}%", None),
                ("建議",   f"{lots_int} 張", f"{cost_pct}% 資金"),
                ("換手率", tr_value,       tr_label or None),
            ]
            mcols = st.columns(8)
            for i, (lab, val, sub) in enumerate(cells):
                sub_html = f"<div class='cell-sub'>{sub}</div>" if sub else ""
                mcols[i].markdown(
                    f"<div class='cell'>"
                    f"<div class='cell-label'>{lab}</div>"
                    f"<div class='cell-value'>{val}</div>"
                    f"{sub_html}"
                    f"</div>",
                    unsafe_allow_html=True,
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

    max_score = int(df["評分"].max()) if len(df) and "評分" in df.columns else 8
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
        "風險%", "建議張數", "換手率%", "籌碼確認",
    ]
    full_priority = minimal_cols + [
        "進場類型", "進場條件", "進場成本", "佔資金%", "部位提示",
        "法人連買天數", "法人買賣超(張)", "外資買賣超(張)", "法人5日累計(張)",
        "融資券提示", "融資增減%", "券資比%",
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
        cls = _action_class(action)
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


with tab1:
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
            st.session_state["cfg"] = cfg
            st.session_state["last_scan_at"] = datetime.now().strftime("%H:%M:%S")
            try:
                save_scan(result, market_state=result.get("market_state"),
                          label=mode)
                cleanup_old(keep_n=30)
            except Exception as e:
                logging.getLogger("main").warning("存歷史失敗：%s", e)
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
        result = st.session_state["result"]
        df = result["df"]
        summary = result["summary"]
        failed_df = result["failed_df"]
        ohlc_map = result.get("ohlc_map", {})

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


# =====================================================
# Tab 2: 持股管理
# =====================================================
with tab2:
    # ============ 初始化 ============
    if "holdings_df" not in st.session_state:
        st.session_state["holdings_df"] = pd.DataFrame([
            {"股票代號": "2330", "公司名稱": "台積電", "成本價": 0.00,
             "持有股數": 1000},
        ])

    holdings_df_curr = st.session_state["holdings_df"]
    valid_h = holdings_df_curr.copy()
    if "股票代號" in valid_h.columns:
        valid_h = valid_h.dropna(subset=["股票代號"])
        valid_h = valid_h[valid_h["股票代號"].astype(str).str.strip() != ""]

    h_result = st.session_state.get("holdings_result")

    # ============ 統計：成本 / 現值 / 損益 ============
    total_cost = 0.0
    if len(valid_h) and "成本價" in valid_h.columns and "持有股數" in valid_h.columns:
        try:
            cost_series = (
                valid_h["成本價"].fillna(0).astype(float)
                * valid_h["持有股數"].fillna(0).astype(float)
            )
            total_cost = float(cost_series.sum())
        except Exception:
            total_cost = 0.0

    total_value = 0.0
    total_pnl = 0.0
    total_pnl_pct = 0.0
    if h_result and total_cost > 0:
        h_df_full = h_result["df"]
        code_to_current = {}
        for _, r in h_df_full.iterrows():
            stock_str = str(r.get("股票", ""))
            code = stock_str.split(".")[0]
            cur = r.get("目前價")
            if cur is not None and pd.notna(cur):
                code_to_current[code] = float(cur)
        for _, row in valid_h.iterrows():
            code = fix_stock_code(row["股票代號"], base_cfg.get("etf_fix_map", {}))
            if not code:
                continue
            cur = code_to_current.get(code)
            if cur is None:
                continue
            shares = row.get("持有股數")
            if shares is None or pd.isna(shares):
                continue
            total_value += cur * float(shares)
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    # ============ KPI 列 ============
    kc = st.columns(4)
    kc[0].metric("持股檔數", len(valid_h),
                   help="目前持有的股票數量")
    kc[1].metric("總成本", f"{int(total_cost):,}" if total_cost else "—",
                   help="所有持股的成本價 × 持有股數加總（元）")
    kc[2].metric("總現值", f"{int(total_value):,}" if total_value else "—",
                   help="所有持股的目前價 × 持有股數加總（元）。需先點「分析持股」")
    if total_cost > 0 and h_result:
        kc[3].metric("未實現損益", f"{int(total_pnl):+,}",
                       delta=f"{total_pnl_pct:+.2f}%",
                       delta_color="normal" if total_pnl >= 0 else "inverse",
                       help="總現值 - 總成本。delta 為損益百分比")
    else:
        kc[3].metric("未實現損益", "—",
                       help="需先點「分析持股」取得目前價才能計算")

    st.markdown("")

    # ============ 標題 + 工具列 ============
    th1, th2 = st.columns([5, 2])
    th1.markdown("### 持股清單")
    th1.caption("代號填了，公司名稱會自動帶入。儲存在瀏覽器 session — 刷新會清空，記得「匯出」備份。")

    with th2:
        tt = st.columns(4)
        if tt[0].button("清空", use_container_width=True):
            st.session_state["holdings_df"] = pd.DataFrame(columns=[
                "股票代號", "公司名稱", "成本價", "持有股數",
            ])
            st.session_state.pop("holdings_result", None)
            st.session_state["holdings_editor_version"] = (
                st.session_state.get("holdings_editor_version", 0) + 1
            )
            st.rerun()
        e_buf = io.BytesIO()
        with pd.ExcelWriter(e_buf, engine="openpyxl") as writer:
            st.session_state["holdings_df"].to_excel(writer, sheet_name="持股", index=False)
        e_buf.seek(0)
        tt[1].download_button(
            "匯出", data=e_buf.getvalue(),
            file_name="my_holdings.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        with tt[2].popover("上傳", use_container_width=True):
            uploaded_h = st.file_uploader(
                "上傳 xlsx 覆蓋", type=["xlsx"], key="holdings_uploader",
                label_visibility="collapsed",
            )
            if uploaded_h:
                try:
                    up_df = pd.read_excel(uploaded_h)
                    # 舊版欄名相容
                    if "進場價" in up_df.columns and "成本價" not in up_df.columns:
                        up_df = up_df.rename(columns={"進場價": "成本價"})
                    if "進場日" in up_df.columns:
                        up_df = up_df.drop(columns=["進場日"])
                    st.session_state["holdings_df"] = up_df
                    st.session_state["holdings_editor_version"] = (
                        st.session_state.get("holdings_editor_version", 0) + 1
                    )
                    st.success(f"已載入 {len(up_df)} 筆")
                except Exception as e:
                    st.error(f"讀取失敗：{e}")
        tt[3].download_button(
            "模板",
            data=make_holdings_template(),
            file_name="持股_模板.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    # ============ 編輯器（fragment 隔離 rerun，不在 render 中重設 data 源）============
    # editor_version 用來在「清空 / 上傳 / 查詢名稱」後重置編輯器
    if "holdings_editor_version" not in st.session_state:
        st.session_state["holdings_editor_version"] = 0

    @st.fragment
    def holdings_editor_fragment():
        editor_key = f"holdings_editor_v{st.session_state['holdings_editor_version']}"
        edited = st.data_editor(
            st.session_state["holdings_df"],
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "股票代號": st.column_config.TextColumn(
                    "股票代號", required=True, width="small",
                    help="例：2330",
                ),
                "公司名稱": st.column_config.TextColumn(
                    "公司名稱", width="medium",
                    help="留空後按「查詢名稱」會自動帶入",
                ),
                "成本價": st.column_config.NumberColumn(
                    "成本價", min_value=0.0, step=0.01, format="%.2f", width="small",
                    help=HELP["cost_price"],
                ),
                "持有股數": st.column_config.NumberColumn(
                    "持有股數", min_value=0, step=100, format="%d", width="small",
                    help=HELP["shares_held"],
                ),
            },
            key=editor_key,
        )

        # 鏡像當前內容到另一個 key 給外部讀（不動 holdings_df，避免打斷編輯）
        st.session_state["_holdings_edited"] = edited

        # ===== 查詢名稱按鈕 =====
        pending_codes = []
        if len(edited) and "股票代號" in edited.columns:
            for _, row in edited.iterrows():
                code_raw = row.get("股票代號")
                if code_raw is None or pd.isna(code_raw):
                    continue
                code = fix_stock_code(code_raw, base_cfg.get("etf_fix_map", {}))
                if not code:
                    continue
                current_name = row.get("公司名稱")
                if (current_name is None or pd.isna(current_name)
                        or str(current_name).strip() == ""):
                    pending_codes.append(code)
        pending = len(pending_codes)

        qb_col1, qb_col2 = st.columns([1.5, 5])
        label = f"查詢名稱 ({pending})" if pending else "查詢名稱"
        if qb_col1.button(label, use_container_width=True,
                           disabled=pending == 0,
                           help="TWSE 對照表 → 本地快取 → yfinance（首次較慢）"):
            twse_map = get_code_name_map()
            with st.spinner("查詢中（含 yfinance 後備）…"):
                found = lookup_names(pending_codes, twse_map)
            new_df = edited.copy()
            filled = 0
            for i, row in new_df.iterrows():
                code_raw = row.get("股票代號")
                if code_raw is None or pd.isna(code_raw):
                    continue
                code = fix_stock_code(code_raw, base_cfg.get("etf_fix_map", {}))
                if not code:
                    continue
                current_name = row.get("公司名稱")
                if (current_name is None or pd.isna(current_name)
                        or str(current_name).strip() == ""):
                    name = found.get(code)
                    if name:
                        new_df.at[i, "公司名稱"] = name
                        filled += 1
            st.session_state["holdings_df"] = new_df
            st.session_state["holdings_editor_version"] += 1  # 換 key 重置編輯器
            miss = pending - filled
            if miss:
                st.warning(f"已填 {filled} 檔，{miss} 檔仍查無 — 請手動輸入")
            else:
                st.success(f"已填入 {filled} 檔名稱")
            st.rerun(scope="fragment")
        if pending:
            qb_col2.caption(f"有 {pending} 檔代號填了但名稱空白，點左側按鈕查詢")
        else:
            qb_col2.caption("名稱填寫完成")

    holdings_editor_fragment()
    edited = st.session_state.get("_holdings_edited", st.session_state["holdings_df"])
    # 把當前編輯狀態鏡像回 holdings_df 給下游讀 KPI / 分析使用
    # （在 fragment 之外，不會影響編輯器的內部追蹤）
    st.session_state["holdings_df"] = edited

    # ============ 分析按鈕 ============
    st.markdown("")
    ac1, ac2 = st.columns([1.4, 5])
    do_analyze = ac1.button("分析持股", type="primary", use_container_width=True,
                              disabled=len(valid_h) == 0)
    last_analyzed = st.session_state.get("holdings_analyzed_at")
    if last_analyzed:
        ac2.caption(f"上次分析：{last_analyzed}")
    elif len(valid_h) == 0:
        ac2.caption("請先填入至少一檔持股")
    else:
        ac2.caption("分析會抓最新收盤價並判斷出場建議")

    if do_analyze:
        valid = edited.dropna(subset=["股票代號"])
        valid = valid[valid["股票代號"].astype(str).str.strip() != ""]
        cfg = build_cfg()
        holdings_list = []
        today = pd.Timestamp.today().date()
        for _, row in valid.iterrows():
            code = fix_stock_code(row["股票代號"], cfg["etf_fix_map"])
            if code is None:
                continue
            shares_val = int(row["持有股數"]) if pd.notna(row.get("持有股數")) else None
            holdings_list.append({
                "code": code,
                "company_name": str(row.get("公司名稱", "")).strip(),
                "entry_price": float(row["成本價"]) if pd.notna(row.get("成本價")) else 0,
                "entry_date": today,  # 無進場日欄位，預設今天（時間停損從今天起算）
                "shares": shares_val,
            })

        bar, log_area, buf, handler = make_progress_block("持股分析")
        logging.getLogger().addHandler(handler)

        def h_progress(stage, pct, msg):
            bar.progress(min(pct, 1.0), text=f"{stage} — {msg}")
            log_area.code("\n".join(buf[-30:]) or "（執行中…）")

        try:
            with st.spinner("分析中 …"):
                h_result_new = run_holdings_scan(
                    cfg=cfg, holdings=holdings_list, progress_cb=h_progress,
                )
            st.session_state["holdings_result"] = h_result_new
            st.session_state["holdings_analyzed_at"] = datetime.now().strftime("%H:%M:%S")
        except Exception as e:
            st.error(f"分析失敗：{e}")
        finally:
            logging.getLogger().removeHandler(handler)
        bar.progress(1.0, text="完成")
        st.rerun()

    # ============ 分析結果 ============
    if "holdings_result" in st.session_state:
        h_df = st.session_state["holdings_result"]["df"].copy()
        if "操作建議" in h_df.columns:
            for sym in ["⛔", "🟢", "🔴", "🟡", "⌛", "✅", "❓", "⚠️"]:
                h_df["操作建議"] = h_df["操作建議"].astype(str).str.replace(sym, "")
            h_df["操作建議"] = h_df["操作建議"].str.strip()

        urgent_keywords = ["停損", "技術轉弱", "+2R", "+1R", "時間停損", "移動停利"]
        urgent = h_df[h_df["操作建議"].apply(
            lambda a: any(k in str(a) for k in urgent_keywords)
        )] if "操作建議" in h_df.columns else h_df.iloc[0:0]
        hold = h_df.drop(urgent.index) if len(urgent) else h_df

        st.divider()

        # ===== 今天行動摘要（一眼看懂今天要做什麼）=====
        qty_col = h_df.get("賣出量", pd.Series(dtype=str)).astype(str)
        n_sell = int(qty_col.str.contains("全出").sum())
        n_half = int(qty_col.str.contains("賣半").sum())
        n_hold = int(qty_col.str.contains("保留").sum())
        st.markdown(
            f"<div style='font-size:14px;margin-bottom:6px;'>📋 <b>今天</b>："
            f"<span style='color:#DC2626;font-weight:700;'>{n_sell} 檔要賣</span> · "
            f"<span style='color:#D97706;font-weight:700;'>{n_half} 檔減半</span> · "
            f"<span style='color:#059669;'>{n_hold} 檔續抱</span></div>",
            unsafe_allow_html=True,
        )

        # 優先顯示需要動作（紅色強調 banner）
        if len(urgent):
            st.markdown(
                f"<div class='holdings-alert'>"
                f"⚠ 有 <b>{len(urgent)}</b> 檔持股建議立即處理"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.dataframe(urgent, use_container_width=True, hide_index=True)
        else:
            st.markdown(
                "<div class='holdings-ok'>✓ 所有持股目前皆建議續抱</div>",
                unsafe_allow_html=True,
            )

        if len(hold):
            st.markdown("### 續抱")
            st.dataframe(hold, use_container_width=True, hide_index=True)

        # ============ 出場策略階梯 ============
        st.markdown("### 出場策略階梯")
        st.caption("每檔持股的完整出場規劃 — 觸發任一條件就執行對應動作")

        exit_cols = ["股票", "公司名稱", "成本價", "目前價", "報酬%",
                      "停損價", "目標1(+1R半倉)", "目標2(+2R出清)",
                      "移動停利MA10", "時間停損日", "技術轉弱觸發"]
        avail = [c for c in exit_cols if c in h_df.columns]
        exit_df = h_df[avail].copy()

        # 數值格式化 + help
        col_cfg_exit = {}
        exit_help = {
            "成本價": HELP["cost_price"],
            "目前價": HELP["current_price"],
            "停損價": HELP["stop_loss"],
            "目標1(+1R半倉)": HELP["target_1r"],
            "目標2(+2R出清)": HELP["target_2r"],
            "移動停利MA10": HELP["trail_stop_ma10"],
            "時間停損日": HELP["time_stop"],
            "技術轉弱觸發": HELP["tech_weak"],
        }
        for c in ["成本價", "目前價", "停損價", "目標1(+1R半倉)",
                   "目標2(+2R出清)", "移動停利MA10"]:
            if c in exit_df.columns:
                col_cfg_exit[c] = st.column_config.NumberColumn(
                    c, format="%.2f", help=exit_help.get(c),
                )
        if "報酬%" in exit_df.columns:
            col_cfg_exit["報酬%"] = st.column_config.NumberColumn(
                "報酬%", format="%.2f%%", help=HELP["profit_pct"],
            )
        for c in ["時間停損日", "技術轉弱觸發"]:
            if c in exit_df.columns:
                col_cfg_exit[c] = st.column_config.TextColumn(c, help=exit_help.get(c))

        st.dataframe(exit_df, use_container_width=True, hide_index=True,
                      column_config=col_cfg_exit)

        with st.expander("出場規則說明"):
            st.markdown("""
- **停損價** — 跌破即全出，由 MA20 與近 10 日低點取較高者
- **目標 1 (+1R)** — 觸及賣出 1/2 鎖利（剩餘半倉轉移動停利）
- **目標 2 (+2R)** — 觸及全部出清
- **移動停利 (MA10)** — 已有 5% 以上獲利時，跌破 MA10 全出鎖利
- **時間停損** — 進場後 10 個交易日仍未到 +1R 全出（換股提升資金效率）
- **技術轉弱** — K 死叉 D 且跌破 MA20 → 動能消失，提早出場
            """)

        h_buf = io.BytesIO()
        with pd.ExcelWriter(h_buf, engine="openpyxl") as writer:
            h_df.to_excel(writer, sheet_name="持股賣出建議", index=False)
        h_buf.seek(0)
        st.download_button(
            "下載持股報告", data=h_buf.getvalue(),
            file_name="持股賣出建議.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# =====================================================
# Tab 3: 回測
# =====================================================
with tab3:
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
        cc1.checkbox("計入交易成本", value=_bc.get("enabled", True), key="cost_enabled")
        cc2.number_input("手續費率 %", 0.0, 0.5,
                         _bc.get("fee_rate", 0.001425) * 100, 0.01, key="cost_fee")
        cc3.number_input("券商折數", 0.1, 1.0,
                         float(_bc.get("fee_discount", 1.0)), 0.05, key="cost_disc")
        cc4.number_input("證交稅 %", 0.0, 0.5,
                         _bc.get("tax_rate", 0.003) * 100, 0.05, key="cost_tax")
        st.checkbox("因子驗證也扣成本", value=_bc.get("apply_to_factor_eval", False),
                    key="cost_apply_fe",
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
            st.error("請從側欄選擇資料來源（上傳清單或全台股）")
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

    st.divider()

    if "backtest_result" not in st.session_state:
        st.info("設定參數後點「**跑回測**」")
    else:
        bt = st.session_state["backtest_result"]
        s = bt["summary"]

        # Edge 燈號條（全寬）
        _costs_on = st.session_state.get("cost_enabled", True)
        st.caption("📊 報酬已扣來回交易成本" if _costs_on else "⚠ 未計交易成本（期望值偏樂觀）")
        render_edge_meter(s["期望值R"])
        st.markdown("")

        # KPI
        c = st.columns(4)
        c[0].metric("總交易數", fmt_int(s["總交易數"]),
                      help="回測期間累計模擬交易筆數")
        c[1].metric("勝率 %", f"{s['勝率%']}%",
                     delta=f"{s['勝率%']-50:.1f}%" if s["勝率%"] else None,
                     help=HELP["win_rate"])
        c[2].metric("平均 R", s["平均R"], help=HELP["avg_r"])
        c[3].metric("最大回撤 R", s["最大回撤R"], help=HELP["max_dd_r"])

        c2 = st.columns(3)
        c2[0].metric("平均報酬 %", f"{s['平均報酬%']}%",
                       help="每筆交易報酬% 的平均")
        c2[1].metric("最大單筆 %", f"{s['最大單筆%']}%",
                       help="所有交易中單筆最大獲利%")
        c2[2].metric("期望值 R", s["期望值R"], help=HELP["expectancy_r"])

        # 統計顯著性
        if "期望值R_CI下界" in s:
            ci_txt = f"期望值R 95% CI = [{s['期望值R_CI下界']}, {s['期望值R_CI上界']}]"
            if s.get("顯著正Edge"):
                st.success(f"✅ {ci_txt}（下界 > 0，達顯著正 edge）")
            else:
                st.warning(f"⚠ {ci_txt}（CI 跨 0，未達顯著 — 勿據此調參）")
            if s.get("樣本警示"):
                st.warning(f"⚠ 樣本可信度：{s.get('樣本可信度', '')} — 統計噪音大，勿過度解讀")
            else:
                st.caption(f"樣本可信度：{s.get('樣本可信度', '')}")

        # 樣本外（OOS）驗證 — 最能代表真實期望值
        oos_split = bt.get("oos_split")
        if oos_split and oos_split.get("n_oos", 0) > 0:
            oos = oos_split["oos"]
            st.markdown("#### 🎯 樣本外（OOS）— 只信這個")
            st.caption("用前段資料挑參數、後段驗證；OOS 期望值才避開了選參偏誤。")
            oc = st.columns(4)
            oc[0].metric("OOS 交易數", fmt_int(oos["總交易數"]))
            oc[1].metric("OOS 勝率 %", f"{oos['勝率%']}%")
            oc[2].metric("OOS 平均 R", oos["平均R"])
            oc[3].metric("OOS 期望值 R", oos["期望值R"])
            if oos_split["n_oos"] < 30:
                st.warning(f"⚠ OOS 僅 {oos_split['n_oos']} 筆（<30），期望值僅供參考")
            elif oos.get("顯著正Edge"):
                st.success(f"✅ OOS 期望值R CI = [{oos['期望值R_CI下界']}, {oos['期望值R_CI上界']}]，樣本外仍顯著為正")
            else:
                st.warning(f"⚠ OOS 期望值R CI = [{oos['期望值R_CI下界']}, {oos['期望值R_CI上界']}]，樣本外未達顯著")
            with st.expander("樣本內 IS / 全體 對照"):
                ist, ov = oos_split["is"], oos_split["overall"]
                st.dataframe(pd.DataFrame([
                    {"分組": "樣本內 IS", "交易數": ist["總交易數"], "勝率%": ist["勝率%"], "期望值R": ist["期望值R"]},
                    {"分組": "樣本外 OOS", "交易數": oos["總交易數"], "勝率%": oos["勝率%"], "期望值R": oos["期望值R"]},
                    {"分組": "全體", "交易數": ov["總交易數"], "勝率%": ov["勝率%"], "期望值R": ov["期望值R"]},
                ]), use_container_width=True, hide_index=True)
                st.caption("IS 因事後挑門檻而樂觀；IS 遠優於 OOS = 過擬合警訊。")

        # 各大盤 Regime 拆解
        by_regime = bt.get("by_regime")
        if by_regime is not None and len(by_regime):
            st.markdown("### 各大盤 Regime 拆解")
            st.caption("策略在空頭組的 edge 若大幅衰減 → 代表高度依賴大盤多頭，需靠大盤過濾保護。")
            st.dataframe(
                by_regime[["大盤狀態", "總交易數", "勝率%", "平均R", "期望值R", "最大回撤R"]],
                use_container_width=True, hide_index=True,
            )
            fig_r = go.Figure(go.Bar(
                x=by_regime["大盤狀態"], y=by_regime["期望值R"],
                marker_color=["#059669" if v > 0.2 else ("#D97706" if v > 0 else "#DC2626")
                               for v in by_regime["期望值R"]],
                text=[f"{v:.2f}" for v in by_regime["期望值R"]],
                textposition="outside", marker_line_width=0,
            ))
            fig_r.update_layout(
                height=240, margin=dict(l=8, r=8, t=8, b=8),
                plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                showlegend=False, yaxis_title="期望值 R",
                font=dict(family="Inter, sans-serif", size=11),
            )
            fig_r.update_xaxes(showgrid=False)
            fig_r.update_yaxes(showgrid=True, gridcolor="#F1F5F9")
            st.plotly_chart(fig_r, use_container_width=True,
                             config={"displayModeBar": False})

        if len(bt["trades"]):
            st.markdown("### 累積 R 與 Drawdown")
            render_drawdown_chart(bt["trades"])

            st.markdown("### 月度 R 分布")
            render_monthly_returns(bt["trades"])

            tcol1, tcol2 = st.columns(2)
            with tcol1:
                st.markdown("### Top 10 個股")
                st.dataframe(
                    bt["by_symbol"].head(10),
                    use_container_width=True, hide_index=True,
                )
            with tcol2:
                st.markdown("### Worst 10 個股")
                st.dataframe(
                    bt["by_symbol"].tail(10).sort_values("期望值R"),
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

            # ===== 敏感度分析 =====
            st.divider()
            st.markdown("### 敏感度分析")
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
                # 視覺化期望值
                fig_s = go.Figure(go.Bar(
                    x=sens_df["min_score"], y=sens_df["期望值R"],
                    marker_color=["#059669" if v > 0.2 else ("#D97706" if v > 0 else "#DC2626")
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

            # ===== 參數高原圖 =====
            st.divider()
            st.markdown("### 參數高原圖")
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
                ptab = pl["table"]; pinfo = pl["plateau"]
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
                    fig_p.add_vrect(x0=lo, x1=hi, fillcolor="#059669", opacity=0.12, line_width=0)
                for pk in pinfo["peaks"]:
                    fig_p.add_trace(go.Scatter(
                        x=[ptab["param_value"].iloc[pk]], y=[ptab["期望值R"].iloc[pk]],
                        mode="markers", marker=dict(color="#DC2626", size=12, symbol="x"),
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
                    st.success(f"✅ 建議穩健參數（高原中點）：**{pinfo['recommended']}**（綠色區段）")
                else:
                    st.warning("⚠ 找不到明顯高原 — 曲線可能過於起伏（樣本不足或策略不穩），勿挑單一尖峰")
                st.dataframe(ptab, use_container_width=True, hide_index=True)

            # ===== 因子增量貢獻驗證 =====
            st.divider()
            st.markdown("### 因子驗證（增量貢獻）")
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
                        marker_color=["#059669" if v > 0.02 else ("#D97706" if v > 0 else "#DC2626")
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
                from src.runner import run_weight_suggest
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
                    if st.button("套用建議權重到側欄", key="apply_lift_weights"):
                        _map = {
                            "breakout_with_volume": "w_breakout", "ma_bullish": "w_ma",
                            "turnover_strong": "w_turnover", "kd": "w_kd", "macd": "w_macd",
                            "rel_strength": "w_rs", "trend_confirm": "w_trend",
                        }
                        for sc_key, ss_key in _map.items():
                            if sc_key in sug["weights"]:
                                st.session_state[ss_key] = int(sug["weights"][sc_key])
                        st.toast("已套用建議權重，請看側欄「評分權重」", icon="✅")
                        st.rerun()

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


# =====================================================
# Tab 4: 歷史
# =====================================================
with tab4:
    st.markdown("### 掃描歷史")
    st.caption("自動保存最近 30 次掃描，可隨時回看當日結果。")
    scans = list_scans()
    if not scans:
        st.info("尚無歷史紀錄 — 跑一次掃描就會自動存檔")
    else:
        meta_df = pd.DataFrame([{
            "時間": s["timestamp"],
            "標籤": s["label"],
            "大盤": s.get("market", "—"),
            "掃描": s.get("n_total", 0),
            "進場": s.get("n_enter", 0),
            "觀察": s.get("n_watch", 0),
            "耗時(秒)": s.get("elapsed_sec", "—"),
            "_path": s["_path"],
        } for s in scans])
        display_meta = meta_df.drop(columns=["_path"])
        st.dataframe(display_meta, use_container_width=True, hide_index=True)

        sel = st.selectbox(
            "查看明細",
            options=meta_df["時間"].tolist(),
            index=0,
        )
        if sel:
            row = meta_df[meta_df["時間"] == sel].iloc[0]
            old_df = load_scan_df(row["_path"])
            if old_df is not None and len(old_df):
                st.markdown(f"**{sel}** — 進場 {row['進場']} · 觀察 {row['觀察']}")
                # 只顯示精簡欄位
                cols_pref = ["股票", "公司名稱", "操作建議", "評分顯示",
                              "進場參考價", "停損價", "風險%", "建議張數", "換手率%"]
                show_cols = [c for c in cols_pref if c in old_df.columns]
                st.dataframe(old_df[show_cols], use_container_width=True,
                              hide_index=True)
            else:
                st.warning("找不到該次掃描的資料檔")


# =====================================================
# Tab 5: 操作教學
# =====================================================
with tab5:
    st.markdown("## 📖 系統操作教學")
    st.caption("從挑標的 → 定價格 → 管理賣出的完整流程。所有名詞可點欄位旁的 (?) 看說明。")

    st.info("**一句話流程**：大盤綠燈 → 掃描挑「進場＋法人買超＋RS強＋沒追高＋沒臨財報」"
            "→ 照卡片的進場/停損/目標/張數下單 → 持股管理每天看賣出建議 → 嚴守停損。")

    with st.expander("⓪ 先選「策略模式」（側欄最上方）", expanded=True):
        st.markdown(
            "| 模式 | 抓什麼 | 適合 |\n"
            "|---|---|---|\n"
            "| **強勢突破** | 已突破創高＋量增＋法人買 | 追動能、買強勢（會買在已漲一段）|\n"
            "| **早期突破** | 只抓「剛突破、沒追高」 | 想參與突破但不想追高 |\n"
            "| **潛伏起漲前** | 窄幅整理＋量縮＋站穩均線＋接近未突破＋法人吸籌 | 想埋伏在發動前 |\n\n"
            "潛伏模式的進場建議顯示為「**埋伏 · 潛伏**」，是買在整理區、停損放箱底，等突破。\n"
            "三種模式的籌碼否決、部位管理、綜合評級都共用同一套。"
        )

    with st.expander("① 買之前先看「大盤」（紅燈別買）", expanded=True):
        st.markdown(
            "畫面最上方的 **大盤狀態**：\n\n"
            "- 🟢 **多頭** → 正常操作\n"
            "- 🟡 **中性** → 部位自動減半\n"
            "- 🔴 **空頭** → 整套停手，系統會自動把進場降級\n\n"
            "另有 **美股風險偏好**（VIX＋SPX）與台股取較保守者，一起影響建議張數。"
        )

    with st.expander("② 挑買入標的（買入掃描分頁）", expanded=True):
        st.markdown(
            "跑完掃描後，看候選卡片。一檔好買點要同時滿足：\n\n"
            "| 看哪一欄 | 理想狀態 | 意義 |\n"
            "|---|---|---|\n"
            "| **操作建議** | 進場 · 突破/拉回 | 系統判定可進場 |\n"
            "| **評分顯示** | 越高越好（如 ≥7/10） | 多條件同時成立 |\n"
            "| **籌碼確認** | 法人買超 / 法人連買N日 | 有大戶在買 |\n"
            "| **相對強度RS%** | 正值、越大越好 | 比大盤強 |\n"
            "| **族群同步** | 同步 2 檔以上 | 整族群在動有撐 |\n"
            "| **現價偏離%** | 接近 0（別超過 +3~5%） | 沒追高 |\n\n"
            "**出現這些要跳過 / 小心**（系統會自動降級或警示）：\n"
            "- ⚠ 籌碼確認 = **法人賣超** → 突破恐是出貨\n"
            "- ⚠ 融資券提示 = **融資爆增** → 散戶過熱反指標\n"
            "- ⚠ **距財報日** 很近（前 3 日內）→ 避開財報波動\n"
            "- ⚠ **部位提示** 有「追高 / 乖離過熱」→ 等回檔"
        )

    with st.expander("③ 價格怎麼定（卡片已算好，照抄）", expanded=True):
        st.markdown(
            "| 欄位 | 怎麼用 |\n"
            "|---|---|\n"
            "| **進場參考價** | 你的買入掛單價 |\n"
            "| **停損價** | 跌破就無條件賣出（ATR 抓好風險距離）|\n"
            "| **目標價1(+1R半倉)** | 到這裡先賣一半鎖利 |\n"
            "| **目標價2(+2R出清)** | 到這裡全部出清 |\n"
            "| **建議張數** | 固定風險法算好（含資金上限、族群降碼）|\n\n"
            "🔑 **紀律**：進場前先把停損價設好，停損是唯一不能凹的。"
        )

    with st.expander("④ 賣出管理（持股管理分頁）", expanded=True):
        st.markdown(
            "把持股填進去（代號、成本價、進場日、股數），系統每天看 **操作建議** 欄：\n\n"
            "| 系統建議 | 你做什麼 |\n"
            "|---|---|\n"
            "| ⛔ 停損出清 | 全部賣（跌破停損）|\n"
            "| 🔴 技術轉弱 | 全部賣（KD 死叉＋跌破 MA20）|\n"
            "| 🟢 達 +1R 半倉鎖利 | 賣一半 |\n"
            "| 🟢 達 +2R 出清 | 全部賣 |\n"
            "| 🟡 移動停利(ATR) | 全部賣（獲利後跌破移動停利線）|\n"
            "| ⌛ 時間停損 | 全部賣（抱太久沒漲）|\n"
            "| ✅ 續抱 | 留著，每天再看 |\n\n"
            "賣出價參考同列的 **停損價 / 目標1 / 目標2 / 移動停利(ATR)**。"
        )

    with st.expander("⑤ ⚠ 最重要：先驗證策略有沒有效（回測分頁）", expanded=True):
        st.markdown(
            "**別拿沒驗證的設定下單。** 在回測分頁：\n\n"
            "1. 跑回測 → 只看 **🎯 OOS 期望值R（樣本外）**，要 **> 0 且 CI 不跨 0** 才算有 edge\n"
            "2. 看 **Regime 拆解** → 確認不是只在多頭賺\n"
            "3. 跑 **因子驗證 / 參數高原圖** → 砍掉沒貢獻的因子、參數取穩健中點\n\n"
            "→ 報酬已內扣台股來回交易成本（手續費＋證交稅約 0.45~0.6%），數字才可信。"
        )

    st.divider()
    st.caption("⚠ 本工具為技術＋籌碼面決策輔助，非投資建議。籌碼/融資/財報為當日 best-effort 資料，"
               "最終下單與風險自負。系統僅涵蓋上市股，不含上櫃。")
