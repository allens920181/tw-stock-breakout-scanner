"""
全站視覺：色彩 token、字體、元件樣式（規則見 docs/DESIGN.md）。

顏色分三組、互不混用：
  方向色 --up / --down（紅漲綠跌，可切換）· 狀態色 --caution / --critical / --info · 品牌色 --primary
--up / --down 由 color_mode 決定，在 inject_css() 時寫入；Plotly 圖表從 twscanner.ui.format.colors() 取同一組值。
"""
import streamlit as st

from twscanner.ui.format import colors

COLORS = {
    "bg": "#FFFFFF", "surface": "#F5F5F6", "border": "#ECECEE", "grid": "#F4F4F5",
    "text": "#18181B", "muted": "#71717A", "subtle": "#A1A1AA", "primary": "#18181B",
}
CHART_CONFIG = {"displayModeBar": False}

# 視覺原則（docs/DESIGN.md 第 2、4 節）：
# - 用「淺灰填色 + 留白」分區，不用框線；不用卡片左側色條；按鈕沒有深色細框
# - 品牌色是墨黑（主按鈕、目前頁、重點圖表）；紅綠只表示漲跌；狀態用淡底色 + 文字
CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
    --bg: #FFFFFF; --surface: #F5F5F6; --surface-2: #FAFAFA; --line: #ECECEE;
    --text: #18181B; --muted: #71717A; --subtle: #A1A1AA;
    --primary: #18181B; --primary-hover: #3F3F46;
    --flat: #71717A; --flat-bg: #F4F4F5; --flat-text: #52525B;
    --caution: #B45309; --caution-bg: #FDF6E3; --caution-text: #8A4B0B;
    --critical: #9A3412; --critical-bg: #FDF0EA;
    --info: #2563EB; --info-bg: #F1F5FE; --info-text: #1E4FC2;
    --radius: 12px; --radius-sm: 8px;
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
#MainMenu, footer { visibility: hidden; height: 0; }
/* 不要隱藏 stToolbar：頂部導覽與手機選單都在它裡面。Deploy 由 config 的 toolbarMode=minimal 處理 */
/* 頂部導覽在窄螢幕會退成側邊選單；桌機保持可見。手機上改由底部分頁列導覽（見下方手機區塊），這顆按鈕在手機隱藏 */
[data-testid="stExpandSidebarButton"] { visibility: visible !important; }
[data-testid="stExpandSidebarButton"] span[data-testid="stIconMaterial"] { font-size: 0 !important; }
[data-testid="stExpandSidebarButton"] span[data-testid="stIconMaterial"]::after { content: "menu"; font-size: 24px;
    font-family: 'Material Symbols Rounded'; color: var(--text); }
[data-testid="stSidebar"] { background: var(--bg); }
[data-testid="stSidebarNavLink"] { border-radius: var(--radius-sm) !important; }
[data-testid="stSidebarNavLink"][aria-current="page"] { background: var(--surface) !important; }
.block-container { padding-top: 4.6rem; padding-bottom: 3rem; max-width: 1200px; }
/* ===== 頂部導覽 ===== */
/* 導覽與內容對齊同一條左緣（內容最寬 1200px、左右留 2rem） */
.block-container { padding-left: 2rem; padding-right: 2rem; }
[data-testid="stToolbar"] { padding-left: max(0.75rem, calc((100vw - 1200px) / 2 + 2rem - 14px)) !important;
    padding-right: max(0.75rem, calc((100vw - 1200px) / 2 + 2rem)) !important; }
[data-testid="stHeaderLogo"], [data-testid="stLogo"] { margin-right: 20px; height: 28px !important; }
[data-testid="stHeader"] { background: rgba(255,255,255,0.92); backdrop-filter: saturate(180%) blur(8px);
    border-bottom: 1px solid var(--line); }
