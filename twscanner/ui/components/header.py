"""頁首：台股 / 美股 / 大資金三顆燈 + 綜合操作建議。"""

import streamlit as st

from twscanner.core.tz import now_tw
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


def render_header(market_state, last_scan_at=None, us_state=None):
    """整合的 header：左側標題，右側大盤三 chip + 綜合判斷建議 + 日期/上次掃描"""
    date_str = zh_date(now_tw())
    chips = []

    def _clean(label):
        for sym in ["🟢", "🔴", "🟡", "⚪"]:
            label = label.replace(sym, "")
        return label.strip()

    def _chip(name, label, cls, detail):
        chips.append(
            f"<div class='hdr-status {cls}' title='{detail}'>"
            f"<span class='dot'></span><b>{name} {label}</b></div>"
        )

    # 三顆燈永遠顯示；無資料時顯示「待掃描」灰燈，避免看起來像壞掉
    if market_state and market_state.get("regime") not in (None, "unknown"):
        _chip("台股", _clean(market_state["label"]), chip_cls(market_state["regime"]),
              market_state.get("detail", ""))
    else:
        _chip("台股", "待掃描", "unknown", "按「開始掃描」後更新")

    if us_state and us_state.get("regime") not in (None, "unknown"):
        _chip("美股", _clean(us_state["label"]), chip_cls(us_state["regime"]),
              us_state.get("detail", ""))
    else:
        _chip("美股", "待掃描", "unknown", "按「開始掃描」後更新")

    big_state = market_state.get("big_state") if market_state else None
    if big_state:
        _bf = big_state.get("position_factor", 1.0)
        bcls = "bull" if _bf >= 1.0 else ("neutral" if _bf >= 0.75 else "bear")
        _chip("大資金", _clean(big_state.get("label", "")), bcls,
              big_state.get("detail", ""))
    else:
        _chip("大資金", "待掃描", "unknown",
              "外資台指期/台幣/大盤融資，掃描時計算")

    status_html = "<div class='hdr-chips'>" + "".join(chips) + "</div>" if chips else ""
    last = f" · 上次掃描 {last_scan_at}" if last_scan_at else ""

    adv_text, adv_cls = overall_advice(market_state, us_state, big_state)
    advice_html = (
        f"<div class='hdr-advice {adv_cls}'><span class='dot'></span>"
        f"<b>判斷建議</b>　{adv_text}</div>"
    )

    st.markdown(
        f"""
<div class='app-header'>
  <div>
    <div class='app-title'>台股波段決策系統</div>
    <div class='app-sub'>找標的 · 管持股 · 控風險 · 看懂市場</div>
  </div>
  <div class='hdr-right'>
    {status_html}
    <div class='app-date'>{date_str}{last}</div>
  </div>
</div>
{advice_html}
""",
        unsafe_allow_html=True,
    )


def render_market_header():
    """頁首：優先用本次掃描的大盤狀態，沒有就即時抓（快取）。"""
    last_scan_at = st.session_state.get("last_scan_at")
    market_state = None
    us_state = None
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
    render_header(market_state, last_scan_at, us_state=us_state)
