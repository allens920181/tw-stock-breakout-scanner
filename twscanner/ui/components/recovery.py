"""止跌檢查區塊：四個止跌訊號 + 劇本線索。今日決策（空頭時）與資金流向頁共用。"""

import html

import streamlit as st

from twscanner.ui.components.blocks import tag

SIG_TAG = {True: ("成立", "info"), False: ("未成立", "act-hold"), None: ("無資料", "act-hold")}
CLUE_TAG = {"shock": ("偏衝擊型", "info"), "recession": ("衰退警訊", "act-urgent"),
            "neutral": ("中性", "act-hold"), None: ("—", "act-hold")}

# 數字來自 scripts/strategy_study/recovery_signals.py → docs/research/recovery_2026-11.json
EVIDENCE = (
    "**回測（1999–2026，加權距一年高點跌 15% 以上的期間）**\n\n"
    "- 成立越多，之後**再跌得越少**：VIX、20 日線、半導體三個都成立時，之後 60 天內再跌的中位數是 −5%；"
    "都沒成立時是 −10%。\n"
    "- 但**不代表會漲**：三個都成立時，之後 60 天平均 −1.8%，反而比都沒成立的 +1.7% 差。"
    "第一次全部成立的 9 次裡，有 4 次一年後還在下跌（2000、2007 年跌了 45–50%）。\n"
    "- 加上外資（2012 年起才有資料）結論一樣，樣本更少。\n\n"
    "**怎麼用**：這是「賣壓減輕、比較不容易再重挫」的參考，不是買進訊號。開不開新倉仍照大盤狀態；"
    "大盤轉回中性或多頭，系統會自己恢復給候選。\n\n"
    "**劇本線索**：分辨「衝擊型」（2015、2020、2025：4–21 個月收復）與「景氣 / 獲利衰退型」"
    "（2000、2008：之後又跌 44–54%）。衰退線索通常比股價慢，不能抓買點；它們翻壞，代表這次可能不是單純的衝擊。"
)


def _row(title, badge, detail, note=""):
    return (f"<div class='rowline'><div class='main'><div class='t'>{html.escape(title)}　{badge}</div>"
            f"<div class='d'>{html.escape(detail)}" + (f"<br>{html.escape(note)}" if note else "")
            + "</div></div></div>")


def render_recovery(data, heading="止跌檢查"):
    if not data:
        st.caption("止跌訊號暫時抓不到資料，稍後再試。")
        return
    s = data["summary"]
    st.markdown(f"### {heading}")
    st.markdown(f"**{s['ok']}/{s['total']} 個止跌訊號成立**　{html.escape(s['lean'])}。")
    st.markdown("".join(_row(x["name"], tag(*SIG_TAG[x["ok"]]), x["value"], f"條件：{x['rule']}")
                        for x in data["signals"]), unsafe_allow_html=True)
    with st.expander(f"劇本線索：{s['warn']} 項衰退警訊"):
        st.markdown("".join(_row(c["name"], tag(*CLUE_TAG[c["verdict"]]), c["value"], c["note"])
                            for c in data["clues"]), unsafe_allow_html=True)
    with st.expander("這些訊號準嗎？"):
        st.markdown(EVIDENCE)
    if data.get("asof") is not None:
        st.caption(f"資料截至 {data['asof']:%Y/%m/%d}；美股為前一個交易日收盤。來源：Yahoo Finance、FinMind、FRED、證交所。")
