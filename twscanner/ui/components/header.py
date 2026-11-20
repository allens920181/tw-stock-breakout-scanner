"""頁首：頁名、日期、台股 / 美股 / 大資金狀態，與一句綜合操作建議。"""

import html

import streamlit as st

from twscanner.core.tz import now_tw
from twscanner.ui import sync
from twscanner.ui.state import get_market_state_cached, get_us_state_cached


def chip_cls(regime):
    return {
        "bull": "bull", "bear": "bear", "neutral": "neutral",
        "risk_on": "bull", "risk_off": "bear",
    }.get(regime, "unknown")


def overall_advice(market_state, us_state=None, big_state=None):
    """把台股／美股／大資金三顆燈合成一句操作建議。回 (文字, css class)。"""
    tw_r = market_state.get("regime") if market_state else None
    if tw_r in (None, "unknown"):
        return "大盤資料載入中；掃描後會依台股、美股、大資金給出今天的方向", "unknown"
    us_r = us_state.get("regime") if us_state else None
    bf = big_state.get("position_factor", 1.0) if big_state else 1.0

    # 動能策略鐵律：台股空頭一律暫停（不放空個股）
    if tw_r == "bear":
        return "大盤空頭：不開新倉，只處理手上持股（只做多的策略，空頭時休息）", "bear"

    warns = []
    if us_r in ("bear", "risk_off"):
        warns.append("美股轉弱")
    if bf <= 0.5:
        warns.append("大資金偏空")
    if tw_r == "neutral":
        warns.append("台股中性")

    if tw_r == "bull" and not warns:
        return "環境偏多：可以照訊號正常進場，讓獲利的部位續抱", "bull"
    if len(warns) >= 2:
        return ("多重警訊（" + "、".join(warns)
                + "）：大幅減碼，只做最強勢、嚴設停損", "bear")
    return ("環境分歧（" + "、".join(warns)
            + "）：部位縮小、只挑最強的", "neutral")


WEEKDAYS = "一二三四五六日"


def zh_date(dt):
    """2026 年 11 月 19 日（週四）"""
    return f"{dt.year} 年 {dt.month} 月 {dt.day} 日（週{WEEKDAYS[dt.weekday()]}）"


def _status_items(market_state, us_state):
    """台股 / 美股 / 大資金 → [(名稱, 狀態文字, css class, 說明)]。無資料時顯示「待掃描」。"""
    def clean(label):
        for sym in ("🟢", "🔴", "🟡", "⚪"):
            label = label.replace(sym, "")
        return label.strip()

    items = []
    if market_state and market_state.get("regime") not in (None, "unknown"):
        items.append(("台股", clean(market_state["label"]), chip_cls(market_state["regime"]),
                      market_state.get("detail", "")))
    else:
        items.append(("台股", "待掃描", "unknown", "掃描後更新"))
    if us_state and us_state.get("regime") not in (None, "unknown"):
        items.append(("美股", clean(us_state["label"]), chip_cls(us_state["regime"]), us_state.get("detail", "")))
    else:
        items.append(("美股", "待掃描", "unknown", "掃描後更新"))
    big = market_state.get("big_state") if market_state else None
    if big:
        bf = big.get("position_factor", 1.0)
        items.append(("大資金", clean(big.get("label", "")), "bull" if bf >= 1.0 else ("neutral" if bf >= 0.75 else "bear"),
                      big.get("detail", "")))
    else:
        items.append(("大資金", "待掃描", "unknown", "外資台指期、台幣、大盤融資，掃描時計算"))
    return items


def render_header(title, market_state, last_scan_at=None, us_state=None, advice=True):
    """頁首：左邊頁名與日期，右邊三個市場狀態（文字 + 小圓點），下面一行白話建議。不用框線與色條。"""
    esc = html.escape
    status = "".join(
        f"<span class='mkt-item' title='{esc(str(detail))}'><i class='dot {cls}'></i>"
        f"<span class='k'>{esc(name)}</span>{esc(label)}</span>"
        for name, label, cls, detail in _status_items(market_state, us_state))
    big = market_state.get("big_state") if market_state else None
    adv_text, adv_cls = overall_advice(market_state, us_state, big)
    meta = zh_date(now_tw()) + (f" · 上次掃描 {last_scan_at}" if last_scan_at else "")
    sync_text, sync_state = sync.status()
    sync_html = (f" · <span class='sync-state {sync_state}'><i class='dot {sync_state}'></i>{esc(sync_text)}</span>"
                 if sync_text else "")
    st.markdown(
        f"<div class='page-head'><div><div class='page-title'>{esc(title)}</div>"
        f"<div class='page-meta'>{esc(meta)}{sync_html}</div></div>"
        f"<div class='mkt'>{status}</div></div>"
        + (f"<div class='mkt-advice {adv_cls}'>{esc(adv_text)}</div>" if advice else "<div class='mkt-advice'></div>"),
        unsafe_allow_html=True)


def render_page_header(title, advice=True):
    """優先用本次掃描的大盤狀態，沒有就即時抓（快取）。"""
    last_scan_at = st.session_state.get("last_scan_at")
    market_state = us_state = None
    if "result" in st.session_state:
        market_state = st.session_state["result"].get("market_state")
        if market_state:
            us_state = market_state.get("us_state")
    if market_state is None:
        try:
            market_state = get_market_state_cached()
        except Exception:
            market_state = None
    if us_state is None:
        try:
            us_state = get_us_state_cached()
        except Exception:
            us_state = None
    render_header(title, market_state, last_scan_at, us_state=us_state, advice=advice)