[data-testid="stTopNavLink"] { border-radius: var(--radius-sm) !important; padding: 6px 12px !important; }
[data-testid="stTopNavLink"] p { font-size: 0.9rem !important; color: var(--muted) !important; font-weight: 500 !important; }
[data-testid="stTopNavLink"]:hover { background: var(--surface) !important; }
[data-testid="stTopNavLink"][aria-current="page"] { background: var(--surface) !important; }
[data-testid="stTopNavLink"][aria-current="page"] p { color: var(--text) !important; font-weight: 600 !important; }
/* 字級：12 / 14 / 16 / 20 / 26 */
h1 { font-weight: 700 !important; font-size: 1.25rem !important; }
h2 { font-weight: 700 !important; font-size: 1.125rem !important; margin-top: 1.75rem !important; }
h3 { font-weight: 600 !important; font-size: 1.02rem !important; margin-top: 1.75rem !important; letter-spacing: -0.005em; }
h4 { font-weight: 600 !important; font-size: 0.875rem !important; color: var(--muted) !important; }
/* ===== 頁首：頁名 + 市場狀態 ===== */
.page-head { margin: 0 0 10px 0; }
.page-title { font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; line-height: 1.2; }
.page-meta { color: var(--muted); font-size: 0.8rem; margin-top: 4px; font-variant-numeric: tabular-nums; }
/* 市場狀態列：靠左、一條，三燈 + 該怎麼做（取代右上角的狀態與每頁重複的建議句） */
.mkt-strip { display: flex; align-items: center; gap: 6px 18px; flex-wrap: wrap; font-size: 0.86rem;
    margin: 0 0 22px 0; padding-bottom: 16px; border-bottom: 1px solid var(--line); }
.mkt-adv { color: var(--muted); }
.mkt-adv.bear { color: var(--caution-text); }
.mkt-item { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; color: var(--text); font-weight: 600; }
.mkt-item .k { color: var(--muted); font-weight: 500; }
.dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex: 0 0 auto; background: var(--subtle); }
.dot.bull { background: var(--up); } .dot.bear { background: var(--down); } .dot.neutral { background: var(--flat); }
/* ===== 結論句：大字、不加框 ===== */
.conclusion { margin: 4px 0 18px 0; line-height: 1.55; }
.conclusion .tone { display: inline-block; font-size: 0.75rem; font-weight: 600; padding: 2px 8px; border-radius: 999px;
    margin-bottom: 8px; background: var(--flat-bg); color: var(--flat-text); }
.conclusion.go .tone { background: var(--up-bg); color: var(--up-text); }
.conclusion.stop .tone { background: var(--caution-bg); color: var(--caution-text); }
.conclusion.info .tone { background: var(--info-bg); color: var(--info-text); }
.conclusion .lead { font-size: 1.3rem; font-weight: 700; display: block; letter-spacing: -0.01em; line-height: 1.4; }
.conclusion .sub { color: var(--muted); font-size: 0.92rem; display: block; margin-top: 4px; max-width: 72ch; }
/* ===== 徽章 ===== */
.badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 999px;
    font-size: 0.76rem; font-weight: 600; line-height: 1.5; white-space: nowrap; }
.badge.grade-A { background: var(--up); color: #fff; }
.badge.grade-B { background: var(--up-bg); color: var(--up-text); }
.badge.grade-C { background: var(--flat-bg); color: var(--flat-text); }
.badge.grade-X { background: var(--flat-bg); color: var(--muted); }
.badge.act-urgent { background: var(--caution-bg); color: var(--caution-text); }
.badge.act-hold { background: var(--flat-bg); color: var(--flat-text); }
.badge.up { background: var(--up-bg); color: var(--up-text); }
.badge.down { background: var(--down-bg); color: var(--down-text); }
.badge.info { background: var(--info-bg); color: var(--info-text); }
/* ===== KPI：淺灰底、不加框 ===== */
[data-testid="stMetric"] { background: var(--surface); padding: 14px 16px; border-radius: var(--radius); }
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: 0.78rem !important; font-weight: 500 !important; }
[data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 600 !important; }
.kpi-grid { display: grid; grid-template-columns: repeat(var(--n, 4), minmax(0, 1fr)); gap: 10px; margin: 0 0 20px 0; }
.kpi { background: var(--surface); border-radius: var(--radius); padding: 14px 16px; min-width: 0; }
.kpi .label { color: var(--muted); font-size: 0.78rem; font-weight: 500; }
.kpi .value { font-size: 1.5rem; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.35; letter-spacing: -0.01em; }
.kpi .sub { color: var(--muted); font-size: 0.76rem; margin-top: 2px; }
/* ===== 交易計畫卡 ===== */
.plan { background: var(--surface); border-radius: var(--radius); padding: 16px 18px; margin-bottom: 10px; }
.plan .top { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
.plan .name { font-size: 1.02rem; font-weight: 700; }
.plan .code { color: var(--muted); font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; margin-right: 6px; }
.plan .grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; margin: 14px 0 8px 0;
    background: var(--bg); border-radius: var(--radius-sm); padding: 10px 12px; }
.plan .cell .l { color: var(--muted); font-size: 0.72rem; }
.plan .cell .v { font-weight: 600; font-variant-numeric: tabular-nums; font-size: 0.98rem; }
.plan .why { font-size: 0.84rem; line-height: 1.7; }
.plan .why .tag { display: inline-block; background: var(--bg); color: var(--flat-text); border-radius: 999px; padding: 0 8px;
    margin: 2px 4px 2px 0; font-size: 0.76rem; }
