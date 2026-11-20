"""
Streamlit App 外殼：頁面設定 → 狀態與樣式 → 頂部導覽 → 頁首（頁名 + 市場狀態）→ 目前頁面。

版面參考成熟產品（券商 App、Stripe / Linear 類儀表板）：頂部一條導覽、沒有常駐側欄；
每天要用的控制項放在頁面裡（找標的頁頂端的掃描列），不常改的放「設定」頁。
只有目前這一頁會執行，換頁不會把七個分頁全部重算一次。

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

# (網址, 導覽名稱, 頁首標題, 模組, 是否需要掃描設定)；順序 = 每天的操作順序
PAGES = [
    ("today", "今日決策", "今日決策", today, True),
    ("scan", "找標的", "找標的", scan, False),          # 掃描列在頁面裡自己畫
    ("lookup", "個股健檢", "個股健檢", lookup, False),
    ("holdings", "持股與紀錄", "持股與紀錄", holdings, False),
    ("flows", "資金流向", "資金流向", flows, False),
    ("learn", "學習中心", "學習中心", learn, False),
    ("research", "策略驗證", "策略驗證", research, True),
    ("settings", "設定", "設定", settings_page, False),
]


def _page(url, title, heading, module, needs_scan):
    def run():
        sync.pull_changes()              # 別台裝置改過的先拉回來（畫 widget 之前；最多每 45 秒查一次版本）
        if url != "settings":            # 設定頁自己有標題，不需要市場狀態
            # 今日決策與找標的的結論句已經講了大盤怎麼做，頁首就不重複那句建議
            render_page_header(heading, advice=url not in ("today", "scan"))
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
    nav = st.navigation([_page(*p) for p in PAGES], position="top")
    nav.run()


def _render_isolated(title, page, sb):
    """頁面出錯時只顯示錯誤，不讓整個 App 白屏。st.rerun() / st.stop() 是 BaseException，不會被攔截。"""
    try:
        page.render(sb) if sb is not None else page.render()
    except Exception as e:
        st.error(f"「{title}」發生錯誤，其他頁面不受影響。")
        st.exception(e)
