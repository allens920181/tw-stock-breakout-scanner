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
from src.history import cleanup_old, list_scans, load_scan_df, save_scan
from src.market import classify_market
from src.preferences import load_prefs, save_prefs
from src.report import write_excel
from src.runner import run_backtest, run_holdings_scan, run_scan, run_sensitivity
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

.banner {
    padding: 10px 14px; border-radius: 6px;
    border: 1px solid var(--border); background: var(--surface);
    margin-bottom: 14px; display: flex; align-items: center; gap: 10px;
    font-size: 0.9rem;
}
.banner .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.banner.bull    { border-left: 3px solid var(--positive); }
.banner.bull .dot { background: var(--positive); }
.banner.bear    { border-left: 3px solid var(--negative); }
.banner.bear .dot { background: var(--negative); }
.banner.neutral { border-left: 3px solid var(--warning); }
.banner.neutral .dot { background: var(--warning); }
.banner.unknown { border-left: 3px solid var(--subtle); }
.banner.unknown .dot { background: var(--subtle); }
.banner b { font-weight: 600; }
.banner .sep { color: var(--border); margin: 0 4px; }

/* 候選卡片：完全使用 Streamlit 原生 container(border=True)，僅做最小化整體調整 */

/* 卡片內的 metric 拿掉邊框/底色，避免「邊框中的邊框」雙層噪音 */
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    box-shadow: none !important;
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


# =====================================================
# Header
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
# Load base config & cache market state
# =====================================================
@st.cache_data
def get_base_config():
    return load_config("config.yaml")


