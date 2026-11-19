"""
今日決策（預設首頁）：照每日流程排版 —
能不能開新倉 → 先處理持股 → 今日候選交易計畫 → 組合風險與本月目標 → 交易紀律。
"""

import html

import streamlit as st

from twscanner.core.tz import today_tw
from twscanner.portfolio.trade_log import compute
from twscanner.services.today import build_today
from twscanner.ui.actions import analyze_holdings, execute_scan
from twscanner.ui.components.blocks import (
    action_badge,
    asof,
    buy_form,
    callout,
    conclusion,
    empty,
    kpi_row,
    plan_card,
    signed_value,
)
from twscanner.ui.format import dir_color, fmt_money, fmt_pct, fmt_r, stock_label
from twscanner.ui.settings import build_cfg
from twscanner.ui.state import get_market_state_cached, get_sector_map, get_trades_df

RULES = [
    "進場前先決定停損價與張數，下單時一起設好停損。",
    "虧損的部位不攤平；到停損價就出場，不找理由。",
    "到 +1R 先賣一半，剩下的用移動停利保護。",
    "10 個交易日還沒到 +1R 就出場，資金拿去做更好的機會。",
    "本月虧損到上限就停手，下個月再來。目標是三個月平均，不是每個月都要賺。",
]


def _market_state():
    res = st.session_state.get("result")
    if res and res.get("market_state"):
        return res["market_state"]
    try:
        return get_market_state_cached()
    except Exception:
        return None


def _goal_section(t):
    prog, plan, target = t["progress"], t["plan"], t["target"]
    st.markdown("### 本月目標")
    pct = max(0.0, min(100.0, prog["pct"] or 0.0)) if prog["realized"] > 0 else 0.0
    color = dir_color(prog["realized"])
    st.markdown(
        f"<div class='rowline'><div class='main'><div class='t'>本月已實現 "
        f"<span style='color:{color}'>{fmt_money(prog['realized'], signed=True)}</span>"
        f" / 目標 {fmt_money(target)}</div>"
        f"<div class='goalbar'><div style='width:{pct:.0f}%;background:{color}'></div></div>"
        f"<div class='d'>{prog['status']}</div></div></div>", unsafe_allow_html=True)
    lines = [plan["verdict"]]
    sim = plan.get("sim")
    if sim:
        lines.append(f"用這組統計模擬一萬個月：平均每月 {fmt_money(sim['mean'], signed=True)}，"
                     f"{sim['p_loss'] * 100:.0f}% 的月份會虧損，{sim['p_hit'] * 100:.0f}% 的月份達標。"
                     "所以用近 3 個月平均來看目標。")
    lines.append(f"每筆最多賠 {fmt_money(plan['risk_amount'])}；本月虧損上限 {fmt_money(plan['loss_limit'])}"
                 f"（{plan['loss_limit_r']:.0f}R）。")
    st.markdown("\n".join(f"- {x}" for x in lines))
    if t["stats"]:
        s = t["stats"]
        st.caption(f"統計來源：{s['source']} {s['n']} 筆 · 勝率 {s['win_rate'] * 100:.0f}% · "
                   f"平均賺 {s['avg_win_r']:.2f}R · 期望值 {s['expectancy_r']:+.2f}R")


