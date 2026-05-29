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
    page_icon="·",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "**台股強勢突破掃描器** v0.3"
    },
)


# =====================================================
# 全域樣式 — 細緻、低彩度、Inter 字體
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

/* 字體：只套到一般文字節點，避免覆蓋 Material Symbols icon 字體 */
html, body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    color: var(--text);
}
.stMarkdown, .stText, p, span:not([class*="material-symbols"]):not([class*="icon"]),
div:not([class*="material-symbols"]):not([class*="icon"]),
label, h1, h2, h3, h4, h5, h6, button {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
}
code, pre, [data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace;
}
/* 保留 Material Symbols icon 字體，不被 Inter 蓋掉 */
[class*="material-symbols"],
.material-symbols-outlined, .material-symbols-rounded, .material-symbols-sharp,
[data-testid*="Icon"], [data-testid*="icon"] {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Symbols Sharp' !important;
    font-feature-settings: 'liga';
}

#MainMenu, footer { visibility: hidden; height: 0; }
[data-testid="stHeader"] { background: transparent; }

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 1rem;
    max-width: 1400px;
}

/* --- Headings --- */
h1 { font-weight: 700 !important; letter-spacing: -0.02em; font-size: 1.6rem !important; }
h2 { font-weight: 600 !important; letter-spacing: -0.01em; font-size: 1.2rem !important; margin-top: 1.5rem !important; }
h3 { font-weight: 600 !important; font-size: 1.0rem !important; color: var(--text); margin-top: 1.2rem !important; }

/* --- 自訂頁首 --- */
.app-header {
    display: flex; justify-content: space-between; align-items: baseline;
    padding-bottom: 12px; border-bottom: 1px solid var(--border-2);
    margin-bottom: 16px;
}
.app-title { font-size: 1.4rem; font-weight: 700; letter-spacing: -0.02em; }
.app-sub  { color: var(--muted); font-size: 0.85rem; }
.app-date { color: var(--subtle); font-size: 0.8rem; font-variant-numeric: tabular-nums; }

/* --- metric --- */
[data-testid="stMetric"] {
    background: var(--surface);
    padding: 12px 14px;
    border-radius: 8px;
    border: 1px solid var(--border);
    box-shadow: none;
}
[data-testid="stMetricLabel"] {
    color: var(--muted) !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    letter-spacing: 0;
}
[data-testid="stMetricValue"] {
    font-size: 1.3rem !important;
    font-weight: 600 !important;
    color: var(--text) !important;
}
[data-testid="stMetricDelta"] { font-size: 0.75rem !important; }

/* --- 大盤橫幅 --- */
.banner {
    padding: 10px 14px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--surface);
    margin-bottom: 14px;
    display: flex; align-items: center; gap: 10px;
    font-size: 0.9rem;
}
.banner .dot {
    width: 8px; height: 8px; border-radius: 50%; display: inline-block;
}
.banner.bull    { border-left: 3px solid var(--positive); }
.banner.bull .dot    { background: var(--positive); }
.banner.bear    { border-left: 3px solid var(--negative); }
.banner.bear .dot    { background: var(--negative); }
.banner.neutral { border-left: 3px solid var(--warning); }
.banner.neutral .dot { background: var(--warning); }
.banner.unknown { border-left: 3px solid var(--subtle); }
.banner.unknown .dot { background: var(--subtle); }
.banner b { font-weight: 600; }
.banner .sep { color: var(--border); margin: 0 4px; }

/* --- 候選卡片 --- */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 8px;
    transition: border-color 0.15s;
}
.card:hover { border-color: var(--subtle); }
.card.go    { border-left: 3px solid var(--positive); }
.card.watch { border-left: 3px solid var(--warning); }
.card.skip  { border-left: 3px solid var(--subtle); }

.card-head {
    display: flex; justify-content: space-between; align-items: baseline;
    margin-bottom: 4px;
}
.card-title { font-size: 0.95rem; font-weight: 600; }
.card-title .code { font-family: 'JetBrains Mono', monospace; color: var(--muted); margin-right: 6px; font-size: 0.85rem; }
.card-meta { color: var(--muted); font-size: 0.78rem; }
.card-action {
    font-size: 0.75rem; font-weight: 500;
    padding: 2px 8px; border-radius: 12px;
    background: var(--slate-2); color: var(--slate);
}
.card-action.go    { background: var(--positive-2); color: var(--positive); }
.card-action.watch { background: var(--warning-2); color: var(--warning); }
.card-action.skip  { background: var(--slate-2); color: var(--slate); }

