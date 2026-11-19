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
        return "掃描後依台股／美股／大資金三項給出操作指引", "unknown"
    us_r = us_state.get("regime") if us_state else None
    bf = big_state.get("position_factor", 1.0) if big_state else 1.0

    # 動能策略鐵律：台股空頭一律暫停（不放空個股）
    if tw_r == "bear":
        return "🔴 大盤空頭 — 暫停進場，優先保護持股、嚴設停損", "bear"

    warns = []
    if us_r in ("bear", "risk_off"):
        warns.append("美股轉弱")
    if bf <= 0.5:
        warns.append("大資金偏空")
    if tw_r == "neutral":
        warns.append("台股中性")

    if tw_r == "bull" and not warns:
        return "🟢 環境偏多 — 可正常／積極進場，照訊號操作、讓利潤奔跑", "bull"
    if len(warns) >= 2:
        return ("🟠 多重警訊（" + "、".join(warns)
                + "）— 大幅減碼，只做最強勢、嚴設停損", "bear")
    return ("🟡 環境分歧（" + "、".join(warns)
            + "）— 減碼謹慎，提高選股門檻、縮小部位", "neutral")


def render_header(market_state, last_scan_at=None, us_state=None):
    """整合的 header：左側標題，右側大盤三 chip + 綜合判斷建議 + 日期/上次掃描"""
    date_str = now_tw().strftime('%Y / %m / %d  %A')
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
    last = f"<span class='sep'>·</span>上次掃描 {last_scan_at}" if last_scan_at else ""

    adv_text, adv_cls = overall_advice(market_state, us_state, big_state)
    advice_html = (
        f"<div class='hdr-advice {adv_cls}'><span class='dot'></span>"
        f"<b>判斷建議</b>　{adv_text}</div>"
    )

    st.markdown(
        f"""
<div class='app-header'>
  <div>
    <div class='app-title'>台股強勢突破掃描器</div>
    <div class='app-sub'>加權評分 · 換手率分析 · 操作建議</div>
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
