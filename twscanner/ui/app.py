"""
Streamlit App 外殼：頁面設定 → 狀態與樣式 → 導覽 → 頁首（頁名 + 市場狀態列）→ 目前頁面。

導覽（參考券商 App 與 Stripe / Linear 類儀表板，研究依據見 docs/DESIGN.md）：
- 桌機：頂部導覽只放每天用的 5 頁，學習中心、策略驗證、設定收進「更多」下拉。
- 手機：底部固定分頁列（今日 / 找標的 / 個股 / 持股 / 更多），拇指碰得到；不用右上角的 ☰。
只有目前這一頁會執行，換頁不會把所有頁面重算一次。

新增頁面：在 twscanner/ui/pages/ 建模組並提供 render()，再加進下方 PAGES。
"""
from pathlib import Path

import streamlit as st

from twscanner import __version__
from twscanner.ui import state, sync
from twscanner.ui.components.header import render_page_header
from twscanner.ui.pages import flows, holdings, learn, lookup, research, scan, settings_page, today
from twscanner.ui.scan_controls import current_scan_state
from twscanner.ui.theme import inject_css

LOGO = Path(__file__).parent / "assets" / "logo.svg"

# (網址, 導覽名稱, 模組, 是否需要掃描設定, 群組, 手機分頁列名稱, 圖示)；順序 = 每天的操作順序
PAGES = [
    ("today", "今日決策", today, True, "main", "今日", ":material/today:"),
    ("scan", "找標的", scan, False, "main", "找標的", ":material/manage_search:"),   # 掃描列在頁面裡自己畫
    ("lookup", "個股健檢", lookup, False, "main", "個股", ":material/query_stats:"),
    ("holdings", "持股與紀錄", holdings, False, "main", "持股", ":material/account_balance_wallet:"),
    ("flows", "資金流向", flows, False, "main", None, ":material/swap_horiz:"),
    ("learn", "學習中心", learn, False, "more", None, ":material/school:"),
    ("research", "策略驗證", research, True, "more", None, ":material/fact_check:"),
    ("settings", "設定", settings_page, False, "more", None, ":material/settings:"),
]
_OBJS = {}


def _tab_bar(current):
    """手機底部分頁列（桌機用 CSS 隱藏）。放在頁面最前面畫，頁面中途 st.stop 也不會不見。"""
    bar = st.container(key="tabbar")
    cols = bar.columns(5, gap=None)
    tabs = [p for p in PAGES if p[5]]
    for col, (url, _, _, _, _, short, icon) in zip(cols, tabs):
        with col.container(key=f"tab_{url}_{'on' if url == current else 'off'}"):
            st.page_link(_OBJS[url], label=short, icon=icon)
    more_on = current not in {p[0] for p in tabs}
    with cols[4].container(key=f"tab_more_{'on' if more_on else 'off'}"):
        with st.popover("更多", icon=":material/more_horiz:"):
            for url, title, _, _, _, short, icon in PAGES:
                if not short:
                    st.page_link(_OBJS[url], label=title, icon=icon)


def _page(url, title, module, needs_scan, *_):
    def run():
        sync.pull_changes()              # 別台裝置改過的先拉回來（畫 widget 之前；最多每 45 秒查一次版本）
        _tab_bar(url)
        if url != "settings":            # 設定頁自己有標題，不需要市場狀態
            # 今日決策與找標的的結論句已經講了大盤怎麼做，頁首就不重複那句建議
            render_page_header(title, advice=url not in ("today", "scan"))
        sync.render_conflicts()
        new_conflict = False
        try:
            _render_isolated(title, module, current_scan_state() if needs_scan else None)
        finally:
            new_conflict = sync.push_changes()   # 有變的才上傳（st.rerun 之前也會執行）
        if new_conflict:
            st.rerun()                   # 衝突是在結尾才發現的：重畫一次，讓頁面上方出現選擇
    run.__name__ = f"page_{url}"
    return st.Page(run, title=title, url_path=url, default=(url == "today"))


def main():
    st.set_page_config(
        page_title="台股波段決策系統",
        page_icon="·",
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={"About": f"**台股波段決策系統** v{__version__}"},
    )
    state.persist_settings()  # 換頁時保留設定值（widget 不在本頁時 Streamlit 會清掉）
    state.bootstrap()         # 先載入偏好（漲跌顏色），樣式才拿得到正確的 --up / --down
    inject_css()
    st.logo(str(LOGO), size="large")
    _OBJS.clear()
    _OBJS.update({p[0]: _page(*p) for p in PAGES})
    nav = st.navigation({"": [_OBJS[p[0]] for p in PAGES if p[4] == "main"],
                         "更多": [_OBJS[p[0]] for p in PAGES if p[4] == "more"]}, position="top")
    nav.run()


def _render_isolated(title, page, sb):
    """頁面出錯時只顯示錯誤，不讓整個 App 白屏。st.rerun() / st.stop() 是 BaseException，不會被攔截。"""
    try:
        page.render(sb) if sb is not None else page.render()
    except Exception as e:
        st.error(f"「{title}」發生錯誤，其他頁面不受影響。")
        st.exception(e)