.card-grid {
    display: grid; grid-template-columns: repeat(7, 1fr);
    gap: 8px 16px; margin-top: 10px;
    font-size: 0.82rem;
}
.card-grid .label { color: var(--muted); font-size: 0.72rem; margin-bottom: 2px; }
.card-grid .value { font-weight: 600; color: var(--text); font-variant-numeric: tabular-nums; }

.warn-text { color: var(--warning); font-size: 0.75rem; margin-top: 6px; }

/* --- Tabs --- */
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] {
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    padding: 8px 14px !important;
    color: var(--muted) !important;
}
.stTabs [aria-selected="true"] { color: var(--text) !important; font-weight: 600 !important; }

/* --- Sidebar --- */
[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }
[data-testid="stSidebar"] .stMarkdown h3 { font-size: 0.85rem !important; color: var(--muted) !important; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px !important; }
[data-testid="stSidebar"] [data-testid="stExpander"] {
    border: 1px solid var(--border); border-radius: 6px; background: var(--bg);
    margin-bottom: 6px;
}
[data-testid="stSidebar"] [data-testid="stExpander"] details summary {
    font-size: 0.85rem; font-weight: 500;
}

/* --- Buttons --- */
button[kind="primary"] {
    background: var(--primary) !important;
    border: 1px solid var(--primary) !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
}
button[kind="secondary"] {
    border-radius: 6px !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    font-weight: 500 !important;
    background: var(--surface) !important;
}
button[kind="secondary"]:hover {
    border-color: var(--subtle) !important;
    background: var(--bg) !important;
}

/* --- Dataframe --- */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: 6px;
}

/* --- Progress bar --- */
[data-testid="stProgress"] > div > div > div { background-color: var(--primary) !important; }

/* --- Info / warning / error boxes 統一柔化 --- */
[data-testid="stAlert"] {
    border-radius: 6px !important;
    border: 1px solid var(--border) !important;
    background: var(--surface) !important;
    color: var(--text) !important;
}
</style>
""", unsafe_allow_html=True)


# =====================================================
# 頁首
# =====================================================
st.markdown(
    f"""
<div class='app-header'>
  <div>
    <div class='app-title'>台股強勢突破掃描器</div>
    <div class='app-sub'>加權評分 · 換手率分析 · 操作建議</div>
  </div>
  <div class='app-date'>{pd.Timestamp.today().strftime('%Y / %m / %d  %A')}</div>
