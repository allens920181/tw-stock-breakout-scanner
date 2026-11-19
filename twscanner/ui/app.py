"""
Streamlit App 外殼：頁面設定 → 樣式 → 狀態初始化 → 頁首 → 側欄 → 分頁。

新增分頁：在 twscanner/ui/pages/ 新建模組並提供 render()，再加進下方 PAGES。
需要側欄互動結果（資料來源 / 開始掃描）的分頁，render 接收 SidebarState。
"""
import streamlit as st

from twscanner import __version__
from twscanner.ui import state
from twscanner.ui.components.header import render_market_header
from twscanner.ui.pages import backtest, flows, guide, history, holdings, lookup, scan
from twscanner.ui.sidebar import render_sidebar
from twscanner.ui.theme import inject_css

# (分頁標題, 模組, 是否需要 SidebarState)；順序 = 畫面上的分頁順序
PAGES = [
    ("📈 買入掃描", scan, True),
    ("🔎 個股查詢", lookup, False),
    ("💰 資金流向", flows, False),
    ("💼 持股管理", holdings, False),
    ("🧪 回測", backtest, True),
    ("🕘 歷史", history, False),
    ("📖 操作教學", guide, False),
]


def main():
    st.set_page_config(
        page_title="台股強勢突破掃描器",
        page_icon="·",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={"About": f"**台股強勢突破掃描器** v{__version__}"},
    )
    inject_css()
    state.bootstrap()

    # 側欄先渲染（widget 值寫入 session_state，build_cfg 才讀得到），頁首在主區最上方
    sb = render_sidebar()
    render_market_header()

    tabs = st.tabs([title for title, _, _ in PAGES])
    for tab, (title, page, needs_sidebar) in zip(tabs, PAGES):
        with tab:
            _render_isolated(title, page, sb if needs_sidebar else None)


def _render_isolated(title, page, sb):
    """
    單一分頁出錯只影響自己，不讓後面的分頁整個消失。
    st.rerun() / st.stop() 的控制例外繼承 BaseException，不會被這裡攔截。
    """
    try:
        page.render(sb) if sb is not None else page.render()
    except Exception as e:
        st.error(f"「{title}」分頁發生錯誤，其他分頁不受影響。")
        st.exception(e)