@st.cache_data(ttl=600)
def get_market_state_cached():
    cfg = get_base_config()
    return classify_market(cfg["data"]["period"], cfg["data"]["cache_dir"])


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
    ps_cols = st.columns(3)
    for i, key in enumerate(["conservative", "balanced", "aggressive"]):
        label = base_cfg["presets"][key]["label"]
        is_active = st.session_state.get("preset") == key
        if ps_cols[i].button(
            label,
            type="primary" if is_active else "secondary",
            use_container_width=True,
            key=f"preset_{key}",
        ):
            apply_preset(key)
            st.rerun()

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
        uploaded = st.file_uploader("上傳股票清單 (xlsx)", type=["xlsx"])
        use_default = st.checkbox(
            "使用專案內 stock_list.xlsx",
            value=not uploaded, disabled=bool(uploaded),
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
        st.caption("首次 5–15 分鐘；同日重跑 < 1 分鐘")

    st.markdown("")
    run_btn = st.button("開始掃描", type="primary", use_container_width=True)

    st.divider()

    with st.expander("部位管理", expanded=True):
        total_capital = st.number_input(
            "總資金（元）", min_value=100_000,
            value=int(base_cfg.get("position_sizing", {}).get("total_capital", 1_000_000)),
            step=100_000, key="total_capital",
        )
        risk_pct = st.slider(
            "單筆風險 %", 0.5, 5.0,
            st.session_state.get("risk_pct", 1.0), 0.25, key="risk_pct",
        ) / 100
        max_pos_pct = st.slider(
            "單檔最大佔比 %", 5, 50,
            st.session_state.get("max_pos_pct", 20), 5, key="max_pos_pct",
        ) / 100

    with st.expander("品質過濾", expanded=False):
        min_price = st.number_input(
            "最低股價", min_value=0.0,
            value=st.session_state.get("min_price", 10.0), step=1.0, key="min_price",
        )
        min_avg_volume = st.number_input(
            "20 日均量下限（股）", min_value=0,
            value=st.session_state.get("min_avg_volume", 500_000), step=100_000,
            key="min_avg_volume",
        )
        require_ma60 = st.checkbox(
            "必須站上 MA60",
            value=st.session_state.get("require_ma60", True), key="require_ma60",
        )
        min_risk_pct = st.slider(
            "最小停損距離 %", 0.0, 10.0,
            st.session_state.get("min_risk_pct", 0.02) * 100, 0.5,
            key="min_risk_pct_slider",
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

        thr_enter = st.number_input(
            "進場 ≥", 0, 20,
            st.session_state.get("thr_enter", 6), key="thr_enter",
        )
        thr_watch = st.number_input(
            "觀察 ≥", 0, 20,
            st.session_state.get("thr_watch", 5), key="thr_watch",
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


def render_market_banner(market_state, last_scan_at=None):
    if not market_state:
        return
    regime = market_state["regime"]
    cls = {"bull": "bull", "bear": "bear", "neutral": "neutral"}.get(regime, "unknown")
    label = market_state["label"]
    for sym in ["🟢", "🔴", "🟡", "⚪"]:
        label = label.replace(sym, "")
    label = label.strip()
    last = ""
    if last_scan_at:
        last = f"<span class='sep'>·</span>上次掃描 {last_scan_at}"
    st.markdown(
        f"""
<div class='banner {cls}'>
  <span class='dot'></span>
  <span><b>大盤</b><span class='sep'>·</span>{label}<span class='sep'>·</span>{market_state['detail']}{last}</span>
</div>
""",
        unsafe_allow_html=True,
    )


def _action_class(action):
    s = str(action)
    if "進場" in s:
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
# Execute scan
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
            st.info(f"將掃描 {len(items)} 檔")
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


# =====================================================
# Market banner (一開啟就抓)
# =====================================================
last_scan_at = st.session_state.get("last_scan_at")
market_state = None
if "result" in st.session_state:
    market_state = st.session_state["result"].get("market_state")
if market_state is None:
    try:
        market_state = get_market_state_cached()
    except Exception:
        market_state = None
render_market_banner(market_state, last_scan_at)


# =====================================================
# Tabs
# =====================================================
tab1, tab2, tab3, tab4 = st.tabs(["買入掃描", "持股管理", "回測", "歷史"])


# =====================================================
# Tab 1: 買入掃描
# =====================================================
def render_top_candidates(df, ohlc_map, n=10):
    if "訊號判斷" not in df.columns:
        return

    entry_mask = df["訊號判斷"] == "進場"
    actionable_mask = df.get("操作建議", pd.Series(dtype=str)).astype(str).str.contains("進場", na=False)
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
            # ===== 標題列 =====
            hc1, hc2, hc3 = st.columns([6, 1, 1])
            hc1.markdown(
                f"**{row['股票']}**  {row['公司名稱']}  "
                f":green-badge[{action}]" if _action_class(action) == "go"
                else (
                    f"**{row['股票']}**  {row['公司名稱']}  :orange-badge[{action}]"
                    if _action_class(action) == "watch"
                    else f"**{row['股票']}**  {row['公司名稱']}  :gray-badge[{action}]"
                )
            )
            hc1.caption(f"評分 {score_d} · {entry_type}")
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

            # ===== 資料列：7 個 st.metric（副資訊改用 caption，避免 delta 箭頭誤導）=====
            mcols = st.columns(7)
            mcols[0].metric("進場", entry)
            mcols[1].metric("停損", stop)
            mcols[2].metric("目標 1", t1)
            mcols[3].metric("目標 2", t2)
            mcols[4].metric("風險", f"{risk_pct_val}%")

            try:
                lots_int = int(lots) if lots is not None and pd.notna(lots) else 0
            except Exception:
                lots_int = lots
            mcols[5].metric("建議張數", f"{lots_int} 張")
            mcols[5].caption(f"{cost_pct}% 資金")

            tr_value = f"{turnover}%" if turnover is not None and pd.notna(turnover) else "—"
            tr_label = _turnover_label(turnover) if turnover is not None and pd.notna(turnover) else ""
            mcols[6].metric("換手率", tr_value)
            if tr_label:
                mcols[6].caption(tr_label)

            if warning:
                st.caption(f":orange[{warning}]")


def render_results_table(df, key_prefix=""):
    fcol1, fcol2, fcol3, fcol4 = st.columns([2, 1.5, 1, 1])

    signal_options = ["進場", "觀察", "不操作"]
    available_signals = [
        s for s in signal_options
        if "訊號判斷" in df.columns and (df["訊號判斷"] == s).any()
    ]
    default_signals = [s for s in ["進場", "觀察"] if s in available_signals]

    sel_signals = fcol1.multiselect(
        "訊號", options=available_signals,
        default=default_signals or available_signals,
        key=f"{key_prefix}sig",
    )
    max_score = int(df["評分"].max()) if len(df) and "評分" in df.columns else 8
    min_score_filter = fcol2.slider(
        "最低評分", 0, max_score, 0, key=f"{key_prefix}minsc",
    )
    keyword = fcol3.text_input("搜尋", placeholder="股票或公司名",
                                key=f"{key_prefix}kw")
    show_full = fcol4.toggle("顯示全欄", value=False, key=f"{key_prefix}full")

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

    # 精簡欄位（預設）
    minimal_cols = [
        "股票", "公司名稱", "操作建議", "評分顯示",
        "進場參考價", "停損價", "目標價1(+1R半倉)",
        "風險%", "建議張數", "換手率%",
    ]
    full_priority = minimal_cols + [
        "進場類型", "進場條件", "進場成本", "佔資金%", "部位提示",
        "市場", "訊號判斷", "評分", "收盤價",
        "目標價2(+2R出清)", "RR比",
        "20日平均換手率%", "MA5", "MA20", "MA60", "K", "D", "OSC",
        "成交量", "20日均量",
        "突破+量增", "MA多頭", "換手率強勢", "KD強勢", "MACD多方",
        "大盤狀態", "狀態",
    ]
    target_cols = full_priority if show_full else minimal_cols
    show_cols = [c for c in target_cols if c in filtered.columns]
    if show_full:
        other_cols = [c for c in filtered.columns if c not in show_cols]
        show_cols += other_cols
    display = filtered[show_cols]

    col_cfg = {}
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
        cols[0].metric("進場候選", int(s.get("進場檔數", 0)))
        cols[1].metric("觀察", int(s.get("觀察檔數", 0)))
        cols[2].metric("掃描", int(s.get("掃描股票數", 0)))
        cols[3].metric("耗時 (秒)", s.get("執行秒數", "—"))

        render_top_candidates(df, ohlc_map, n=10)

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
    st.markdown("### 我的持股")
    st.caption("從買入掃描加入候選，或直接編輯。儲存在瀏覽器 session — 刷新會清空，記得「匯出」備份。")

    if "holdings_df" not in st.session_state:
        st.session_state["holdings_df"] = pd.DataFrame([
            {"股票代號": "2330", "公司名稱": "台積電", "進場價": 0.0,
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
            "股票代號": st.column_config.TextColumn("股票代號", required=True, width="small"),
            "公司名稱": st.column_config.TextColumn("公司名稱", width="medium"),
            "進場價": st.column_config.NumberColumn("進場價", min_value=0.0, step=0.5, format="%.2f", width="small"),
            "進場日": st.column_config.DateColumn("進場日", format="YYYY-MM-DD", width="small"),
            "持有張數": st.column_config.NumberColumn("持有張數", min_value=0, step=1, format="%d", width="small"),
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
            finally:
                logging.getLogger().removeHandler(handler)
            bar.progress(1.0, text="完成")

    if "holdings_result" in st.session_state:
        st.markdown("")
        h_df = st.session_state["holdings_result"]["df"]
        if "操作建議" in h_df.columns:
            h_df = h_df.copy()
            for sym in ["⛔", "🟢", "🔴", "🟡", "⌛", "✅", "❓", "⚠️"]:
                h_df["操作建議"] = h_df["操作建議"].astype(str).str.replace(sym, "")
            h_df["操作建議"] = h_df["操作建議"].str.strip()

        urgent_keywords = ["停損", "技術轉弱", "+2R", "+1R", "時間停損", "移動停利"]
        urgent = h_df[h_df["操作建議"].apply(
            lambda a: any(k in str(a) for k in urgent_keywords)
        )] if "操作建議" in h_df.columns else h_df.iloc[0:0]
        hold = h_df.drop(urgent.index) if len(urgent) else h_df

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
    bt_lookback = bt_c1.number_input("回測天數", 30, 500, 120, 30)
    bt_hold = bt_c2.number_input("持有天數", 3, 60, 10, 1)
    bt_min_score = bt_c3.number_input("最低評分", 0, 20, 5, 1)
    bt_c4.markdown("")
    run_bt_btn = bt_c4.button("跑回測", type="primary", use_container_width=True)

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
            st.error("請先在側欄設定股票來源")
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
        render_edge_meter(s["期望值R"])
        st.markdown("")

        # KPI
        c = st.columns(4)
        c[0].metric("總交易數", fmt_int(s["總交易數"]))
        c[1].metric("勝率 %", f"{s['勝率%']}%",
                     delta=f"{s['勝率%']-50:.1f}%" if s["勝率%"] else None)
        c[2].metric("平均 R", s["平均R"])
        c[3].metric("最大回撤 R", s["最大回撤R"])

        c2 = st.columns(3)
        c2[0].metric("平均報酬 %", f"{s['平均報酬%']}%")
        c2[1].metric("最大單筆 %", f"{s['最大單筆%']}%")
        c2[2].metric("期望值 R", s["期望值R"])

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
