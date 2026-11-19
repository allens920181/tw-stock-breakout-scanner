"""
全站視覺：CSS（色票 / 字型 / 頁首 / 卡片 / 表格）與圖表共用常數。

色票以 CSS 變數定義在 :root，元件與分頁只引用變數名稱；
Plotly 圖表無法讀 CSS 變數，故在 COLORS 保留同一份 hex。
"""
import streamlit as st

COLORS = {
    "bg": "#F8FAFC", "surface": "#FFFFFF", "border": "#E2E8F0", "grid": "#F1F5F9",
    "text": "#0F172A", "muted": "#64748B", "subtle": "#94A3B8",
    "primary": "#4F46E5", "positive": "#059669", "warning": "#D97706", "negative": "#DC2626",
}
CHART_CONFIG = {"displayModeBar": False}

CSS = """
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

/* 綜合判斷建議列 */
.hdr-advice {
  display: flex; align-items: center; gap: 7px;
  margin: 8px 0 4px 0; padding: 8px 13px; border-radius: 8px;
  font-size: 13px; font-weight: 500; line-height: 1.4;
  border: 1px solid var(--border, #E2E8F0); background: var(--surface, #F8FAFC);
}
.hdr-advice .dot { width: 8px; height: 8px; border-radius: 50%; flex: 0 0 auto; }
.hdr-advice b { font-weight: 700; margin-right: 2px; }
.hdr-advice.bull    { border-left: 4px solid var(--positive); background: rgba(5,150,105,.06); }
.hdr-advice.bull .dot { background: var(--positive); }
.hdr-advice.bear    { border-left: 4px solid var(--negative); background: rgba(220,38,38,.06); }
.hdr-advice.bear .dot { background: var(--negative); }
.hdr-advice.neutral { border-left: 4px solid var(--warning); background: rgba(217,119,6,.06); }
.hdr-advice.neutral .dot { background: var(--warning); }
.hdr-advice.unknown { border-left: 4px solid var(--subtle); }
.hdr-advice.unknown .dot { background: var(--subtle); }

/* 今日三步引導列 */
.today-steps {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
  background: var(--surface, #F8FAFC); border: 1px solid var(--border, #E2E8F0);
  border-radius: 8px; padding: 7px 12px; margin: 2px 0 12px 0; font-size: 12.5px;
}
.today-steps .step { color: var(--muted, #475569); }
.today-steps .step b { color: var(--accent, #2563EB); margin-right: 3px; }
.today-steps .arrow { color: var(--border, #CBD5E1); margin: 0 2px; }

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
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)
