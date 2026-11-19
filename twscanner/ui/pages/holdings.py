"""持股與紀錄：今天哪幾檔要動（出場建議）→ 編輯持股 → 賣出後記錄 → 月損益與目標。"""
import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from twscanner.analysis.goal import month_progress
from twscanner.core.tz import today_tw
from twscanner.data.names import lookup_names
from twscanner.data.prices import fix_stock_code
from twscanner.portfolio import trade_log
from twscanner.storage import cloud as store
from twscanner.ui.actions import analyze_holdings
from twscanner.ui.components.blocks import asof, conclusion, empty, kpi_row, signed_value
from twscanner.ui.components.common import make_holdings_template
from twscanner.ui.format import clean_stock_col, colors, fmt_money, strip_icon
from twscanner.ui.glossary import HELP
from twscanner.ui.settings import build_cfg
from twscanner.ui.state import cloud_owner, get_base_config, get_code_name_map, get_trades_df, save_trades_df
from twscanner.ui.theme import CHART_CONFIG

HOLD_COLS = ["股票代號", "公司名稱", "成本價", "持有股數"]
URGENT_QTY = ("全出", "賣半")
EXIT_RULES = """
出場規則依序檢查，第一個成立的就是今天的建議：

1. **停損出清**：收盤跌破 MA20，而且跌破近 10 日最低點。
2. **技術轉弱**：KD 在高檔死亡交叉，而且收盤跌破 MA20。
3. **移動停利（ATR）**：有獲利時，收盤跌破「買進後最高價 − 3 × ATR」。
4. **+1R 賣一半**：獲利達到 1R（1R = 買進當時的 ATR × 1.5，也就是當初設定的停損距離）。
5. **+2R 以上**：趨勢仍強就續抱、交給移動停利保護；趨勢轉弱就全部了結。
6. **時間停損**：持有 10 個交易日還沒到 +1R，就出場換更好的機會。
7. **MA10 移動停利**：獲利超過 5% 後跌破 MA10。

表中的「停損價」是成本 − 1R 的參考線；沒填進場日時，以最近一次成交價觸及成本價的日子推估。
"""


def _normalize(df):
    df = df.copy()
    if "進場價" in df.columns and "成本價" not in df.columns:
        df = df.rename(columns={"進場價": "成本價"})
    if "持有張數" in df.columns and "持有股數" not in df.columns:
        df["持有股數"] = pd.to_numeric(df["持有張數"], errors="coerce") * 1000
    for c in HOLD_COLS:
        if c not in df.columns:
            df[c] = None
    # 代號一律文字（雲端 / Excel 來源可能是整數，會讓編輯表格崩潰）
    df["股票代號"] = df["股票代號"].map(lambda x: None if pd.isna(x) else str(x).strip().removesuffix(".0"))
    return df[HOLD_COLS]


def _bump():
    st.session_state["holdings_editor_version"] = st.session_state.get("holdings_editor_version", 0) + 1


def _ensure_holdings():
    if "holdings_df" not in st.session_state:
        st.session_state["holdings_df"] = pd.DataFrame(columns=HOLD_COLS).astype({"股票代號": str})
    norm = _normalize(st.session_state["holdings_df"])
    cur = st.session_state["holdings_df"]
    if list(norm.columns) != list(cur.columns) or not norm["股票代號"].equals(cur.get("股票代號")):
        st.session_state["holdings_df"] = norm
        _bump()
    st.session_state.setdefault("holdings_editor_version", 0)


def _totals(valid, result_df, etf_map):
    cost = float((pd.to_numeric(valid["成本價"], errors="coerce").fillna(0)
                  * pd.to_numeric(valid["持有股數"], errors="coerce").fillna(0)).sum()) if len(valid) else 0.0
    value = None
    if result_df is not None and len(result_df):
        px = {str(r["股票"]).split(".")[0]: r.get("目前價") for _, r in result_df.iterrows()}
        value = 0.0
        for _, row in valid.iterrows():
            code = fix_stock_code(row["股票代號"], etf_map)
            p, sh = px.get(code), row.get("持有股數")
            if p is not None and pd.notna(p) and sh is not None and pd.notna(sh):
                value += float(p) * float(sh)
    return cost, value


