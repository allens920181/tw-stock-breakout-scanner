"""
全站視覺（設計基準 v1 第 5–6 節）：色彩 token、字體、元件樣式。

顏色分三組、互不混用：
  方向色 --up / --down（紅漲綠跌，可切換）· 狀態色 --caution / --critical / --info · 品牌色 --primary
--up / --down 由 color_mode 決定，在 inject_css() 時寫入；Plotly 圖表從 twscanner.ui.format.colors() 取同一組值。
"""
import streamlit as st

from twscanner.ui.format import colors

COLORS = {
    "bg": "#F8FAFC", "surface": "#FFFFFF", "border": "#E2E8F0", "grid": "#F1F5F9",
    "text": "#0F172A", "muted": "#64748B", "subtle": "#94A3B8", "primary": "#4F46E5",
}
CHART_CONFIG = {"displayModeBar": False}

CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
    --bg: #F8FAFC; --surface: #FFFFFF; --border: #E2E8F0; --border-2: #F1F5F9;
    --text: #0F172A; --muted: #64748B; --subtle: #94A3B8;
    --primary: #4F46E5; --primary-2: #EEF2FF;
    --flat: #64748B; --flat-bg: #F1F5F9; --flat-text: #475569;
    --caution: #B45309; --caution-bg: #FEF3C7; --caution-text: #92400E;
    --critical: #9A3412; --info: #2563EB; --info-bg: #EFF6FF; --info-text: #1D4ED8;
    --font: 'Inter', 'Noto Sans TC', -apple-system, BlinkMacSystemFont, 'PingFang TC', 'Microsoft JhengHei', sans-serif;
}

html, body { font-family: var(--font); color: var(--text); }
.stMarkdown, .stText, p,
span:not([class*="material-symbols"]):not([class*="icon"]),
div:not([class*="material-symbols"]):not([class*="icon"]),
label, h1, h2, h3, h4, h5, h6, button { font-family: var(--font); }
code, pre { font-family: 'JetBrains Mono', monospace; }
[data-testid="stMetricValue"], .num { font-variant-numeric: tabular-nums; }
[class*="material-symbols"], .material-symbols-outlined, .material-symbols-rounded,
[data-testid*="Icon"], [data-testid*="icon"] {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined' !important;
    font-feature-settings: 'liga';
}

#MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; height: 0; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1320px; }

/* 字級 5 級：12 / 14 / 16 / 20 / 28 */
h1 { font-weight: 700 !important; font-size: 1.25rem !important; }
h2 { font-weight: 700 !important; font-size: 1.125rem !important; margin-top: 1.5rem !important; }
h3 { font-weight: 600 !important; font-size: 1rem !important; margin-top: 1.25rem !important; }
h4 { font-weight: 600 !important; font-size: 0.875rem !important; color: var(--muted) !important; }

