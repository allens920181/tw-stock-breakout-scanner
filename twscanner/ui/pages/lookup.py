"""個股健檢：這檔現在能不能買、手上的該不該賣、公司體質如何（財報白話）、K 線。"""
import html

import streamlit as st

from twscanner.reporting.kline import make_kline
from twscanner.services import run_single_lookup
from twscanner.services.today import trade_plan
from twscanner.ui.components.blocks import (
    action_badge,
    asof,
    buy_form,
    callout,
    conclusion,
    kpi_row,
    plan_card,
    price_ladder_html,
    signed_value,
)
from twscanner.ui.format import colors, fmt_pct, fmt_price, fmt_r, strip_icon
from twscanner.ui.settings import build_cfg
from twscanner.ui.state import get_code_name_map
from twscanner.ui.theme import CHART_CONFIG

VERDICT = {"good": ("良好", "up"), "neutral": ("普通", "info"), "bad": ("注意", "act-urgent"),
           "na": ("不適用", "act-hold")}
LESSON = {"revenue": "營運 › 月營收", "margin": "財報 › 毛利率", "op_income": "財報 › 本業與業外",
          "eps": "財報 › EPS", "pe": "股票 › 本益比", "balance": "財報 › 資產負債表", "pb": "股票 › 股價淨值比"}


def _search():
    q1, q2, q3 = st.columns([1.4, 1.2, 0.8])
    code = q1.text_input("股票代號", key="lookup_code", placeholder="例如 2330")
    cost = q2.number_input("我的成本價（沒持有就留 0）", min_value=0.0, value=0.0, step=0.5, key="lookup_cost",
                           help="填了才會給出場建議。沒填進場日時，系統以最近一次成交價觸及成本價的日子推估。")
    q3.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    go = q3.button("健檢", type="primary", key="lookup_btn", use_container_width=True)
    if go and code.strip():
        with st.status("查詢中 …", expanded=False) as status:
            try:
                res = run_single_lookup(
                    code.strip(), build_cfg(), company_name=get_code_name_map().get(code.strip(), ""),
                    entry_price=cost if cost > 0 else None,
                    progress_cb=lambda p, m: status.update(label=f"查詢中：{m}"))
                st.session_state["lookup_result"] = res
                status.update(label="完成", state="complete")
            except Exception as e:
                st.session_state["lookup_result"] = {"error": str(e)}
                status.update(label=f"查詢失敗：{e}", state="error")
    elif go:
        st.warning("請輸入股票代號")


def _lead(res):
    sc, hd = res["scoring"], res.get("holding")
    if hd:
        act = strip_icon(hd.get("操作建議", ""))
        urgent = hd.get("賣出量") in ("全出", "賣半")
        return (f"持有中：{act}", f"{hd.get('說明', '')}", "stop" if urgent else "info")
    signal = sc.get("訊號判斷")
    if signal == "進場":
        return (f"可以考慮進場：{sc.get('操作建議', '')}", sc.get("評級理由"), "go")
    if signal == "觀察":
        return (f"先觀察：{sc.get('操作建議', '')}", sc.get("評級理由"), "wait")
    return (f"目前不建議買：{sc.get('操作建議', '') or '未達條件'}", sc.get("評級理由"), "wait")


def _exit_section(hd):
    st.markdown("### 出場建議")
    urgent = hd.get("賣出量") in ("全出", "賣半")
    ladder = price_ladder_html(hd.get("停損價"), hd.get("成本價"), hd.get("目標1(+1R半倉)"),
                               hd.get("目標2(+2R出清)"), hd.get("目前價"))
    st.markdown(
        f"<div class='plan'><div class='top'><div class='name'>{action_badge(hd.get('操作建議'), urgent)}"
        f"　賣出量：{hd.get('賣出量', '—')}</div><div>{fmt_r(hd.get('R倍數'))} · "
        f"{signed_value(hd.get('報酬%'))}</div></div>"
        f"<div class='grid'>"
        + "".join(f"<div class='cell'><div class='l'>{lbl}</div><div class='v'>{fmt_price(hd.get(k))}</div></div>"
                  for lbl, k in (("停損價", "停損價"), ("成本", "成本價"), ("+1R 賣一半", "目標1(+1R半倉)"),
                                 ("+2R", "目標2(+2R出清)"), ("移動停利", "移動停利(ATR)")))
        + f"</div>{ladder}<div class='rule'>{html.escape(str(hd.get('說明', '')))}<br>"
        f"趨勢：{html.escape(str(hd.get('趨勢強度', '—')))} · 進場日：{html.escape(str(hd.get('進場日來源', '—')))}"
        f"</div></div>", unsafe_allow_html=True)
    if hd.get("主動警示") and hd["主動警示"] != "—":
        callout(f"持股警示：{html.escape(str(hd['主動警示']))}")


