"""
今日決策（預設首頁）：結論 → 三個數字 → 今天要做的事（左欄）＋本月目標（右欄）。
大盤空頭時，右欄最上面多一塊「止跌檢查」：回答「什麼時候可以再開新倉」。

順序跟著情境：有持股要處理時先列持股（先賣後買）；沒有時候選交易計畫排第一。
同一個數字只出現一次；交易紀律在用得到的地方出現（我已買進、出場建議），完整版在學習中心。
"""

import html

import streamlit as st

from twscanner.analysis.goal import capital_for_target
from twscanner.core.tz import today_tw
from twscanner.portfolio.trade_log import compute
from twscanner.services.today import build_today
from twscanner.ui.actions import analyze_holdings, execute_scan
from twscanner.ui.components.blocks import (
    action_badge,
    buy_form,
    callout,
    conclusion,
    empty,
    kpi_row,
    plan_card,
    signed_value,
)
from twscanner.ui.components.recovery import render_recovery
from twscanner.ui.format import dir_color, fmt_money, fmt_pct, fmt_r, stock_label
from twscanner.ui.settings import build_cfg
from twscanner.ui.state import get_market_state_cached, get_recovery_cached, get_sector_map, get_trades_df

SHOW_PLANS = 3        # 候選交易計畫先顯示幾張，其餘收合
DUP_WARNINGS = ("全部打到停損會賠", "同時持有")     # 這兩種已經在結論句與數字卡說過


def _market_state():
    res = st.session_state.get("result")
    if res and res.get("market_state"):
        return res["market_state"]
    try:
        return get_market_state_cached()
    except Exception:
        return None


def _goal_section(t):
    """右欄只放進度與一句話；推算細節（含達標需要的本金）收在「怎麼算」。"""
    prog, plan, target = t["progress"], t["plan"], t["target"]
    st.markdown("### 本月目標")
    pct = max(0.0, min(100.0, prog["pct"] or 0.0)) if prog["realized"] > 0 else 0.0
    color = dir_color(prog["realized"])
    st.markdown(
        f"<div class='goal'><div class='goal-num'><span style='color:{color}'>{fmt_money(prog['realized'], signed=True)}</span>"
        f"<span class='of'> / {fmt_money(target)}</span></div>"
        f"<div class='goalbar'><div style='width:{pct:.0f}%;background:{color}'></div></div>"
        f"<div class='goal-status'>{html.escape(prog['status'])}</div></div>", unsafe_allow_html=True)
    with st.expander("怎麼算：要做幾筆、需要多少本金"):
        lines = [plan["verdict"]]
        sim = plan.get("sim")
        if sim:
            lines.append(f"用這組統計模擬一萬個月：平均每月 {fmt_money(sim['mean'], signed=True)}，"
                         f"{sim['p_loss'] * 100:.0f}% 的月份會虧損，{sim['p_hit'] * 100:.0f}% 的月份達標。"
                         "所以用近 3 個月平均來看目標。")
        lines.append(f"每筆最多賠 {fmt_money(plan['risk_amount'])}；本月虧損上限 {fmt_money(plan['loss_limit'])}"
                     f"（{plan['loss_limit_r']:.0f}R）。")
        need = plan.get("required_annual_pct")
        if need is not None:
            lines.append(f"本金 {fmt_money(t['capital'])} 每月賺 {fmt_money(target)}，等於年報酬 {need:.0f}%。")
        st.markdown("\n".join(f"- {x}" for x in lines))
        caps = " · ".join(f"年化 {r * 100:.0f}% → {fmt_money(capital_for_target(target, r))}" for r in (0.06, 0.08, 0.10))
        st.caption(f"平均每月賺 {fmt_money(target)} 需要的本金：{caps}。台股過去十年大盤年化約 17%（大多頭），"
                   "長期規劃用 6–10% 比較穩妥；依據見「策略驗證 → 大樣本實證」。")
        if t["stats"]:
            s = t["stats"]
            st.caption(f"統計來源：{s['source']} {s['n']} 筆 · 勝率 {s['win_rate'] * 100:.0f}% · "
                       f"平均賺 {s['avg_win_r']:.2f}R · 期望值 {s['expectancy_r']:+.2f}R")