/* ===== 頁首 ===== */
.app-header {
    display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;
    padding-bottom: 12px; border-bottom: 1px solid var(--border-2); margin-bottom: 12px;
}
.app-title { font-size: 1.25rem; font-weight: 700; letter-spacing: -0.01em; }
.app-sub { color: var(--muted); font-size: 0.8rem; }
.hdr-right { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
.app-date { color: var(--muted); font-size: 0.75rem; font-variant-numeric: tabular-nums; }
.hdr-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.hdr-status {
    display: flex; align-items: center; gap: 6px; font-size: 0.82rem;
    padding: 4px 10px; border-radius: 6px; background: var(--surface); border: 1px solid var(--border);
}
.hdr-status .dot, .hdr-advice .dot { width: 8px; height: 8px; border-radius: 50%; flex: 0 0 auto; }
.hdr-status.bull { border-left: 3px solid var(--up); }   .hdr-status.bull .dot { background: var(--up); }
.hdr-status.bear { border-left: 3px solid var(--down); } .hdr-status.bear .dot { background: var(--down); }
.hdr-status.neutral { border-left: 3px solid var(--flat); } .hdr-status.neutral .dot { background: var(--flat); }
.hdr-status.unknown { border-left: 3px solid var(--subtle); } .hdr-status.unknown .dot { background: var(--subtle); }
.hdr-advice {
    display: flex; align-items: center; gap: 8px; margin: 4px 0 6px 0; padding: 9px 14px;
    border-radius: 8px; font-size: 0.875rem; line-height: 1.45; border: 1px solid var(--border);
    background: var(--surface);
}
.hdr-advice b { font-weight: 700; margin-right: 4px; white-space: nowrap; }
.hdr-advice.bull { border-left: 4px solid var(--up); background: var(--up-bg); }       .hdr-advice.bull .dot { background: var(--up); }
.hdr-advice.bear { border-left: 4px solid var(--down); background: var(--down-bg); }   .hdr-advice.bear .dot { background: var(--down); }
.hdr-advice.neutral { border-left: 4px solid var(--flat); background: var(--flat-bg); } .hdr-advice.neutral .dot { background: var(--flat); }
.hdr-advice.unknown { border-left: 4px solid var(--subtle); } .hdr-advice.unknown .dot { background: var(--subtle); }

/* ===== 結論句（每頁首屏第一行）===== */
.conclusion {
    padding: 14px 18px; border-radius: 8px; margin: 4px 0 14px 0; border: 1px solid var(--border);
    background: var(--surface); font-size: 1rem; line-height: 1.55;
}
.conclusion .lead { font-size: 1.125rem; font-weight: 700; display: block; margin-bottom: 2px; }
.conclusion .sub { color: var(--muted); font-size: 0.875rem; }
.conclusion.go { border-left: 4px solid var(--up); }
.conclusion.stop { border-left: 4px solid var(--caution); background: var(--caution-bg); }
.conclusion.wait { border-left: 4px solid var(--flat); }
.conclusion.info { border-left: 4px solid var(--info); }

/* ===== 徽章 ===== */
.badge {
    display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 6px;
    font-size: 0.78rem; font-weight: 600; line-height: 1.5; white-space: nowrap;
}
.badge.grade-A { background: var(--up); color: #fff; }
.badge.grade-B { background: var(--up-bg); color: var(--up-text); }
.badge.grade-C { background: var(--surface); color: var(--flat-text); border: 1px solid var(--border); }
.badge.grade-X { background: var(--flat-bg); color: var(--muted); }
.badge.act-urgent { background: var(--caution-bg); color: var(--caution-text); }
.badge.act-hold { background: var(--flat-bg); color: var(--flat-text); }
.badge.up { background: var(--up-bg); color: var(--up-text); }
.badge.down { background: var(--down-bg); color: var(--down-text); }
.badge.info { background: var(--info-bg); color: var(--info-text); }

/* ===== KPI ===== */
[data-testid="stMetric"] {
    background: var(--surface); padding: 12px 16px; border-radius: 8px; border: 1px solid var(--border);
}
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: 0.78rem !important; font-weight: 500 !important; }
[data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 600 !important; }
[data-testid="stMetricValue"] > div { overflow: visible !important; white-space: normal !important; }
[data-testid="stMetricDelta"] { font-size: 0.78rem !important; }
.kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px 16px; height: 100%; }
.kpi .label { color: var(--muted); font-size: 0.78rem; font-weight: 500; }
.kpi .value { font-size: 1.5rem; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.3; }
.kpi .sub { color: var(--muted); font-size: 0.78rem; margin-top: 2px; }

/* ===== 交易計畫卡 ===== */
.plan { border: 1px solid var(--border); border-radius: 8px; background: var(--surface); padding: 14px 16px; margin-bottom: 12px; }
.plan .top { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
.plan .name { font-size: 1rem; font-weight: 700; }
.plan .code { color: var(--muted); font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; margin-right: 6px; }
.plan .grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; margin: 12px 0 8px 0; }
.plan .cell .l { color: var(--muted); font-size: 0.72rem; }
.plan .cell .v { font-weight: 600; font-variant-numeric: tabular-nums; font-size: 0.98rem; }
.plan .why { font-size: 0.84rem; color: var(--text); line-height: 1.6; }
.plan .why .tag { display: inline-block; background: var(--flat-bg); color: var(--flat-text); border-radius: 4px; padding: 0 6px; margin: 2px 4px 2px 0; font-size: 0.78rem; }
.plan .rule { color: var(--muted); font-size: 0.8rem; margin-top: 6px; }
.ladder { position: relative; height: 26px; margin: 6px 0 2px 0; }
.ladder .track { position: absolute; top: 11px; left: 0; right: 0; height: 4px; border-radius: 2px;
    background: linear-gradient(90deg, var(--down-bg), var(--flat-bg) 40%, var(--up-bg)); }
.ladder .mk { position: absolute; top: 4px; width: 2px; height: 18px; }
.ladder .lb { position: absolute; top: -2px; font-size: 0.68rem; color: var(--muted); transform: translateX(-50%); white-space: nowrap; }

