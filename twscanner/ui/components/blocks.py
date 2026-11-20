"""
共用版面積木（設計基準 v1 第 6 節）。每個頁面都由這些組成，外觀才會一致。

結論句 → KPI 列 → 主體 → 進階；徽章、交易計畫卡、空狀態、資料時間都在這裡。
"""
import html

import streamlit as st

from twscanner.ui.format import dir_color, fmt_money, fmt_pct, fmt_price, strip_icon

# 交易紀律：完整版在學習中心；平常在用得到的地方出現（我已買進、持股出場建議、月虧損上限）
TRADING_RULES = [
    "進場前先決定停損價與張數，下單時一起設好停損。",
    "虧損的部位不攤平；到停損價就出場，不找理由。",
    "到 +1R 先賣一半，剩下的用移動停利保護。",
    "10 個交易日還沒到 +1R 就出場，資金拿去做更好的機會。",
    "本月虧損到上限就停手，下個月再來。目標是三個月平均，不是每個月都要賺。",
]

GRADE_TEXT = {"A": "A 強力進場", "B": "B 可進場", "C": "C 觀察", "避開": "避開"}


def _e(s):
    return html.escape(str(s)) if s is not None else ""


TONE_LABEL = {"go": "可行動", "stop": "注意", "wait": "觀望", "info": ""}


def conclusion(lead, sub=None, tone="info"):
    """tone: go（可行動）/ stop（暫停、需處理）/ wait（中性等待）/ info。文字一律跳脫（資料裡常有 < 符號）。"""
    label = TONE_LABEL.get(tone, "")
    st.markdown(f"<div class='conclusion {tone}'>"
                + (f"<span class='tone'>{label}</span>" if label else "")
                + f"<span class='lead'>{_e(strip_icon(lead))}</span>"
                + (f"<span class='sub'>{_e(sub)}</span>" if sub else "") + "</div>",
                unsafe_allow_html=True)


def kpi_row(items):
    """items: [(label, value, sub)]，最多 4 個；value 可含 HTML（已格式化的數字）。"""
    items = list(items)[:4]
    cells = "".join(
        f"<div class='kpi'><div class='label'>{_e(label)}</div><div class='value'>{value}</div>"
        + (f"<div class='sub'>{sub}</div>" if sub else "") + "</div>"
        for label, value, sub in items)
    # 單一 grid：桌機一列 N 個、手機 2×2（st.columns 在手機會疊成一長串）
    st.markdown(f"<div class='kpi-grid' style='--n:{len(items)}'>{cells}</div>", unsafe_allow_html=True)


def grade_badge(grade):
    g = str(grade or "")
    cls = {"A": "grade-A", "B": "grade-B", "C": "grade-C"}.get(g, "grade-X")
    return f"<span class='badge {cls}'>{_e(GRADE_TEXT.get(g, g or '—'))}</span>"


def action_badge(text, urgent):
    return f"<span class='badge {'act-urgent' if urgent else 'act-hold'}'>{_e(strip_icon(text))}</span>"


def tag(text, kind="info"):
    return f"<span class='badge {kind}'>{_e(text)}</span>"


def asof(text):
    st.markdown(f"<div class='asof'>{_e(text)}</div>", unsafe_allow_html=True)


def empty(title, body=""):
    st.markdown(f"<div class='empty'><b>{_e(title)}</b><br>{body}</div>", unsafe_allow_html=True)


def callout(text, kind="caution"):
    st.markdown(f"<div class='callout {'info' if kind == 'info' else ''}'>{text}</div>",
                unsafe_allow_html=True)


