"""
全站數字格式與漲跌顏色（設計基準 v1 第 5 節）。

- 方向色只有兩個 token：up（漲 / 買超 / 偏多）、down（跌 / 賣超 / 偏空），預設台股紅漲綠跌，
  使用者可切換為綠漲紅跌（color_mode = "us"）。任何地方要漲跌色都從這裡拿，不要寫死 hex。
- 數字一律帶單位與正負號；負號用「−」（U+2212）。
"""
import math
import re

import pandas as pd
import streamlit as st

PALETTE = {
    "tw": {"up": "#D7263D", "up_bg": "#FDECEE", "up_text": "#B4182F",
           "down": "#0B8457", "down_bg": "#E6F4EE", "down_text": "#08704A"},
    "us": {"up": "#0B8457", "up_bg": "#E6F4EE", "up_text": "#08704A",
           "down": "#D7263D", "down_bg": "#FDECEE", "down_text": "#B4182F"},
}
FLAT = "#64748B"
CAUTION, CAUTION_BG, CAUTION_TEXT = "#B45309", "#FEF3C7", "#92400E"
INFO = "#2563EB"
MINUS = "−"


def color_mode():
    try:
        return st.session_state.get("color_mode", "tw")
    except Exception:
        return "tw"


def colors(mode=None):
    c = dict(PALETTE.get(mode or color_mode(), PALETTE["tw"]))
    c.update(flat=FLAT, caution=CAUTION, caution_bg=CAUTION_BG, caution_text=CAUTION_TEXT, info=INFO)
    return c


def metric_delta_color():
    """st.metric 的 delta_color：Streamlit 的 normal = 綠漲紅跌。"""
    return "inverse" if color_mode() == "tw" else "normal"


def dir_color(v, mode=None):
    c = colors(mode)
    if v is None or (isinstance(v, float) and math.isnan(v)) or v == 0:
        return c["flat"]
    return c["up"] if v > 0 else c["down"]


# ---------- 數字 ----------
def _num(v):
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _sign(f, s):
    return ("+" + s) if f > 0 else (MINUS + s.lstrip("-")) if f < 0 else s


def fmt_price(v):
    f = _num(v)
    return "—" if f is None else f"{f:,.2f}"


def fmt_pct(v, digits=2, signed=True):
    f = _num(v)
    if f is None:
        return "—"
    s = f"{abs(f):,.{digits}f}%"
    return _sign(f, s) if signed else (MINUS + s if f < 0 else s)


def fmt_int(v, signed=False):
    f = _num(v)
    if f is None:
        return "—"
    s = f"{abs(round(f)):,.0f}"
    return _sign(f, s) if signed else (MINUS + s if f < 0 else s)


def fmt_money(v, signed=False):
    s = fmt_int(v, signed)
    return s if s == "—" else s + " 元"


def fmt_yi(v, digits=1, signed=True):
    """億元。"""
    f = _num(v)
    if f is None:
        return "—"
    s = f"{abs(f):,.{digits}f} 億"
    return _sign(f, s) if signed else s


def fmt_r(v):
    f = _num(v)
    return "—" if f is None else _sign(f, f"{abs(f):.2f}R")


def code_of(symbol):
    return str(symbol or "").split(".")[0]


def stock_label(symbol, name=None):
    c = code_of(symbol)
    return f"{c} {name}".strip() if name and str(name) != "nan" else c


# ---------- HTML 片段 ----------
def signed_span(v, text=None, bold=False):
    w = "600" if bold else "500"
    return (f"<span style='color:{dir_color(_num(v))};font-weight:{w};"
            f"font-variant-numeric:tabular-nums'>{text if text is not None else fmt_pct(v)}</span>")


# ---------- 表格 ----------
def style_signed(df, cols):
    """回傳 Styler：指定欄位依正負上漲跌色（其他欄位不動）。"""
    cols = [c for c in cols if c in df.columns]

    def _c(v):
        f = _num(v)
        return f"color: {dir_color(f)}" if f not in (None, 0) else ""
    sty = df.style
    if cols:
        sty = sty.map(_c, subset=cols)
    return sty


def clean_stock_col(df, sym_col="股票", name_col="公司名稱", out="股票"):
    """股票欄改成「代號 名稱」，移除 .TW/.TWO 與重複的公司名稱欄。"""
    if df is None or sym_col not in df.columns:
        return df
    d = df.copy()
    names = d[name_col] if name_col in d.columns else pd.Series([None] * len(d), index=d.index)
    d[out] = [stock_label(s, n) for s, n in zip(d[sym_col], names)]
    drop = [c for c in (name_col, "市場") if c in d.columns and c != out]
    return d.drop(columns=drop)


def rgba(hex_color, alpha):
    """'#D7263D', 0.12 → 'rgba(215, 38, 61, 0.12)'（Plotly 填色用）。"""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


_ICON = re.compile(r"^[^\w+]+")


def strip_icon(text):
    """去掉開頭的 emoji / 符號（「✅ 續抱」→「續抱」）。
    用 Python re 而不是 pandas .str.replace：pandas 3 的 pyarrow 字串用 RE2，\\w 只認 ASCII，會把中文一起刪掉。"""
    return _ICON.sub("", str(text)).strip() if text is not None else text