/* ===== 清單列（持股動作、健檢項目）===== */
.rowline { display: flex; gap: 12px; align-items: flex-start; padding: 10px 0; border-bottom: 1px solid var(--border-2); }
.rowline:last-child { border-bottom: none; }
.rowline .main { flex: 1; min-width: 0; }
.rowline .t { font-weight: 600; }
.rowline .d { color: var(--muted); font-size: 0.84rem; line-height: 1.55; }
.rowline .v { font-variant-numeric: tabular-nums; font-weight: 600; white-space: nowrap; }
.health-v { width: 64px; flex: 0 0 64px; }

/* ===== 進度條（月目標）===== */
.goalbar { background: var(--flat-bg); border-radius: 6px; height: 10px; overflow: hidden; margin: 6px 0; }
.goalbar > div { height: 100%; border-radius: 6px; }

/* ===== 空狀態 / 資料時間 / 課程 ===== */
.empty { border: 1px dashed var(--border); border-radius: 8px; padding: 18px; color: var(--muted); background: var(--surface); }
.empty b { color: var(--text); }
.asof { color: var(--muted); font-size: 0.75rem; margin: 4px 0 10px 0; }
.lesson { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 14px 18px; margin-bottom: 10px; line-height: 1.7; }
.lesson .ex { background: var(--info-bg); border-radius: 6px; padding: 8px 12px; margin-top: 8px; font-size: 0.88rem; }
.callout { border-left: 4px solid var(--caution); background: var(--caution-bg); color: var(--caution-text);
    padding: 10px 14px; border-radius: 6px; margin: 6px 0 12px 0; font-size: 0.9rem; }
.callout.info { border-left-color: var(--info); background: var(--info-bg); color: var(--info-text); }

/* ===== Streamlit 元件 ===== */
.stTabs [data-baseweb="tab-list"] { gap: 2px; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.stTabs [data-baseweb="tab"] { font-size: 0.92rem !important; font-weight: 500 !important; padding: 8px 12px !important; color: var(--muted) !important; }
.stTabs [aria-selected="true"] { color: var(--text) !important; font-weight: 700 !important; }
[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }
[data-testid="stSidebar"] .stMarkdown h3 { font-size: 0.8rem !important; color: var(--muted) !important; letter-spacing: 0.04em; margin-top: 0.8rem !important; }
[data-testid="stSidebar"] [data-testid="stExpander"] { border: 1px solid var(--border); border-radius: 6px; background: var(--bg); margin-bottom: 6px; }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] { padding: 8px 12px !important; min-height: 0 !important; }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small { display: none !important; }
[data-testid="stSidebar"] [data-testid="stSegmentedControl"] button { font-size: 0.82rem !important; padding: 4px 10px !important; }
button { white-space: nowrap !important; }
button[kind="primary"] { background: var(--primary) !important; border: 1px solid var(--primary) !important; border-radius: 6px !important; font-weight: 600 !important; }
button[kind="secondary"] { border-radius: 6px !important; border: 1px solid var(--border) !important; color: var(--text) !important; background: var(--surface) !important; }
button[kind="secondary"]:hover { border-color: var(--subtle) !important; background: var(--bg) !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--border) !important; border-radius: 6px; }
[data-testid="stProgress"] > div > div > div { background-color: var(--primary) !important; }
[data-testid="stExpander"] details summary p { font-weight: 500; }
.watch-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.watch-chip { background: var(--primary-2); color: var(--primary); padding: 4px 10px; border-radius: 12px; font-size: 0.78rem; font-family: 'JetBrains Mono', monospace; }

/* ===== 手機 ===== */
@media (max-width: 640px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; }
    .hdr-right { align-items: flex-start; }
    .plan .grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .conclusion .lead { font-size: 1rem; }
    [data-testid="stMetricValue"], .kpi .value { font-size: 1.2rem !important; }
}
</style>
"""


def _vars():
    c = colors()
    return (f"<style>:root{{--up:{c['up']};--up-bg:{c['up_bg']};--up-text:{c['up_text']};"
            f"--down:{c['down']};--down-bg:{c['down_bg']};--down-text:{c['down_text']};}}</style>")


def _html_block(css):
    """
    Markdown 規則：以 <link> 開頭的 HTML 區塊遇到第一個空行就結束，後面的 CSS 會被當成文字印出。
    所以 <link> 與 <style> 之間保留一個空行，<style> 內部則移除所有空行。
    """
    head, _, rest = css.partition("<style>")
    body = "\n".join(line for line in rest.splitlines() if line.strip())
    return head.strip() + "\n\n<style>\n" + body


def inject_css():
    st.markdown(_html_block(CSS) + "\n\n" + _vars(), unsafe_allow_html=True)