</div>
""",
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
# 側欄
# =====================================================
with st.sidebar:
    st.markdown("### 設定")

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
                "twse": "上市普通股 + ETF (~1180)",
                "twse-common": "僅普通股 (~1030)",
                "twse-etf": "僅 ETF (~150)",
            }[x],
        )
        st.caption("首次約 5–15 分鐘；同日重跑 < 1 分鐘")

    st.markdown("")
    run_btn = st.button("開始掃描", type="primary", use_container_width=True)

    st.divider()

    with st.expander("部位管理", expanded=True):
        ps = base_cfg.get("position_sizing", {})
        total_capital = st.number_input(
            "總資金（元）", min_value=100_000,
            value=int(ps.get("total_capital", 1_000_000)),
            step=100_000,
        )
        risk_pct = st.slider(
            "單筆風險 %", 0.5, 5.0,
            float(ps.get("risk_per_trade_pct", 0.01)) * 100, 0.25,
            help="每筆交易最大可接受虧損 = 總資金 × 此比例",
        ) / 100
        max_pos_pct = st.slider(
            "單檔最大佔比 %", 5, 50,
            int(ps.get("max_position_pct", 0.20) * 100), 5,
        ) / 100

    with st.expander("品質過濾", expanded=False):
        f = base_cfg["filters"]
        min_price = st.number_input(
            "最低股價", min_value=0.0,
            value=float(f["min_price"]), step=1.0,
        )
        min_avg_volume = st.number_input(
            "20 日均量下限（股）", min_value=0,
            value=int(f["min_avg_volume"]), step=100_000,
        )
        require_ma60 = st.checkbox(
            "必須站上 MA60",
            value=bool(f.get("require_above_ma60", True)),
        )
        min_risk_pct = st.slider(
            "最小停損距離 %", 0.0, 10.0,
            float(f.get("min_risk_pct", 0.02)) * 100, 0.5,
        ) / 100

    with st.expander("評分權重 / 門檻", expanded=False):
        w = base_cfg["scoring"]["weights"]
        w_breakout = st.slider("突破 + 量增", 0, 5, int(w["breakout_with_volume"]))
        w_ma = st.slider("MA 多頭", 0, 5, int(w["ma_bullish"]))
        w_turnover = st.slider("換手率強勢", 0, 5, int(w["turnover_strong"]))
        w_kd = st.slider("KD", 0, 5, int(w["kd"]))
        w_macd = st.slider("MACD", 0, 5, int(w["macd"]))

        max_total = w_breakout + w_ma + w_turnover + w_kd + w_macd
        st.caption(f"總分上限：{max_total}")

        thr = base_cfg["scoring"]["thresholds"]
        thr_strong = st.number_input("強勢候選 ≥", 0, 20, int(thr["strong"]))
        thr_watch = st.number_input("觀察 ≥", 0, 20, int(thr["watch"]))
        thr_weak = st.number_input("偏弱觀察 ≥", 0, 20, int(thr["weak"]))

    with st.expander("回測", expanded=False):
        bt_lookback = st.number_input("回測天數", 30, 500, 120, 30)
        bt_hold = st.number_input("持有天數", 3, 60, 10, 1)
        bt_min_score = st.number_input("最低評分", 0, 20, 5, 1)
        run_bt_btn = st.button("跑回測", use_container_width=True)


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
    bar = st.progress(0.0, text=f"{title} 準備中 …")
    log_area = st.expander("執行記錄", expanded=False).empty()
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
    cls = {"bull": "bull", "bear": "bear", "neutral": "neutral"}.get(regime, "unknown")
    label = market_state["label"].split(" ", 1)[-1] if " " in market_state["label"] else market_state["label"]
    # 去掉舊版的 emoji 標籤
    label = label.replace("🟢", "").replace("🔴", "").replace("🟡", "").replace("⚪", "").strip()
    st.markdown(
        f"""
<div class='banner {cls}'>
  <span class='dot'></span>
  <span><b>大盤狀態</b><span class='sep'>·</span>{label}<span class='sep'>·</span>{market_state['detail']}</span>
</div>
""",
        unsafe_allow_html=True,
    )


def _action_class(action):
    s = str(action)
    if "買入" in s:
        return "go"
    if "停損" in s or "賣" in s or "不操作" in s or "出清" in s or "暫不" in s or "跳過" in s:
        return "skip"
    return "watch"


# =====================================================
# 執行買入掃描
# =====================================================
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
            st.info(f"將掃描 **{len(items)}** 檔")
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
        log_area.code("\n".join(buf[-30:]) or "（執行中…）")

    try:
        with st.spinner("掃描中 …"):
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
        log_area.code("\n".join(buf[-30:]) or "（執行中…）")

    try:
        with st.spinner("回測中 …"):
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
# 大盤狀態橫幅
# =====================================================
if "result" in st.session_state:
    render_market_banner(st.session_state["result"].get("market_state"))


# =====================================================
# Tabs
# =====================================================
tab1, tab2, tab3 = st.tabs(["買入掃描", "持股管理", "回測"])


# =====================================================
# Tab 1：買入掃描
# =====================================================
def render_top_candidates(df, n=10):
    if "訊號判斷" not in df.columns:
        return

    top = df[df["訊號判斷"] == "強勢候選"].head(n)
    if len(top) == 0:
        st.info("目前無強勢候選")
        return

    st.markdown("### Top 強勢候選")

    for _, row in top.iterrows():
        action = str(row.get("操作建議", ""))
        # 清掉所有舊版 emoji
        for sym in ["🟢", "🟡", "🔴", "⛔", "⚠️", "✅", "🏆", "📊"]:
            action = action.replace(sym, "").strip()
        cls = _action_class(action)

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

        tr_str = f"{turnover}%" if turnover is not None and pd.notna(turnover) else "—"
        warn_html = f"<div class='warn-text'>{warning}</div>" if warning else ""

        st.markdown(
            f"""