def price_ladder_html(stop, entry, t1, t2, current=None):
    """停損 — 進場 — 目標1 — 目標2 的位置條（現價以實線標示）。"""
    pts = [p for p in (stop, entry, t1, t2, current) if p]
    if len(pts) < 3:
        return ""
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1

    def x(p):
        return 4 + (p - lo) / span * 92

    marks = []
    for label, p, color in (("停損", stop, "var(--down)"), ("進場", entry, "var(--text)"),
                            ("+1R", t1, "var(--up)"), ("+2R", t2, "var(--up)"),
                            ("現價", current, "var(--info)")):
        if p:
            marks.append(f"<div class='mk' style='left:{x(p):.1f}%;background:{color}'></div>"
                         f"<div class='lb' style='left:{x(p):.1f}%;top:22px'>{label}</div>")
    return f"<div class='ladder' style='margin-bottom:16px'><div class='track'></div>{''.join(marks)}</div>"


def plan_card(p):
    """services.today.trade_plan 的結果 → 交易計畫卡。"""
    signal = p.get("signal") or ""
    sig_tag = tag("達進場標準", "up") if signal == "進場" else tag("觀察，未達進場", "info")
    risk_amt = fmt_money(p["risk_amount"]) if p.get("risk_amount") else "—"
    cells = [("進場價", fmt_price(p.get("entry"))),
             ("停損價", fmt_price(p.get("stop"))),
             ("目標 +1R / +2R", f"{fmt_price(p.get('t1'))} / {fmt_price(p.get('t2'))}"),
             ("建議張數", f"{p.get('lots') or 0} 張"),
             ("這筆最多賠", risk_amt)]
    grid = "".join(f"<div class='cell'><div class='l'>{_e(lbl)}</div><div class='v'>{v}</div></div>"
                   for lbl, v in cells)
    reasons = "".join(f"<span class='tag'>{_e(r)}</span>" for r in p.get("reasons") or [])
    entry_note = f"{_e(p.get('entry_type'))}：{_e(p.get('entry_note'))}" if p.get("entry_note") else ""
    st.markdown(
        f"<div class='plan'><div class='top'><div><span class='code'>{_e(p.get('code'))}</span>"
        f"<span class='name'>{_e(p.get('name'))}</span></div>"
        f"<div>{grade_badge(p.get('grade'))} {sig_tag}</div></div>"
        f"<div class='grid'>{grid}</div>"
        f"{price_ladder_html(p.get('stop'), p.get('entry'), p.get('t1'), p.get('t2'))}"
        f"<div class='why'>{('<b>為什麼入選</b>　' + reasons) if reasons else ''}</div>"
        f"<div class='rule'>{entry_note + '<br>' if entry_note else ''}"
        f"出場規則：{_e(p.get('invalidation'))}；到 +1R 賣一半、+2R 看趨勢；"
        f"10 個交易日沒到 +1R 就時間停損，最長抱約 {p.get('max_hold_days', 20)} 個交易日。</div></div>",
        unsafe_allow_html=True)


def signed_value(v, text=None, digits=2):
    """KPI 用：依正負上色的數字 HTML。"""
    t = text if text is not None else fmt_pct(v, digits)
    return f"<span style='color:{dir_color(v)}'>{t}</span>"


def buy_form(plan, key):
    """「我已買進 → 加入持股」：成交價與張數預設帶交易計畫的值。"""
    from twscanner.ui.state import add_holding

    with st.expander("我已買進 → 加入持股", expanded=False):
        stop = plan.get("stop")
        st.caption(f"下單前：同時設好停損 {fmt_price(stop)}，跌破就出場、不攤平；到 +1R 先賣一半；"
                   f"10 個交易日沒到 +1R 就出場。" if stop else "下單前先決定停損價與張數，下單時一起設好停損。")
        c1, c2, c3 = st.columns([1, 1, 1])
        price = c1.number_input("成交價", value=float(plan.get("entry") or 0), step=0.5, key=f"{key}_px")
        lots = c2.number_input("張數", value=max(1, int(plan.get("lots") or 1)), min_value=1, step=1,
                               key=f"{key}_lots")
        if c3.button("加入持股", type="primary", key=f"{key}_buy", use_container_width=True):
            add_holding(plan["code"], plan["name"], price, int(lots) * 1000)
            st.toast(f"已加入持股：{plan['code']} {plan['name']} {int(lots)} 張 @ {price:,.2f}")
