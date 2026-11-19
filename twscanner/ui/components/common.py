"""共用小元件：格式化、Excel 模板下載、進度條 + 執行記錄、"""
import io
import logging

import pandas as pd
import streamlit as st


def fmt_int(n):
    """千分位"""
    try:
        return f"{int(n):,}"
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