<div class='card {cls}'>
  <div class='card-head'>
    <div class='card-title'>
      <span class='code'>{row['股票']}</span>{row['公司名稱']}
    </div>
    <div class='card-action {cls}'>{action}</div>
  </div>
  <div class='card-meta'>評分 {score} · {entry_type}</div>
  <div class='card-grid'>
    <div><div class='label'>進場</div><div class='value'>{entry}</div></div>
    <div><div class='label'>停損</div><div class='value'>{stop}</div></div>
    <div><div class='label'>目標 1</div><div class='value'>{t1}</div></div>
    <div><div class='label'>目標 2</div><div class='value'>{t2}</div></div>
    <div><div class='label'>風險</div><div class='value'>{risk_pct_val}%</div></div>
    <div><div class='label'>建議</div><div class='value'>{lots} 張 · {cost_pct}%</div></div>
    <div><div class='label'>換手率</div><div class='value'>{tr_str}</div></div>
  </div>
  {warn_html}
</div>
""",
            unsafe_allow_html=True,
        )


def render_results_table(df, key_prefix=""):
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

    col_cfg = {}
    if "評分" in display.columns:
        col_cfg["評分"] = st.column_config.ProgressColumn(
            "評分", format="%d", min_value=0,
            max_value=int(display["評分"].max()) if len(display) else 8,
        )
    for c in ["風險%", "佔資金%", "換手率%", "20日平均換手率%"]:
        if c in display.columns:
            col_cfg[c] = st.column_config.NumberColumn(c, format="%.2f%%")
    if "進場成本" in display.columns:
        col_cfg["進場成本"] = st.column_config.NumberColumn("進場成本", format="%d")

    st.dataframe(
        display, use_container_width=True, height=500,
        column_config=col_cfg, hide_index=True,
    )

    return filtered


with tab1:
    if "result" not in st.session_state:
        st.info("從側欄設定資料來源後點「**開始掃描**」")
    else:
        result = st.session_state["result"]
        df = result["df"]
        summary = result["summary"]
        failed_df = result["failed_df"]

        s = summary.iloc[0]
        cols = st.columns(6)
        cols[0].metric("掃描", s["掃描股票數"])
        cols[1].metric("成功", s["成功分析檔數"])
        cols[2].metric("強勢候選", s["強勢候選檔數"])
        cols[3].metric("觀察", s["觀察檔數"])
        cols[4].metric("偏弱", s["偏弱觀察檔數"])
        cols[5].metric("耗時 (秒)", s["執行秒數"])

        render_top_candidates(df, n=10)

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
            "下載 Excel 報告",
            data=buf.getvalue(),
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
# Tab 2：持股管理
# =====================================================
with tab2:
    st.markdown("### 我的持股")
    st.caption("直接在表格內編輯。儲存在瀏覽器 session — 刷新會清空，記得「匯出」備份。")

    if "holdings_df" not in st.session_state:
        st.session_state["holdings_df"] = pd.DataFrame([
            {"股票代號": "", "公司名稱": "", "進場價": 0.0,
             "進場日": pd.Timestamp.today().normalize(), "持有張數": 1},
        ])

    tb = st.columns([1, 1, 1, 1, 2])
    if tb[0].button("新增列", use_container_width=True):
        new_row = pd.DataFrame([{
            "股票代號": "", "公司名稱": "", "進場價": 0.0,
            "進場日": pd.Timestamp.today().normalize(), "持有張數": 1,
        }])
        st.session_state["holdings_df"] = pd.concat(
            [st.session_state["holdings_df"], new_row], ignore_index=True,
        )
        st.rerun()
    if tb[1].button("載入範例", use_container_width=True):
        if Path("holdings.example.xlsx").exists():
            ex = pd.read_excel("holdings.example.xlsx")
            ex["進場日"] = pd.to_datetime(ex["進場日"])
            st.session_state["holdings_df"] = ex
            st.rerun()
        else:
            st.warning("找不到 holdings.example.xlsx")
    if tb[2].button("清空", use_container_width=True):
        st.session_state["holdings_df"] = pd.DataFrame(columns=[
            "股票代號", "公司名稱", "進場價", "進場日", "持有張數",
        ])
        st.rerun()

    e_buf = io.BytesIO()
    with pd.ExcelWriter(e_buf, engine="openpyxl") as writer:
        st.session_state["holdings_df"].to_excel(writer, sheet_name="持股", index=False)
    e_buf.seek(0)
    tb[3].download_button(
        "匯出", data=e_buf.getvalue(),
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

    st.markdown("")

    if st.button("分析持股", type="primary"):
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
                log_area.code("\n".join(buf[-30:]) or "（執行中…）")

            try:
                with st.spinner("分析中 …"):
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

    if "holdings_result" in st.session_state:
        st.markdown("")
        h_df = st.session_state["holdings_result"]["df"]
        # 清理 action 欄位的舊版 emoji
        if "操作建議" in h_df.columns:
            h_df = h_df.copy()
            h_df["操作建議"] = h_df["操作建議"].astype(str).apply(
                lambda x: x.replace("⛔", "").replace("🟢", "").replace("🔴", "")
                          .replace("🟡", "").replace("⌛", "").replace("✅", "")
                          .replace("❓", "").replace("⚠️", "").strip()
            )
        action_counts = h_df["操作建議"].value_counts() if "操作建議" in h_df.columns else {}

        if len(action_counts):
            st.markdown("### 操作摘要")
            cols = st.columns(min(len(action_counts), 6) or 1)
            for i, (action, cnt) in enumerate(action_counts.items()):
                cols[i % len(cols)].metric(action, int(cnt))

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
            st.markdown("### 需要動作")
            st.dataframe(urgent, use_container_width=True, hide_index=True)
        if len(hold):
            st.markdown("### 續抱")
            st.dataframe(hold, use_container_width=True, hide_index=True)

        h_buf = io.BytesIO()
        with pd.ExcelWriter(h_buf, engine="openpyxl") as writer:
            h_df.to_excel(writer, sheet_name="持股賣出建議", index=False)
        h_buf.seek(0)
        st.download_button(
            "下載持股報告",
            data=h_buf.getvalue(),
            file_name="持股賣出建議.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# =====================================================
# Tab 3：回測
# =====================================================
with tab3:
    if "backtest_result" not in st.session_state:
        st.info("從側欄展開「**回測**」設定後點「**跑回測**」")
    else:
        bt = st.session_state["backtest_result"]
        s = bt["summary"]

        c = st.columns(4)
        c[0].metric("總交易數", s["總交易數"])
        c[1].metric(
            "勝率 %", f"{s['勝率%']}%",
            delta=f"{s['勝率%']-50:.1f}%" if s["勝率%"] else None,
            delta_color="normal",
        )
        edge_label = "有 edge" if s["期望值R"] > 0.2 else ("偏弱" if s["期望值R"] > 0 else "無 edge")
        c[2].metric("期望值 R", s["期望值R"], delta=edge_label, delta_color="off")
        c[3].metric("平均報酬 %", f"{s['平均報酬%']}%")

        c2 = st.columns(3)
        c2[0].metric("平均 R", s["平均R"])
        c2[1].metric("最大單筆 %", f"{s['最大單筆%']}%")
        c2[2].metric("最大回撤 R", s["最大回撤R"])

        if len(bt["trades"]):
            st.markdown("### 累積 R 曲線")
            trades = bt["trades"].copy()
            trades = trades.sort_values("entry_date")
            trades["累積R"] = trades["r_multiple"].fillna(0).cumsum()
            st.line_chart(trades.set_index("entry_date")[["累積R"]], height=280)

            st.markdown("### 個股期望值排序（Top 30）")
            st.dataframe(bt["by_symbol"].head(30), use_container_width=True, hide_index=True)

            st.markdown("### 交易明細")
            st.dataframe(bt["trades"], use_container_width=True, height=400, hide_index=True)

            buf_bt = io.BytesIO()
            with pd.ExcelWriter(buf_bt, engine="openpyxl") as writer:
                pd.DataFrame([s]).to_excel(writer, sheet_name="摘要", index=False)
                bt["trades"].to_excel(writer, sheet_name="交易明細", index=False)
                if len(bt["by_symbol"]):
                    bt["by_symbol"].to_excel(writer, sheet_name="個股統計", index=False)
            buf_bt.seek(0)
            st.download_button(
                "下載回測報告",
                data=buf_bt.getvalue(),
                file_name="回測報告.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.warning("回測無任何交易產生 — 試試降低「最低評分」門檻")