def _health_section(health):
    st.markdown("### 公司體檢")
    if not health or not health["items"]:
        st.caption(health["summary"] if health else "查無財報資料。")
        return
    st.markdown(f"**{health['summary']}**　<span class='asof'>財報期間：{health['period']}（證交所最新公告）</span>",
                unsafe_allow_html=True)
    rows = []
    for it in health["items"]:
        label, cls = VERDICT[it["verdict"]]
        rows.append(f"<div class='rowline'><div class='health-v'><span class='badge {cls}'>{label}</span></div>"
                    f"<div class='main'><div class='t'>{it['name']}　<span class='num'>{it['value']}</span></div>"
                    f"<div class='d'>{html.escape(it['plain'])}<br><span style='font-size:0.75rem'>看懂這個數字：學習中心 › "
                    f"{LESSON.get(it['lesson'], '財報')}</span></div></div></div>")
    st.markdown("".join(rows), unsafe_allow_html=True)
    st.caption("對 1 個月內的短線操作，基本面用來「避開地雷」，進出場時機仍以技術面與交易計畫為準。")


def _add_check(sc):
    with st.expander("加碼檢查：現在加碼合理嗎？", expanded=False):
        from twscanner.analysis.sizing import evaluate_add
        cur = sc.get("目前現價") or sc.get("收盤價")
        lots = st.number_input("想加幾張", min_value=1, max_value=100, value=1, step=1, key="add_lots")
        ev = evaluate_add(build_cfg(), cur, sc.get("ATR14"), sc.get("乖離MA20%"),
                          sc.get("相對強度RS%"), int(lots))
        verdict = ev["verdict"].lstrip("🟢🟡🔴 ").strip()
        st.markdown(f"**{verdict}**")
        for b in ev["blocks"]:
            st.markdown(f"- 不建議：{b}")
        for w in ev["warns"]:
            st.markdown(f"- 注意：{w}")
        kpi_row([("加碼停損", fmt_price(ev["stop"]), None),
                 ("每股風險", fmt_price(ev["risk_per_share"]), None),
                 ("加碼風險", f"{ev['add_risk']:,.0f} 元" if ev["add_risk"] is not None else "—", None),
                 ("佔資金", f"{ev['cost_pct']}%" if ev["cost_pct"] is not None else "—", None)])
        st.caption("加碼原則：不追過度延伸的價格；加碼量不超過原部位；加碼後把整體停損上移，總風險守住單筆上限。")


def render():
    _search()
    res = st.session_state.get("lookup_result")
    if not res:
        conclusion("輸入代號做個股健檢",
                   "會告訴你：現在能不能買（含完整交易計畫）、手上持有的該不該賣、這家公司的財報體質，"
                   "每個數字都附白話說明。", "info")
        return
    if res.get("error"):
        st.error(res["error"])
        return
    sc, hd = res["scoring"], res.get("holding")
    lead, sub, tone = _lead(res)
    st.markdown(f"## {res['name']} <span style='color:var(--muted);font-weight:500'>"
                f"{res['symbol'].split('.')[0]}</span>", unsafe_allow_html=True)
    conclusion(lead, sub, tone)
    df = res.get("df")
    if df is not None and len(df) > 1:
        asof(f"價格資料截至 {df.index[-1]:%Y-%m-%d}")
        chg = (df["Close"].iloc[-1] / df["Close"].iloc[-2] - 1) * 100
    else:
        chg = None
    rev = res.get("revenue") or {}
    price = sc.get("目前現價") or sc.get("收盤價")
    if (price is None or price != price) and df is not None and len(df):
        price = float(df["Close"].dropna().iloc[-1])
    kpi_row([
        ("現價", fmt_price(price),
         signed_value(chg, fmt_pct(chg)) if chg is not None else None),
        ("等級 / 分數", f"{sc.get('綜合評級') or '未評級'}",
         f"{sc.get('評分顯示', sc.get('評分', '—'))} 分" if sc.get("綜合評級") else (sc.get("狀態") or None)),
        ("比大盤強多少（60 日）", signed_value(sc.get("相對強度RS%"), fmt_pct(sc.get("相對強度RS%"))), None),
        ("營收年增", signed_value(rev.get("yoy_pct"), fmt_pct(rev.get("yoy_pct"), 1))
         if rev.get("yoy_pct") is not None else "—", None),
    ])

    if hd:
        _exit_section(hd)
    else:
        st.markdown("### 交易計畫")
        plan = trade_plan(sc)
        if plan["entry"] and plan["stop"]:
            plan_card(plan)
            if sc.get("訊號判斷") in ("進場", "觀察"):
                buy_form(plan, key=f"lookup_{plan['code']}")
        else:
            st.caption(f"目前沒有交易計畫：{sc.get('操作建議', '') or '未通過品質過濾'}"
                       f"{'（' + str(sc.get('評級理由')) + '）' if sc.get('評級理由') else ''}")

    _health_section(res.get("health"))

    if df is not None and len(df) > 30:
        st.markdown("### K 線")
        c = colors()
        src = hd or {}
        fig = make_kline(df, title="", entry=src.get("成本價") or sc.get("進場參考價"),
                         stop=src.get("停損價") or sc.get("停損價"),
                         target1=src.get("目標1(+1R半倉)") or sc.get("目標價1(+1R半倉)"),
                         target2=src.get("目標2(+2R出清)") or sc.get("目標價2(+2R出清)"),
                         recent_bars=120, up=c["up"], down=c["down"])
        if fig:
            st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    _add_check(sc)
    st.caption("決策輔助，非投資建議。籌碼、營收、財報為官方公開資料的當日快照。")