def render(sb):
    cfg = build_cfg()
    holdings_res = st.session_state.get("holdings_result")
    holdings_df = holdings_res["df"] if holdings_res else None
    trades = compute(get_trades_df(), cfg.get("costs"))
    scan_df = st.session_state["result"]["df"] if st.session_state.get("result") else None
    t = build_today(
        _market_state(), scan_df, holdings_df, trades, cfg, today_tw().strftime("%Y-%m"),
        target=float(st.session_state.get("month_target", 10_000)),
        loss_limit_r=float(st.session_state.get("loss_limit_r", 2.0)),
        backtest=st.session_state.get("backtest_result"), sector_map=get_sector_map())

    tone = "stop" if not t["can_open"] else ("go" if any(c["signal"] == "進場" for c in t["candidates"])
                                             else "wait")
    sub = "；".join(t["reasons"]) if t["reasons"] else None
    conclusion(t["headline"], sub, tone)
    parts = []
    if st.session_state.get("last_scan_at"):
        parts.append(f"掃描 {st.session_state['last_scan_at']}")
    if st.session_state.get("holdings_analyzed_at"):
        parts.append(f"持股分析 {st.session_state['holdings_analyzed_at']}")
    if parts:
        asof("資料時間：" + " · ".join(parts))

    risk = t["risk"]
    prog = t["progress"]
    kpi_row([
        ("本月已實現", signed_value(prog["realized"], fmt_money(prog["realized"], signed=True)),
         f"目標 {fmt_money(t['target'])}"),
        ("近 3 個月平均", signed_value(prog["avg3"], fmt_money(prog["avg3"], signed=True)),
         f"以 {prog['months_in_avg']} 個月計"),
        ("全部打到停損會賠", f"{risk['risk_pct']:.1f}%" if risk["risk_pct"] is not None else "—",
         f"上限 {risk['max_risk_pct']:.0f}% · {fmt_money(risk['total_risk'])}"),
        ("持股", f"{risk['positions']} 檔", f"{len(t['urgent'])} 檔需要處理" if t["urgent"] else "沒有需要處理的"),
    ])
    for w in risk["warnings"]:
        callout(w)

    # 1. 持股
    st.markdown("### 1. 先處理持股")
    hold_edit = st.session_state.get("holdings_df")
    if not t["actions"]:
        if hold_edit is not None and len(hold_edit):
            empty("持股還沒分析", f"你有 {len(hold_edit)} 檔持股，按下面按鈕取得今天的出場建議。")
            if st.button("分析持股", type="primary", key="today_hold"):
                analyze_holdings(hold_edit)
                st.rerun()
        else:
            empty("目前沒有持股", "買進後在交易計畫卡按「我已買進」，或到「持股與紀錄」輸入。")
    else:
        rows = []
        for a in t["actions"]:
            meta = []
            if a["pnl_pct"] is not None:
                meta.append(f"<span style='color:{dir_color(a['pnl_pct'])}'>{fmt_pct(a['pnl_pct'])}</span>")
            if a["r"] is not None:
                meta.append(fmt_r(a["r"]))
            rows.append(
                f"<div class='rowline'><div class='main'><div class='t'>{stock_label(a['code'], a['name'])}"
                f"　{action_badge(a['action'], a['urgent'])}</div>"
                f"<div class='d'>{html.escape(str(a['note'] or ''))}"
                + (f"<br>進場日：{a['entry_source']}" if a.get("entry_source") and "推估" in str(a["entry_source"])
                   else "") + f"</div></div><div class='v'>{' · '.join(meta)}</div></div>")
        st.markdown("".join(rows), unsafe_allow_html=True)
        if st.button("重新分析持股", key="today_rehold"):
            analyze_holdings(hold_edit)
            st.rerun()

    # 2. 候選
    st.markdown("### 2. 今日候選")
    if scan_df is None:
        empty("今天還沒掃描", "依側欄的資料來源與策略模式掃描（全台股首次約 5–15 分鐘，同日重跑不到 1 分鐘）。"
              "手機上請點左上角「›」打開側欄。")
        if st.button("開始掃描", type="primary", key="today_scan"):
            execute_scan(sb)
            st.rerun()
    elif not t["candidates"]:
        empty("沒有進場或觀察名單", "今天沒有符合條件的股票。沒有好機會時不做，也是一種操作。")
    elif not t["can_open"]:
        with st.expander(f"觀察名單（今天不開新倉，共 {len(t['candidates'])} 檔）", expanded=False):
            for p in t["candidates"]:
                plan_card(p)
    else:
        st.caption("依訊號與分數排序。每張卡都是一份完整交易計畫：照計畫下單，不臨場改。")
        for p in t["candidates"]:
            plan_card(p)
            buy_form(p, key=f"today_{p['code']}")

    # 3. 目標與紀律
    _goal_section(t)
    with st.expander("交易紀律（每次下單前看一遍）", expanded=False):
        st.markdown("\n".join(f"{i}. {r}" for i, r in enumerate(RULES, 1)))