.plan .rule { color: var(--muted); font-size: 0.8rem; margin-top: 6px; line-height: 1.6; }
.ladder { position: relative; height: 26px; margin: 6px 0 2px 0; }
.ladder .track { position: absolute; top: 11px; left: 0; right: 0; height: 4px; border-radius: 2px; background: var(--line); }
.ladder .mk { position: absolute; top: 4px; width: 2px; height: 18px; border-radius: 1px; }
.ladder .lb { position: absolute; top: -2px; font-size: 0.68rem; color: var(--muted); transform: translateX(-50%); white-space: nowrap; }
/* ===== 清單列（持股動作、健檢項目）：只用細分隔線 ===== */
.rowline { display: flex; gap: 12px; align-items: flex-start; padding: 12px 0; border-bottom: 1px solid var(--line); }
.rowline:last-child { border-bottom: none; }
.rowline .main { flex: 1; min-width: 0; }
.rowline .t { font-weight: 600; }
.rowline .d { color: var(--muted); font-size: 0.84rem; line-height: 1.6; }
.rowline .v { font-variant-numeric: tabular-nums; font-weight: 600; white-space: nowrap; }
.health-v { width: 64px; flex: 0 0 64px; }
.goal { margin: 4px 0 12px 0; }
.goal-num { font-size: 1.35rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.goal-num .of { color: var(--muted); font-size: 0.95rem; font-weight: 500; }
.goal-status { color: var(--muted); font-size: 0.84rem; line-height: 1.6; }
.kpi .warn, .kpi .sub .warn { color: var(--caution); }
.goalbar { background: var(--flat-bg); border-radius: 999px; height: 8px; overflow: hidden; margin: 8px 0; }
.goalbar > div { height: 100%; border-radius: 999px; }
/* ===== 空狀態 / 資料時間 / 課程 / 提醒 ===== */
.empty { background: var(--surface); border-radius: var(--radius); padding: 18px 20px; color: var(--muted); line-height: 1.6; }
.empty b { color: var(--text); font-weight: 600; }
.asof { color: var(--subtle); font-size: 0.75rem; margin: -6px 0 14px 0; }
.lesson { background: var(--surface); border-radius: var(--radius); padding: 16px 20px; margin-bottom: 10px; line-height: 1.75; }
.lesson .ex { background: var(--bg); border-radius: var(--radius-sm); padding: 10px 14px; margin-top: 10px; font-size: 0.88rem; }
.callout { background: var(--caution-bg); color: var(--caution-text); padding: 10px 14px; border-radius: var(--radius-sm);
    margin: 6px 0 12px 0; font-size: 0.9rem; }
.callout.info { background: var(--info-bg); color: var(--info-text); }
.set-head { margin: 28px 0 10px 0; padding-top: 20px; border-top: 1px solid var(--line); }
.set-head .t { font-weight: 700; font-size: 1.02rem; }
.set-head .d { color: var(--muted); font-size: 0.84rem; margin-top: 2px; }
.page-title + .set-head { border-top: none; padding-top: 0; }
/* ===== Streamlit 元件：無框、淺灰填色 ===== */
button { white-space: nowrap !important; }
button[kind="primary"], [data-testid="stBaseButton-primary"] {
    background: var(--primary) !important; color: #fff !important; border: none !important;
    border-radius: var(--radius-sm) !important; font-weight: 600 !important; box-shadow: none !important; }
button[kind="primary"]:hover { background: var(--primary-hover) !important; }
button[kind="secondary"], [data-testid="stBaseButton-secondary"], [data-testid="stPopoverButton"],
[data-testid="stDownloadButton"] button {
    background: var(--surface) !important; color: var(--text) !important; border: none !important;
    border-radius: var(--radius-sm) !important; font-weight: 500 !important; box-shadow: none !important; }
button[kind="secondary"]:hover, [data-testid="stPopoverButton"]:hover, [data-testid="stDownloadButton"] button:hover {
    background: #EBEBED !important; color: var(--text) !important; }
button[kind="tertiary"] { color: var(--muted) !important; }
/* 分段選擇：灰色軌道 + 白色選中塊（iOS / Linear 的做法） */
[data-testid="stButtonGroup"] > div { background: var(--surface); border-radius: 10px; padding: 3px; gap: 2px !important;
    display: inline-flex !important; flex-wrap: wrap; }
[data-testid="stBaseButton-segmented_control"], [data-testid="stBaseButton-segmented_controlActive"] {
    border: none !important; border-radius: var(--radius-sm) !important; background: transparent !important;
    color: var(--muted) !important; font-size: 0.86rem !important; padding: 4px 12px !important; min-height: 32px !important; }
[data-testid="stBaseButton-segmented_controlActive"] { background: var(--bg) !important; color: var(--text) !important;
    font-weight: 600 !important; box-shadow: 0 1px 2px rgba(0,0,0,0.06) !important; }
/* 次分頁：細底線、選中用墨黑 */
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--line); flex-wrap: nowrap;
    overflow-x: auto; scrollbar-width: none; -webkit-overflow-scrolling: touch; }
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { display: none; }
.stTabs [data-baseweb="tab"] { flex: 0 0 auto; font-size: 0.9rem !important; font-weight: 500 !important;
    padding: 8px 4px !important; margin-right: 14px; color: var(--muted) !important; background: transparent !important; }