def _results(h_df):
    qty = h_df.get("賣出量", pd.Series(dtype=str)).astype(str)
    n_sell, n_half = int((qty == "全出").sum()), int((qty == "賣半").sum())
    n_keep = len(h_df) - n_sell - n_half
    if n_sell or n_half:
        conclusion(f"今天：{n_sell} 檔要賣、{n_half} 檔減半、{n_keep} 檔續抱",
                   "需要處理的排在表格最上面。照規則執行，不要因為捨不得而拖延。", "stop")
    else:
        conclusion(f"今天：{n_keep} 檔都續抱", "沒有觸發出場條件。收盤後再看一次即可。", "info")

    d = h_df.copy()
    d["_urgent"] = d.get("賣出量", pd.Series("", index=d.index)).isin(URGENT_QTY)
    d = d.sort_values(["_urgent", "報酬%"], ascending=[False, True]).reset_index(drop=True)
    d["操作建議"] = d["操作建議"].map(strip_icon)
    view = clean_stock_col(d)
    cols = ["股票", "操作建議", "賣出量", "報酬%", "R倍數", "目前價", "成本價", "停損價",
            "目標1(+1R半倉)", "目標2(+2R出清)", "移動停利(ATR)", "持有天數", "說明", "進場日來源"]
    view = view[[c for c in cols if c in view.columns]]
    c = colors()

    def row_style(r):
        urgent = r.get("賣出量") in URGENT_QTY
        return [f"background-color:{c['caution_bg']}" if urgent and col in ("股票", "操作建議", "賣出量")
                else "" for col in r.index]

    def signed(v):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return ""
        return f"color:{c['up'] if f > 0 else c['down']}" if f else ""
    sty = view.style.apply(row_style, axis=1).map(signed, subset=[x for x in ("報酬%", "R倍數") if x in view])
    fmt = {k: st.column_config.NumberColumn(k, format="%.2f") for k in
           ("目前價", "成本價", "停損價", "目標1(+1R半倉)", "目標2(+2R出清)", "移動停利(ATR)")}
    fmt["報酬%"] = st.column_config.NumberColumn("報酬%", format="%+.2f%%", help=HELP["profit_pct"])
    fmt["R倍數"] = st.column_config.NumberColumn("R 倍數", format="%+.2fR")
    fmt["持有天數"] = st.column_config.NumberColumn("持有天數", format="%d 天")
    fmt["股票"] = st.column_config.TextColumn("股票", pinned=True)
    ev = st.dataframe(sty, hide_index=True, use_container_width=True, column_config=fmt,
                      height=min(36 * (len(view) + 1) + 4, 480),
                      on_select="rerun", selection_mode="single-row", key="hold_table")
    st.caption("點一列可以記錄賣出。")
    with st.expander("出場規則怎麼判斷", expanded=False):
        st.markdown(EXIT_RULES)
    rows = ev.selection.rows if ev and ev.selection else []
    if rows:
        _sell_form(d.iloc[rows[0]])


