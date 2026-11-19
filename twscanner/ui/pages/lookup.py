"""🔎 個股快速查詢分頁。"""

import pandas as pd
import streamlit as st

from twscanner.services import run_single_lookup
from twscanner.ui.settings import build_cfg
from twscanner.ui.state import get_code_name_map


def render():
    """🔎 個股快速查詢"""
    st.markdown("### 🔎 個股快速查詢")
    st.caption("輸入代號（可選填成本）→ 立即拿到現價/R/趨勢強度/出場建議＋籌碼/營收/RS，免跑全市場掃描。")

    q1, q2, q3, q4 = st.columns([1.2, 1, 1, 1])
    q_code = q1.text_input("股票代號", key="lookup_code", placeholder="如 1608")
    q_cost = q2.number_input("成本價（可選）", min_value=0.0, value=0.0, step=0.01,
                             key="lookup_cost", help="填了才會給『出場建議』；0=只看技術/籌碼快照")
    q_date = q3.date_input("進場日（可選）", value=None, key="lookup_date",
                           help="影響持有天數/波段高基準；不填用全段")
    q_big = q4.checkbox("含大資金", value=False, key="lookup_big",
                        help="多抓外資期貨/台幣/融資（較慢）")
    look_btn = st.button("🔎 查詢", type="primary", key="lookup_btn")

    if look_btn:
        if not q_code.strip():
            st.warning("請輸入股票代號")
        else:
            cfg = build_cfg()
            barL = st.progress(0.0, text="查詢中 …")

            def _lk_cb(p, msg):
                try:
                    barL.progress(min(p, 1.0), text=f"查詢：{msg}")
                except Exception:
                    pass
            try:
                try:
                    _nm = get_code_name_map().get(q_code.strip(), "")
                except Exception:
                    _nm = ""
                res = run_single_lookup(
                    q_code.strip(), cfg, company_name=_nm,
                    entry_price=(q_cost if q_cost > 0 else None),
                    entry_date=q_date, with_bigmoney=q_big, progress_cb=_lk_cb)
                st.session_state["lookup_result"] = res
            except Exception as e:
                st.session_state["lookup_result"] = {"error": str(e)}
            barL.progress(1.0, text="完成")

    res = st.session_state.get("lookup_result")
    if res:
        if res.get("error"):
            st.error(res["error"])
        else:
            sc = res["scoring"]
            hd = res.get("holding")
            st.markdown(f"#### {res['name']}　`{res['symbol']}`")

            # ---- 出場建議（有成本才顯示）----
            if hd:
                a1, a2, a3, a4 = st.columns(4)
                a1.metric("現價", hd.get("目前價"))
                a2.metric("報酬%", f"{hd.get('報酬%')}%" if hd.get("報酬%") is not None else "—")
                a3.metric("R 倍數", hd.get("R倍數"))
                a4.metric("趨勢強度", hd.get("趨勢強度", "—"))
                _act = str(hd.get("操作建議", ""))
                _cls = ("bull" if ("續抱" in _act or "強勢" in _act)
                        else ("bear" if ("停損" in _act or "了結" in _act or "轉弱" in _act)
                              else "neutral"))
                st.markdown(
                    f"<div class='hdr-advice {_cls}'><span class='dot'></span>"
                    f"<b>出場建議</b>　{_act}（{hd.get('賣出量','—')}）— {hd.get('說明','')}</div>",
                    unsafe_allow_html=True)
                e1, e2, e3, e4 = st.columns(4)
                e1.metric("停損價", hd.get("停損價"))
                e2.metric("目標2(+2R)", hd.get("目標2(+2R出清)"))
                e3.metric("移動停利ATR", hd.get("移動停利(ATR)"))
                e4.metric("ADX", hd.get("ADX"))
                if hd.get("主動警示") and hd["主動警示"] != "—":
                    st.warning(f"⚠ 主動警示：{hd['主動警示']}")
                st.divider()

            # ---- 技術 / 籌碼 / 基本面快照 ----
            st.markdown("**快照（買入視角）**")
            g1, g2, g3, g4 = st.columns(4)
            g1.metric("綜合評級", sc.get("綜合評級", "—"))
            g2.metric("評分", sc.get("評分顯示", sc.get("評分")))
            g3.metric("相對強度RS%", sc.get("相對強度RS%"))
            g4.metric("乖離MA20%", sc.get("乖離MA20%"))
            g5, g6, g7, g8 = st.columns(4)
            g5.metric("籌碼確認", sc.get("籌碼確認", "—"))
            g6.metric("法人5日(張)", sc.get("法人5日累計(張)"))
            g7.metric("營收動能", sc.get("營收動能", "—"))
            g8.metric("換手率%", sc.get("換手率%"))
            if sc.get("評級理由"):
                st.caption(f"評級理由：{sc['評級理由']}")

            with st.expander("更多欄位"):
                show = {k: sc.get(k) for k in [
                    "操作建議", "進場參考價", "停損價", "目標價1(+1R半倉)", "目標價2(+2R出清)",
                    "外資買賣超(張)", "法人買賣超(張)", "法人連買天數",
                    "月營收YoY%", "月營收MoM%", "融資券提示", "ADX",
                    "MA20", "MA60", "K", "D", "成交量", "20日均量"] if k in sc}
                st.dataframe(pd.DataFrame([show]).T.rename(columns={0: "值"}),
                             use_container_width=True)

            # ---- 近 5 日收盤 ----
            dfx = res.get("df")
            if dfx is not None and len(dfx):
                closes = [round(float(x), 2) for x in dfx["Close"].iloc[-5:]]
                st.caption("近 5 日收盤：" + " → ".join(str(c) for c in closes))

            # ---- ➕ 加碼檢查 ----
            with st.expander("➕ 加碼檢查（現價加碼是否合理）", expanded=False):
                from twscanner.analysis.sizing import evaluate_add
                cur_px = sc.get("目前現價") or sc.get("收盤價")
                add_lots = st.number_input("想加幾張", min_value=1, max_value=100,
                                           value=1, step=1, key="add_lots")
                ev = evaluate_add(
                    build_cfg(), cur_px, sc.get("ATR14"),
                    sc.get("乖離MA20%"), sc.get("相對強度RS%"), int(add_lots))
                _vc = ("bull" if ev["verdict"].startswith("🟢")
                       else ("bear" if ev["verdict"].startswith("🔴") else "neutral"))
                st.markdown(
                    f"<div class='hdr-advice {_vc}'><span class='dot'></span>"
                    f"<b>加碼判斷</b>　{ev['verdict']}</div>", unsafe_allow_html=True)
                if ev["blocks"]:
                    for b in ev["blocks"]:
                        st.error("✕ " + b)
                for w in ev["warns"]:
                    st.warning("⚠ " + w)
                ac1, ac2, ac3, ac4 = st.columns(4)
                ac1.metric("加碼停損", ev["stop"])
                ac2.metric("每股風險", ev["risk_per_share"])
                ac3.metric("加碼風險", f"{ev['add_risk']:,.0f}" if ev["add_risk"] is not None else "—")
                ac4.metric("佔資金%", f"{ev['cost_pct']}%" if ev["cost_pct"] is not None else "—")
                if ev.get("max_lots_in_budget") is not None:
                    st.caption(f"💡 此價在單筆風險預算內最多可加 **{ev['max_lots_in_budget']} 張**"
                               f"（停損 {ev['stop']}，每股風險 {ev['risk_per_share']}）")
                st.caption("加碼鐵律：過度延伸別追高；加碼量 ≤ 原倉、加後上移整體停損、總風險守單筆上限。")

            st.caption("⚠ 決策輔助、非投資建議；籌碼/營收為當日 best-effort 資料。")