def render(sb):
    cfg = build_cfg()
    ms = _market_state()
    holdings_res = st.session_state.get("holdings_result")
    holdings_df = holdings_res["df"] if holdings_res else None
    trades = compute(get_trades_df(), cfg.get("costs"))
    scan_df = st.session_state["result"]["df"] if st.session_state.get("result") else None
    t = build_today(
        ms, scan_df, holdings_df, trades, cfg, today_tw().strftime("%Y-%m"),
        target=float(st.session_state.get("month_target", 10_000)),
        loss_limit_r=float(st.session_state.get("loss_limit_r", 2.0)),
        backtest=st.session_state.get("backtest_result"), sector_map=get_sector_map())

    tone = "stop" if not t["can_open"] else ("go" if any(c["signal"] == "進場" for c in t["candidates"])
                                             else "wait")
    sub = "；".join(r.rstrip("。") for r in t["reasons"]) + "。" if t["reasons"] else None
    conclusion(t["headline"], sub, tone)

    risk = t["risk"]
    prog = t["progress"]
    over = risk["risk_pct"] is not None and risk["risk_pct"] > risk["max_risk_pct"]
    risk_txt = f"{risk['risk_pct']:.1f}%" if risk["risk_pct"] is not None else "—"
    kpi_row([
        ("本月已實現", signed_value(prog["realized"], fmt_money(prog["realized"], signed=True)),
         f"目標 {fmt_money(t['target'])}"),
        ("近 3 個月平均", signed_value(prog["avg3"], fmt_money(prog["avg3"], signed=True)),
         f"以 {prog['months_in_avg']} 個月計"),
        ("全部打到停損會賠", f"<span class='warn'>{risk_txt}</span>" if over else risk_txt,
         (f"<span class='warn'>超過上限 {risk['max_risk_pct']:.0f}%</span> · " if over else f"上限 {risk['max_risk_pct']:.0f}% · ")
         + fmt_money(risk["total_risk"])),
        ("今天要處理", f"{len(t['urgent'])} 檔", f"持有 {risk['positions']} 檔"),
    ])
    for w in risk["warnings"]:
        if not w.startswith(DUP_WARNINGS):
            callout(w)

    main, side = st.columns([1.75, 1], gap="large")
    with main:
        if t["urgent"] or not t["can_open"]:      # 先賣後買；不能開新倉時候選本來就收合
            _holdings_section(t)
            _candidates_section(t, scan_df, sb)
        else:
            _candidates_section(t, scan_df, sb)
            _holdings_section(t)
    with side:
        if (ms or {}).get("regime") == "bear":
            with st.spinner("讀取止跌訊號…"):
                rec = get_recovery_cached()
            render_recovery(rec)
        _goal_section(t)


def _holdings_section(t):
    st.markdown("### 先處理持股")
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
        if st.session_state.get("holdings_analyzed_at"):
            st.caption(f"分析於 {st.session_state['holdings_analyzed_at']}")
        if st.button("重新分析持股", key="today_rehold"):
            analyze_holdings(hold_edit)
            st.rerun()


def _candidates_section(t, scan_df, sb):
    st.markdown("### 今日候選")
    if scan_df is None:
        empty("今天還沒掃描", "用「找標的」頁目前的範圍與策略掃描（全台股第一次約 5–15 分鐘，同一天再掃不到 1 分鐘）。"
              "要換範圍或策略，到「找標的」頁上方調整。")
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
        st.caption("依訊號與「距一年高點」排序。每張卡都是一份完整交易計畫：照計畫下單，不臨場改。")
        for p in t["candidates"][:SHOW_PLANS]:
            plan_card(p)
            buy_form(p, key=f"today_{p['code']}")
        more = t["candidates"][SHOW_PLANS:]
        if more:
            with st.expander(f"其他 {len(more)} 檔候選"):
                for p in more:
                    plan_card(p)
                    buy_form(p, key=f"today_{p['code']}")