def _sell_form(r):
    code = str(r["股票"]).split(".")[0]
    st.markdown(f"#### 記錄賣出：{code} {r.get('公司名稱', '')}")
    held = int(r.get("持有股數") or 0)
    default = max(1, held // 2 if r.get("賣出量") == "賣半" else held)
    c1, c2, c3, c4 = st.columns(4)
    px = c1.number_input("賣出價", value=float(r.get("目前價") or 0), step=0.5, key=f"sell_px_{code}")
    sh = c2.number_input("股數", value=int(default), min_value=1, max_value=max(held, 1),
                         step=1000 if held >= 1000 else 1, key=f"sell_sh_{code}")
    day = c3.date_input("賣出日", value=today_tw(), key=f"sell_day_{code}")
    c4.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    if c4.button("記入交易紀錄", type="primary", key=f"sell_btn_{code}", use_container_width=True):
        rec = {"賣出日": day.isoformat(), "股票代號": code, "公司名稱": r.get("公司名稱"),
               "買進日": r.get("進場日"), "買進價": float(r.get("成本價") or 0), "賣出價": float(px),
               "股數": int(sh), "停損價": r.get("停損價"), "備註": r.get("操作建議")}
        save_trades_df(pd.concat([get_trades_df(), pd.DataFrame([rec])], ignore_index=True))
        h = st.session_state["holdings_df"].copy()
        mask = h["股票代號"].astype(str) == code
        left = held - int(sh)
        if left > 0:
            h.loc[mask, "持有股數"] = left
        else:
            h = h[~mask]
        st.session_state["holdings_df"] = h.reset_index(drop=True)
        st.session_state.pop("holdings_result", None)
        _bump()
        st.toast(f"已記錄：賣出 {code} {int(sh):,} 股 @ {px:,.2f}")
        st.rerun()


def _toolbar():
    t2, t3 = st.columns(2)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        st.session_state["holdings_df"].to_excel(w, sheet_name="持股", index=False)
    t2.download_button("匯出持股", data=buf.getvalue(), file_name="my_holdings.xlsx", use_container_width=True,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with t3.popover("匯入 / 範本 / 清空", use_container_width=True):
        st.download_button("下載空白範本", data=make_holdings_template(), file_name="持股_模板.xlsx",
                           use_container_width=True,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if st.button("清空全部持股", use_container_width=True):
            st.session_state["holdings_df"] = pd.DataFrame(columns=HOLD_COLS).astype({"股票代號": str})
            st.session_state.pop("holdings_result", None)
            _bump()
            st.rerun()
        st.caption("上傳 xlsx（會取代目前持股）")
        up = st.file_uploader("上傳 xlsx 覆蓋", type=["xlsx"], key="holdings_uploader",
                              label_visibility="collapsed")
        if up:
            try:
                # 代號一律當文字讀：Excel 的 2330 預設是數字，會讓編輯表格拒絕顯示而整頁崩潰
                st.session_state["holdings_df"] = _normalize(pd.read_excel(up, dtype={"股票代號": str}))
                _bump()
                st.success(f"已載入 {len(st.session_state['holdings_df'])} 筆")
            except Exception as e:
                st.error(f"讀取失敗：{e}")


def _editor(etf_map):
    @st.fragment
    def frag():
        edited = st.data_editor(
            st.session_state["holdings_df"], num_rows="dynamic", use_container_width=True,
            key=f"holdings_editor_v{st.session_state['holdings_editor_version']}",
            column_config={
                "股票代號": st.column_config.TextColumn("股票代號", required=True, width="small", help="例：2330"),
                "公司名稱": st.column_config.TextColumn("公司名稱", width="medium", help="留空後按「查詢名稱」自動帶入"),
                "成本價": st.column_config.NumberColumn("成本價", min_value=0.0, step=0.01, format="%.2f",
                                                     help=HELP["cost_price"]),
                "持有股數": st.column_config.NumberColumn("持有股數", min_value=0, step=1000, format="%d",
                                                       help=HELP["shares_held"]),
            })
        st.session_state["_holdings_edited"] = edited
        pending = []
        for _, r in edited.iterrows():
            raw, name = r.get("股票代號"), r.get("公司名稱")
            if raw and pd.notna(raw) and (name is None or pd.isna(name) or not str(name).strip()):
                code = fix_stock_code(raw, etf_map)
                if code:
                    pending.append(code)
        if pending and st.button(f"查詢名稱（{len(pending)} 檔）"):
            found = lookup_names(pending, get_code_name_map())
            new = edited.copy()
            for i, r in new.iterrows():
                code = fix_stock_code(r.get("股票代號"), etf_map) if pd.notna(r.get("股票代號")) else None
                name = r.get("公司名稱")
                if code in found and (name is None or pd.isna(name) or not str(name).strip()):
                    new.at[i, "公司名稱"] = found[code]
            st.session_state["holdings_df"] = new
            _bump()
            st.rerun(scope="fragment")
    frag()
    edited = st.session_state.get("_holdings_edited", st.session_state["holdings_df"])
    st.session_state["holdings_df"] = edited
    if cloud_owner():
        try:
            sig = edited.to_json()
            if st.session_state.get("_hold_sig") != sig and store.save_holdings(cloud_owner(), edited):
                st.session_state["_hold_sig"] = sig
        except Exception:
            pass
    return edited


def _holdings_tab():
    etf_map = get_base_config().get("etf_fix_map", {})
    _ensure_holdings()
    hdf = st.session_state["holdings_df"]
    valid = hdf.dropna(subset=["股票代號"])
    valid = valid[valid["股票代號"].astype(str).str.strip() != ""]
    res = st.session_state.get("holdings_result")
    result_df = res["df"] if res else None

    if result_df is not None and len(result_df):
        _results(result_df)
        asof(f"分析時間 {st.session_state.get('holdings_analyzed_at', '')}")
    elif len(valid):
        conclusion(f"你有 {len(valid)} 檔持股，還沒分析", "按下方「分析持股」取得今天的出場建議。", "info")
    else:
        conclusion("目前沒有持股", "在下方表格輸入代號、成本與股數，或在交易計畫卡按「我已買進」。", "info")

    cost, value = _totals(valid, result_df, etf_map)
    pnl = value - cost if value is not None and cost else None
    kpi_row([
        ("持股", f"{len(valid)} 檔", None),
        ("總成本", fmt_money(cost) if cost else "—", None),
        ("總現值", fmt_money(value) if value else "—", "需先分析持股" if value is None else None),
        ("未實現損益", signed_value(pnl, fmt_money(pnl, signed=True)) if pnl is not None else "—",
         signed_value(pnl / cost * 100) if pnl is not None and cost else None),
    ])

    st.markdown("### 編輯持股")
    _toolbar()
    edited = _editor(etf_map)
    a1, a2 = st.columns([1.2, 4])
    if a1.button("分析持股", type="primary", use_container_width=True, disabled=len(valid) == 0):
        analyze_holdings(edited)
        st.rerun()
    a2.caption("抓最新收盤價並判斷出場建議。資料存在瀏覽器；登入雲端會自動保存，否則記得匯出備份。")


def _month_chart(summ, target):
    if summ.empty:
        return
    d = summ.sort_values("月份")
    c = colors()
    fig = go.Figure(go.Bar(
        x=d["月份"], y=d["已實現損益"], marker_color=[c["up"] if v >= 0 else c["down"] for v in d["已實現損益"]],
        marker_line_width=0, text=[fmt_money(v, signed=True) for v in d["已實現損益"]], textposition="outside",
        hovertemplate="%{x}：%{y:,.0f} 元<extra></extra>"))
    fig.add_hline(y=target, line=dict(color="#94A3B8", width=1, dash="dot"),
                  annotation_text=f"月目標 {target:,.0f}", annotation_position="top left")
    fig.add_hline(y=0, line=dict(color="#CBD5E1", width=1))
    fig.update_xaxes(type="category")      # 「2026-11」是月份標籤，不要被當成日期
    fig.update_layout(height=280, margin=dict(l=8, r=8, t=24, b=8), plot_bgcolor="#FFFFFF",
                      paper_bgcolor="#FFFFFF", showlegend=False, yaxis=dict(visible=False),
                      font=dict(family="Inter, Noto Sans TC, sans-serif", size=12))
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


def _trades_io(raw):
    """未登入雲端時紀錄只在這個瀏覽器分頁裡：提供匯出 / 匯入。"""
    if not cloud_owner():
        st.caption("目前沒有登入雲端空間：紀錄只存在這個瀏覽器分頁，重新整理就會消失。"
                   "請在側欄登入雲端，或用下方按鈕匯出備份。")
    c1, c2 = st.columns(2)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        raw.to_excel(w, sheet_name="交易紀錄", index=False)
    c1.download_button("匯出交易紀錄", data=buf.getvalue(), file_name="trades.xlsx", use_container_width=True,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with c2.popover("匯入交易紀錄", use_container_width=True):
        up = st.file_uploader("上傳 trades.xlsx（會取代目前紀錄）", type=["xlsx"], key="trades_uploader")
        if up and st.button("確認匯入", key="trades_import"):
            try:
                df = pd.read_excel(up, dtype={"股票代號": str})
                save_trades_df(df.reindex(columns=trade_log.COLUMNS))
                st.rerun()
            except Exception as e:
                st.error(f"讀取失敗：{e}")


def _trades_tab():
    cfg = build_cfg()
    target = float(st.session_state.get("month_target", 10_000))
    raw = get_trades_df()
    comp = trade_log.compute(raw, cfg.get("costs"))
    summ = trade_log.monthly_summary(comp)
    month = today_tw().strftime("%Y-%m")
    realized, r_sum, prev = trade_log.month_stats(comp, month)
    prog = month_progress(realized, r_sum, target, float(st.session_state.get("loss_limit_r", 2.0)), prev)
    conclusion(f"本月已實現 {fmt_money(realized, signed=True)}，目標 {fmt_money(target)}", prog["status"],
               "stop" if prog["stop_trading"] else "info")
    cur = summ[summ["月份"] == month]
    total = float(comp["損益(元)"].dropna().sum()) if len(comp) else 0.0
    kpi_row([
        ("本月已實現", signed_value(realized, fmt_money(realized, signed=True)), f"{r_sum:+.1f}R"),
        ("本月筆數", f"{int(cur['筆數'].iloc[0]) if len(cur) else 0} 筆",
         f"勝率 {cur['勝率%'].iloc[0]:.0f}%" if len(cur) else None),
        ("近 3 個月平均", signed_value(prog["avg3"], fmt_money(prog["avg3"], signed=True)),
         f"以 {prog['months_in_avg']} 個月計"),
        ("累計已實現", signed_value(total, fmt_money(total, signed=True)), f"{len(comp)} 筆"),
    ])
    st.markdown("### 每月已實現損益")
    if summ.empty:
        empty("還沒有交易紀錄", "在「持股」點一列記入賣出，或直接在下表新增一列。")
    else:
        _month_chart(summ, target)

    st.markdown("### 交易紀錄")
    st.caption("每一筆賣出記一列。填了停損價才算得出 R 倍數（統計勝率與期望值會用到）。手續費與證交稅自動扣除。")
    _trades_io(raw)
    edited = st.data_editor(
        raw, num_rows="dynamic", use_container_width=True, key="trades_editor", hide_index=True,
        column_config={
            "賣出日": st.column_config.TextColumn("賣出日", help="YYYY-MM-DD"),
            "買進日": st.column_config.TextColumn("買進日", help="YYYY-MM-DD，可空"),
            "股票代號": st.column_config.TextColumn("股票代號", required=True),
            "買進價": st.column_config.NumberColumn("買進價", format="%.2f"),
            "賣出價": st.column_config.NumberColumn("賣出價", format="%.2f"),
            "股數": st.column_config.NumberColumn("股數", format="%d", step=1000),
            "停損價": st.column_config.NumberColumn("停損價", format="%.2f"),
        })
    if not edited.equals(raw):
        save_trades_df(edited)
        st.rerun()
    if len(comp):
        show = comp[["賣出日", "股票代號", "公司名稱", "損益(元)", "報酬%", "R倍數", "持有天數"]].copy()
        c = colors()

        def signed(v):
            try:
                f = float(v)
            except (TypeError, ValueError):
                return ""
            return f"color:{c['up'] if f > 0 else c['down']}" if f == f and f else ""
        st.dataframe(show.style.map(signed, subset=["損益(元)", "報酬%", "R倍數"]), hide_index=True,
                     use_container_width=True, column_config={
                         "損益(元)": st.column_config.NumberColumn("損益（元，已扣成本）", format="localized"),
                         "報酬%": st.column_config.NumberColumn(format="%+.2f%%"),
                         "R倍數": st.column_config.NumberColumn("R 倍數", format="%+.2fR"),
                         "持有天數": st.column_config.NumberColumn(format="%d 天")})
    costs = cfg["costs"]
    st.caption(f"成本：手續費 {costs['fee_rate'] * 100:.4f}%（折扣 {costs['fee_discount']}，最低 20 元）"
               f" + 證交稅 {costs['tax_rate'] * 100:.1f}%，未滿 1 元不計。")


def render():
    t_hold, t_trades = st.tabs(["持股", "交易紀錄與月損益"])
    with t_hold:
        _holdings_tab()
    with t_trades:
        _trades_tab()