.stTabs [aria-selected="true"] { color: var(--text) !important; font-weight: 600 !important; }
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--text) !important; height: 2px !important; }
.stTabs [data-baseweb="tab-border"] { display: none; }
/* 收合區塊：淺灰底、無框 */
[data-testid="stExpander"] details { border: none !important; background: var(--surface); border-radius: var(--radius) !important; }
[data-testid="stExpander"] summary { padding: 12px 16px !important; }
[data-testid="stExpander"] summary:hover { color: var(--text) !important; }
[data-testid="stExpander"] details summary p { font-weight: 600; font-size: 0.92rem; }
[data-testid="stExpanderDetails"] { padding: 0 16px 14px 16px !important; }
/* 表格、彈出選單 */
[data-testid="stDataFrame"] { border: none !important; }
[data-testid="stPopoverBody"] { border: none !important; border-radius: var(--radius) !important;
    box-shadow: 0 8px 28px rgba(24,24,27,0.12), 0 1px 3px rgba(24,24,27,0.06) !important; }
[data-testid="stFileUploaderDropzone"] { border: none !important; background: var(--surface) !important; }
[data-testid="stStatusWidget"], [data-testid="stStatus"] details { border: none !important; }
[data-testid="stProgress"] > div > div > div { background-color: var(--primary) !important; }
hr { border-color: var(--line) !important; }
/* Streamlit 提示框：淡底色、無左側色條；紅綠只留給漲跌方向 */
[data-testid="stAlertContainer"] { border-radius: var(--radius-sm) !important; border: none !important; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) { background: var(--critical-bg) !important; }
[data-testid="stAlertContentError"], [data-testid="stAlertContentError"] * { color: var(--critical) !important; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) { background: var(--caution-bg) !important; }
[data-testid="stAlertContentWarning"], [data-testid="stAlertContentWarning"] * { color: var(--caution-text) !important; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]),
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) { background: var(--info-bg) !important; }
[data-testid="stAlertContentSuccess"], [data-testid="stAlertContentSuccess"] *,
[data-testid="stAlertContentInfo"], [data-testid="stAlertContentInfo"] * { color: var(--info-text) !important; }
/* ===== 雲端同步狀態 ===== */
.sync-state { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }
.sync-state .dot { width: 6px; height: 6px; }
.dot.ok { background: var(--info); } .dot.error, .dot.conflict { background: var(--caution); } .dot.local { background: var(--subtle); }
.sync-state.error, .sync-state.conflict { color: var(--caution-text); }
/* ===== 報價式頁首（個股健檢）===== */
.quote { margin: 0 0 14px 0; }
.quote .q-name { font-size: 1.05rem; font-weight: 600; }
.quote .q-code { color: var(--muted); font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; margin-left: 8px; font-weight: 500; }
.quote .q-px { font-size: 2rem; font-weight: 700; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; line-height: 1.25; }
.quote .q-chg { font-size: 1rem; font-weight: 600; margin-left: 10px; }
.quote .q-meta { color: var(--subtle); font-size: 0.75rem; }
/* 資金流向摘要卡：無框淺灰底 */
[class*="st-key-flowcard_"] { background: var(--surface); border-radius: var(--radius); padding: 14px 16px; height: 100%; }
[class*="st-key-flowcard_"] [data-testid="stExpander"] details { background: transparent !important; }
[class*="st-key-flowcard_"] [data-testid="stExpander"] summary { padding: 6px 0 !important; }
.fc-title { color: var(--muted); font-size: 0.8rem; font-weight: 600; margin-bottom: 4px; }
.fc-lead { font-size: 0.95rem; line-height: 1.6; }
/* 閱讀型內容（學習中心）：限制行長，中文每行約 35–40 字 */
[class*="st-key-reading"] { max-width: 760px; }
/* 區塊標題＋同一行摘要（找標的的結果數量） */
.res-head { display: flex; align-items: baseline; gap: 6px 16px; flex-wrap: wrap; margin: 8px 0 4px 0; }
.res-head h3 { margin: 0 !important; padding: 0 !important; }
.res-head span { color: var(--muted); font-size: 0.88rem; }
.res-head b { color: var(--text); font-variant-numeric: tabular-nums; }
/* ===== 手機底部分頁列（桌機隱藏）===== */
.st-key-tabbar, [data-testid="stLayoutWrapper"]:has(> .st-key-tabbar) { display: none !important; }   /* 連外層一起藏，桌機不留空隙 */
/* ===== 手機 ===== */
@media (max-width: 640px) {
    /* 導覽改由底部分頁列負責：拇指碰得到（Hoober），也不用藏在 ☰（NN/g） */
    [data-testid="stExpandSidebarButton"] { display: none !important; }
    .block-container { padding-left: 1rem; padding-right: 1rem; padding-top: 3.9rem;
        padding-bottom: calc(84px + env(safe-area-inset-bottom, 0px)) !important; }
    [data-testid="stLayoutWrapper"]:has(> .st-key-tabbar) { display: contents !important; }   /* 不佔版面、不留間距 */
    .st-key-tabbar { display: block !important; position: fixed; left: 0; right: 0; bottom: 0; z-index: 999;
        background: rgba(255,255,255,0.97); backdrop-filter: saturate(180%) blur(8px); border-top: 1px solid var(--line);
        padding: 4px 6px calc(4px + env(safe-area-inset-bottom, 0px)); }
    .st-key-tabbar [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0 !important; }
    .st-key-tabbar [data-testid="stColumn"] { flex: 1 1 0 !important; min-width: 0 !important; width: auto !important; }
    .st-key-tabbar [data-testid="stPageLink"] a, .st-key-tabbar [data-testid="stPopoverButton"] {
        display: flex !important; flex-direction: column !important; align-items: center !important; gap: 2px !important;
        padding: 6px 0 !important; background: transparent !important; border: none !important; width: 100% !important;
        min-height: 52px; justify-content: center; }
    .st-key-tabbar [data-testid="stPageLink"] a p, .st-key-tabbar [data-testid="stPopoverButton"] p {
        font-size: 0.7rem !important; color: var(--muted) !important; margin: 0 !important; line-height: 1.2 !important; }
    .st-key-tabbar [data-testid="stPopoverButton"] [data-testid="stMarkdownContainer"] { margin: 0 !important; }
    .st-key-tabbar [data-testid="stPageLink"] a span[data-testid="stIconMaterial"],
    .st-key-tabbar [data-testid="stPopoverButton"] span[data-testid="stIconMaterial"] { font-size: 22px !important; color: var(--muted) !important; }
    .st-key-tabbar [data-testid="stElementContainer"], .st-key-tabbar [data-testid="stLayoutWrapper"],
    .st-key-tabbar [data-testid="stPopover"], .st-key-tabbar [data-testid="stPageLink"] { width: 100% !important; }
    .st-key-tabbar [data-testid="stPopoverButton"] > div { justify-content: center !important; width: 100%; }
    .st-key-tabbar [data-testid="stPopoverButton"] span[data-has-shortcut] { display: flex !important; flex-direction: column !important;
        align-items: center !important; gap: 2px !important; }
    .st-key-tabbar [data-testid="stPopoverButton"] div[aria-hidden="true"] { display: none !important; }
    [class*="st-key-tab_"][class*="_on"] p, [class*="st-key-tab_"][class*="_on"] span[data-testid="stIconMaterial"] {
        color: var(--text) !important; font-weight: 600 !important; }
    .st-key-scanbar [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: 8px !important; }
    .st-key-scanbar [data-testid="stColumn"] { flex: 1 1 calc(50% - 4px) !important; min-width: calc(50% - 4px) !important;
        width: calc(50% - 4px) !important; }
    .st-key-scanbar button p { overflow: hidden; text-overflow: ellipsis; }
    .page-title { font-size: 1.25rem; }
    .mkt-strip { gap: 4px 12px; font-size: 0.8rem; margin-bottom: 14px; padding-bottom: 12px; }
    .conclusion .lead { font-size: 1.12rem; }
    .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .kpi { padding: 10px 12px; }
    .kpi .label, .kpi .sub { font-size: 0.72rem; }
    .kpi .value { font-size: 1.12rem; line-height: 1.3; }
    [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
    .plan { padding: 14px; }
    .plan .grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .rowline { gap: 8px; }
    .health-v { width: 52px; flex-basis: 52px; }
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
