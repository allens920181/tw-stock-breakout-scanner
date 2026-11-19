"""共用小元件：格式化、Excel 模板下載、進度條 + 執行記錄、首次引導。"""
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
