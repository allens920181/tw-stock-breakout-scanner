# -*- coding: utf-8 -*-
"""
「💰 資金流向」分頁的 Streamlit 視覺化。資料/計算都在 twscanner/market/flows.py。

Streamlit 每次互動都會重跑所有分頁 → 重的抓取全部包在 st.cache_data，
且第一次需使用者按鈕才開始載入（台股歷史首次約 1~2 分鐘）。
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from twscanner.market import flows as F

# 與 app.py 一致的色票
_POS, _NEG, _MUTED, _GRID, _TEXT = "#059669", "#DC2626", "#94A3B8", "#F1F5F9", "#0F172A"
# 類別色（依固定順序，不輪替）：外資 / 投信 / 自營商 / 第 4 條線
_CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
_QUAD_COLOR = {"leading": "#059669", "improving": "#2a78d6",
               "weakening": "#D97706", "lagging": "#DC2626"}
_CFG = {"displayModeBar": False}


def _layout(fig, height=360, **kw):
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=36, b=8),
        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
        font=dict(family="Inter, sans-serif", size=11, color=_TEXT),
        hoverlabel=dict(font_size=12), **kw)
    fig.update_xaxes(showgrid=True, gridcolor=_GRID, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=_GRID, zeroline=False)
    return fig


def _tbl_h(n):
    """讓表格完整顯示所有列（不出現內捲軸）。"""
    return 38 + 35 * max(int(n), 1)


def _plot(fig):
    st.plotly_chart(fig, use_container_width=True, config=_CFG)


# ---------------------------------------------------------------
# 快取包裝
# ---------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def _load_us(cache_dir):
    px = F.fetch_prices(cache_dir)
    if not px:
        return None
    ratio_series, ratio_stats = F.risk_ratio_series(px)
    link = F.tw_us_linkage(px)
    return {
        "sectors": F.flow_table(px, F.US_SECTORS),
        "cross": F.flow_table(px, F.CROSS_ASSETS),
        "rrg_sec": F.rrg_tails(px, F.US_SECTORS),
        "rrg_cross": F.rrg_tails(px, {k: v for k, v in F.CROSS_ASSETS.items() if k != F.US_BENCH}),
        "ratio_series": ratio_series, "ratio_stats": ratio_stats,
        "link": link,
        "asof": px["Close"].index[-1] if "Close" in px and len(px["Close"]) else None,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def _load_tw(cache_dir, days):
    tw = F.fetch_tw_flows(cache_dir, days=days)
    return {
        "tw": tw,
        "share": F.sector_share_shift(tw.get("sector_values")),
        "inst_sec": F.fetch_tw_sector_inst(tw, cache_dir),
    }


# ---------------------------------------------------------------
# 美股
# ---------------------------------------------------------------
def _rrg_chart(tails, table, title):
    fig = go.Figure()
    allx, ally = [100], [100]
    for sym, df in tails.items():
        allx += list(df["ratio"])
        ally += list(df["mom"])
    pad = 0.6
    x0, x1 = min(allx) - pad, max(allx) + pad
    y0, y1 = min(ally) - pad, max(ally) + pad
    # 四象限底色 + 角落標籤
    quads = [("leading", 100, x1, 100, y1, "領先：資金流入中", "right", "top"),
             ("weakening", 100, x1, y0, 100, "轉弱：開始流出", "right", "bottom"),
             ("lagging", x0, 100, y0, 100, "落後：資金流出", "left", "bottom"),
             ("improving", x0, 100, 100, y1, "改善：開始流入", "left", "top")]
    for q, xa, xb, ya, yb, lab, xan, yan in quads:
        fig.add_shape(type="rect", x0=xa, x1=xb, y0=ya, y1=yb, layer="below",
                      line_width=0, fillcolor=_QUAD_COLOR[q], opacity=0.06)
        fig.add_annotation(x=xb if xan == "right" else xa, y=yb if yan == "top" else ya,
                           text=lab, showarrow=False, xanchor=xan, yanchor=yan,
                           font=dict(size=11, color=_QUAD_COLOR[q]))
    fig.add_hline(y=100, line=dict(color=_MUTED, width=1))
    fig.add_vline(x=100, line=dict(color=_MUTED, width=1))

    names = dict(zip(table["代號"], table["名稱"])) if not table.empty else {}
    for sym, df in tails.items():
        q = F.quadrant(df["ratio"].iloc[-1], df["mom"].iloc[-1])
        color = _QUAD_COLOR.get(q, _MUTED)
        nm = names.get(sym, sym)
        fig.add_trace(go.Scatter(
            x=df["ratio"], y=df["mom"], mode="lines",
            line=dict(color=color, width=1.5), opacity=0.45,
            hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(
            x=[df["ratio"].iloc[-1]], y=[df["mom"].iloc[-1]], mode="markers+text",
            marker=dict(size=11, color=color, line=dict(color="#FFFFFF", width=2)),
            text=[nm], textposition="top center", textfont=dict(size=11, color=_TEXT),
            showlegend=False,
            hovertemplate=(f"<b>{nm}</b> ({sym})<br>RS-Ratio %{{x:.2f}}<br>"
                           f"RS-Momentum %{{y:.2f}}<br>{F.QUADRANT.get(q, ('', ''))[1]}<extra></extra>")))
    _layout(fig, 480, title=dict(text=title, font=dict(size=13)))
    fig.update_xaxes(title="相對強弱 RS-Ratio（>100 比大盤強）", range=[x0, x1])
    fig.update_yaxes(title="相對動能 RS-Momentum（>100 正在變強）", range=[y0, y1])
    return fig


def _fmt_flow_table(df):
    if df is None or df.empty:
        return df
    show = df.copy()
    show["象限"] = show.get("象限", pd.Series(dtype=object)).map(
        lambda q: F.QUADRANT[q][0] if q in F.QUADRANT else "—")
    cols = ["名稱", "代號", "資金訊號", "象限", "5日%", "20日%", "60日%",
            "相對大盤20日pp", "CMF20", "成交額放大"]
    return show[[c for c in cols if c in show.columns]]


_FLOW_COLCFG = {
    "5日%": st.column_config.NumberColumn(format="%+.1f%%"),
    "20日%": st.column_config.NumberColumn(format="%+.1f%%"),
    "60日%": st.column_config.NumberColumn(format="%+.1f%%"),
    "相對大盤20日pp": st.column_config.NumberColumn("相對大盤20日", format="%+.1f pp"),
    "CMF20": st.column_config.NumberColumn(
        format="%+.2f", help="Chaikin 資金流：>0 收盤偏高檔且有量＝買盤主導；<0 賣盤主導"),
    "成交額放大": st.column_config.NumberColumn(
        format="%.2fx", help="近 5 日均成交金額 ÷ 近 60 日均；>1.3 代表資金湧入/湧出特別多"),
}


def _risk_ratio_chart(series):
    fig = go.Figure()
    for i, (name, s) in enumerate(series.items()):
        c = _CAT[i % len(_CAT)]
        fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", name=name,
                                 line=dict(color=c, width=2),
                                 hovertemplate=f"{name}：%{{y:.1f}}<extra></extra>"))
        fig.add_annotation(x=s.index[-1], y=float(s.iloc[-1]), text=name, showarrow=False,
                           xanchor="left", xshift=6, font=dict(size=11, color=_TEXT))
    fig.add_hline(y=100, line=dict(color=_MUTED, width=1, dash="dot"))
    if series:
        s0 = next(iter(series.values()))
        fig.update_xaxes(range=[s0.index[0], s0.index[-1]])
    _layout(fig, 340, hovermode="x unified",
            legend=dict(orientation="h", y=1.08, x=0),
            title=dict(text="風險偏好比值（近 120 日，期初=100）", font=dict(size=13)))
    fig.update_layout(margin=dict(l=8, r=90, t=56, b=8))
    return fig


def _render_us(us):
    if not us:
        st.info("美股資料暫時抓不到（Yahoo 可能限流），稍後按「重新整理」再試。")
        return
    st.markdown("### 類股輪動圖（RRG）— 美國資金正從哪裡移到哪裡")
    st.caption("每個點是一個類股 ETF 相對 S&P500 的位置，淡線是近 10 個交易日的軌跡（每 2 日一點）。"
               "正常輪動方向為 **順時針**：改善 → 領先 → 轉弱 → 落後。")
    view = st.radio("觀察範圍", ["美股類股", "跨資產（股/債/金/美元/幣）"], horizontal=True,
                    key="flows_rrg_view", label_visibility="collapsed")
    if view == "美股類股":
        _plot(_rrg_chart(us["rrg_sec"], us["sectors"], "美股 12 類股 vs S&P500"))
        tbl = us["sectors"]
    else:
        _plot(_rrg_chart(us["rrg_cross"], us["cross"], "跨資產 vs S&P500"))
        tbl = us["cross"]
    st.dataframe(_fmt_flow_table(tbl), hide_index=True, use_container_width=True,
                 column_config=_FLOW_COLCFG, height=_tbl_h(len(tbl)))

    st.markdown("### 風險胃口 — 美國投資人在進攻還是防守")
    lab, up, down = F.risk_appetite_label(us["ratio_stats"])
    st.markdown(f"**{lab}**　（{up} 項向上 / {down} 項向下）")
    if us["ratio_series"]:
        _plot(_risk_ratio_chart(us["ratio_series"]))
    if not us["ratio_stats"].empty:
        rs = us["ratio_stats"].copy()
        rs["站上50日線"] = rs["站上50日線"].map({True: "✅ 是", False: "❌ 否"})
        st.dataframe(rs, hide_index=True, use_container_width=True, column_config={
            "20日變化%": st.column_config.NumberColumn(format="%+.1f%%")})


# ---------------------------------------------------------------
# 台股
# ---------------------------------------------------------------
def _inst_daily_chart(inst):
    fig = go.Figure()
    x = inst.index.strftime("%m/%d")
    for i, col in enumerate(["外資", "投信", "自營商"]):
        fig.add_trace(go.Bar(x=x, y=inst[col], name=col, marker_color=_CAT[i],
                             marker_line_width=0,
                             hovertemplate=f"{col}：%{{y:+,.0f}} 億<extra></extra>"))
    _layout(fig, 320, barmode="group", bargap=0.25, bargroupgap=0.08,
            hovermode="x unified", legend=dict(orientation="h", y=1.1, x=0),
            title=dict(text="三大法人每日買賣超（億元）", font=dict(size=13)))
    fig.update_layout(margin=dict(l=8, r=8, t=56, b=8))
    fig.add_hline(y=0, line=dict(color=_MUTED, width=1))
    return fig


def _inst_cum_chart(inst):
    cum = inst.cumsum()
    fig = go.Figure()
    x = cum.index.strftime("%m/%d")
    for i, col in enumerate(["外資", "投信", "自營商"]):
        fig.add_trace(go.Scatter(x=x, y=cum[col], name=col, mode="lines+markers",
                                 line=dict(color=_CAT[i], width=2), marker=dict(size=5),
                                 hovertemplate=f"{col} 累計：%{{y:+,.0f}} 億<extra></extra>"))
        fig.add_annotation(x=x[-1], y=float(cum[col].iloc[-1]), text=f"{col} {cum[col].iloc[-1]:+,.0f}",
                           showarrow=False, xanchor="left", xshift=8, font=dict(size=11, color=_TEXT))
    fig.add_hline(y=0, line=dict(color=_MUTED, width=1))
    _layout(fig, 300, hovermode="x unified", showlegend=False,
            title=dict(text=f"近 {len(inst)} 日累計買賣超（億元）— 斜率＝佈局方向", font=dict(size=13)))
    fig.update_layout(margin=dict(l=8, r=110, t=40, b=8))
    return fig


def _diverging_hbar(s, title, unit, hover_extra=None, n=8):
    """依值排序的水平長條（正綠負紅），只取前 n / 後 n。"""
    s = s.dropna().sort_values()
    if len(s) > 2 * n:
        s = pd.concat([s.head(n), s.tail(n)])
    colors = [_POS if v >= 0 else _NEG for v in s.values]
    custom = hover_extra.reindex(s.index).values if hover_extra is not None else None
    fig = go.Figure(go.Bar(
        x=s.values, y=s.index, orientation="h", marker_color=colors, marker_line_width=0,
        text=[f"{v:+.1f}" for v in s.values], textposition="auto",
        insidetextanchor="end", textfont=dict(size=10), cliponaxis=False,
        customdata=custom,
        hovertemplate=("<b>%{y}</b><br>%{x:+.2f} " + unit +
                       ("<br>%{customdata}" if custom is not None else "") + "<extra></extra>")))
    fig.add_vline(x=0, line=dict(color=_MUTED, width=1))
    _layout(fig, max(300, 24 * len(s) + 60), title=dict(text=title, font=dict(size=13)),
            showlegend=False, bargap=0.3)
    fig.update_xaxes(title=unit)
    fig.update_layout(margin=dict(l=8, r=40, t=40, b=8))
    return fig


def _render_tw(twd):
    tw, share, isec = twd["tw"], twd["share"], twd["inst_sec"]
    inst = tw.get("inst")
    if inst is None or inst.empty:
        st.info("TWSE 資料暫時抓不到（可能被限流），稍後按「重新整理」再試。")
        return
    st.markdown("### 三大法人 — 大資金是買還是賣")
    s5 = inst.tail(5).sum()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"外資 {inst.index[-1]:%m/%d}", f"{inst['外資'].iloc[-1]:+,.0f} 億")
    m2.metric("外資 近5日", f"{s5['外資']:+,.0f} 億")
    m3.metric("投信 近5日", f"{s5['投信']:+,.0f} 億")
    m4.metric("自營商 近5日", f"{s5['自營商']:+,.0f} 億")
    c1, c2 = st.columns(2)
    with c1:
        _plot(_inst_daily_chart(inst))
    with c2:
        _plot(_inst_cum_chart(inst))

    st.markdown("### 錢往哪個類股集中")
    c3, c4 = st.columns(2)
    with c3:
        if share is not None and not share.empty:
            extra = share.apply(lambda r: f"今日比重 {r['今日比重%']:.1f}%（平均 {r['平均比重%']:.1f}%）"
                                          f"<br>成交 {r['今日金額億']:,.0f} 億", axis=1)
            _plot(_diverging_hbar(share["比重變化pp"], "類股成交比重變化（今日 vs 近 20 日平均）",
                                  "pp", extra))
            st.caption("成交比重上升＝市場的錢正往這個類股移動（不分買賣，看的是『熱度』）。")
        else:
            st.info("類股成交值暫無資料")
    with c4:
        if isec is not None and not isec.empty:
            extra = isec.apply(lambda r: f"外資 {r['外資']:+.1f} 億 · 投信 {r['投信']:+.1f} 億", axis=1)
            nd = len(tw.get("t86") or [])
            _plot(_diverging_hbar(isec["合計"], f"外資＋投信 依產業買賣超（近 {nd} 日，億）",
                                  "億元", extra))
            st.caption("方向性：法人實際把錢『買進』或『賣出』哪些族群（股數×最新收盤估算，僅上市）。")
        else:
            st.info("法人產業別資料暫無")
    if isec is not None and not isec.empty:
        with st.expander("法人產業別明細"):
            st.dataframe(isec, use_container_width=True, column_config={
                c: st.column_config.NumberColumn(format="%+.1f 億") for c in isec.columns})


# ---------------------------------------------------------------
# 台美連動
# ---------------------------------------------------------------
def _lead_lag_scatter(r, name):
    df = r["df"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["us_ret"], y=df["tw_ret"], mode="markers",
        marker=dict(size=8, color=_CAT[0], opacity=0.6, line=dict(color="#FFFFFF", width=1)),
        customdata=df.index.strftime("%Y-%m-%d"),
        hovertemplate=(f"%{{customdata}}<br>前一晚{name} %{{x:+.2f}}%<br>"
                       "台股當日 %{y:+.2f}%<extra></extra>")))
    if r.get("beta") is not None and len(df) > 2:
        xs = np.linspace(df["us_ret"].min(), df["us_ret"].max(), 20)
        a = df["tw_ret"].mean() - r["beta"] * df["us_ret"].mean()
        fig.add_trace(go.Scatter(x=xs, y=a + r["beta"] * xs, mode="lines",
                                 line=dict(color=_TEXT, width=1.5, dash="dash"),
                                 hoverinfo="skip"))
    fig.add_hline(y=0, line=dict(color=_MUTED, width=1))
    fig.add_vline(x=0, line=dict(color=_MUTED, width=1))
    _layout(fig, 340, showlegend=False,
            title=dict(text=f"前一晚{name} vs 台股隔日（近 {r['n']} 日）", font=dict(size=13)))
    fig.update_xaxes(title=f"前一晚{name}漲跌 %")
    fig.update_yaxes(title="台股加權指數漲跌 %")
    return fig


def _adr_chart(adr):
    s = adr.tail(250)
    ma5 = s.rolling(5).mean()
    avg = s.rolling(60).mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", name="每日",
                             line=dict(color=_CAT[0], width=1), opacity=0.25,
                             hovertemplate="每日 %{y:+.1f}%<extra></extra>"))
    fig.add_trace(go.Scatter(x=ma5.index, y=ma5.values, mode="lines", name="5 日平均",
                             line=dict(color=_CAT[0], width=2),
                             hovertemplate="5日平均 %{y:+.1f}%<extra></extra>"))
    fig.add_trace(go.Scatter(x=avg.index, y=avg.values, mode="lines", name="60 日平均",
                             line=dict(color=_TEXT, width=1.5, dash="dot"),
                             hovertemplate="60日平均 %{y:+.1f}%<extra></extra>"))
    _layout(fig, 340, hovermode="x unified", legend=dict(orientation="h", y=1.1, x=0),
            title=dict(text="台積電 ADR 溢價 %（美國投資人願意多付多少）", font=dict(size=13)))
    fig.update_layout(margin=dict(l=8, r=8, t=56, b=8))
    return fig


def _render_link(us):
    if not us:
        st.info("美股資料暫時抓不到")
        return
    link = us["link"]
    sox, spx = link.get("sox") or {}, link.get("spx") or {}
    st.markdown("### 台股真的跟著美股走嗎？— 用資料回答")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("與前晚費半 相關係數", f"{sox['corr']:.2f}" if sox.get("corr") is not None else "—")
    k2.metric("與前晚費半 同向率", f"{sox['same_dir']:.0f}%" if sox.get("same_dir") is not None else "—")
    k3.metric("與前晚S&P500 相關係數", f"{spx['corr']:.2f}" if spx.get("corr") is not None else "—")
    k4.metric("與前晚S&P500 同向率", f"{spx['same_dir']:.0f}%" if spx.get("same_dir") is not None else "—")
    st.caption("相關係數：1＝完全同步、0＝無關。同向率：美股漲（跌）隔天台股也漲（跌）的比例，"
               "50% 等於丟銅板。台股權值以半導體為主，因此通常跟 **費城半導體** 比跟 S&P500 更同步。")
    c1, c2 = st.columns(2)
    with c1:
        if sox.get("n", 0) >= 20:
            _plot(_lead_lag_scatter(sox, "費半"))
    with c2:
        adr = link.get("adr")
        if adr is not None and len(adr) > 60:
            _plot(_adr_chart(adr))
            st.caption("ADR 溢價高於平常＝美國資金搶著買台灣科技股（偏多）；"
                       "溢價快速收斂＝美國熱度退潮，外資常同步在台股賣超。")


_GUIDE = """
**這頁在回答三個問題**

1. **美國的錢在進攻還是防守？** → 看「風險胃口」。攻擊/防禦、高收益債/公債 同時上升＝Risk-on，
   資金願意買成長股與新興市場，對台股有利。
2. **美國的錢從哪個類股移到哪個類股？** → 看 RRG 類股輪動圖。點從「改善」往「領先」移動＝資金正在流入；
   從「領先」掉到「轉弱」＝資金開始獲利了結。**半導體(SMH)** 和 **台灣 ETF(EWT)** 的位置對台股最關鍵。
3. **台股的錢在哪裡、法人怎麼佈局？** → 三大法人金額看「大資金方向」，類股成交比重看「熱度往哪集中」，
   法人產業別買賣超看「實際押注哪些族群」。三者同時指向同一族群＝主流。

**指標說明**
- **CMF20（Chaikin 資金流）**：收盤越靠近當日高點且量越大越正，>+0.05 視為買盤主導、<−0.05 賣盤主導。
- **成交額放大**：近 5 日均成交金額 ÷ 近 60 日均，>1.3 代表有大量資金進出。
- **RS-Ratio / RS-Momentum**：相對大盤強度與強度的變化速度（簡化版 RRG）。

**限制（請務必知道）**
- 真正的「基金申購/贖回金流」沒有免費可靠來源，這裡都是 **價格與成交量推算的代理指標**，看的是方向，不是精確金額。
- 法人產業別金額＝買賣超股數 × 最新收盤價的估算，且只含上市股票。
- 相關係數是過去的統計，不保證明天；美股大跌而台股不跌的日子也常見。
- 本頁只供觀察，**不會影響掃描結果與部位計算**（部位用的是既有的大資金燈號）。
"""


# ---------------------------------------------------------------
# 入口
# ---------------------------------------------------------------
def render_flows_tab(cache_dir=".cache", tw_days=20):
    st.markdown("### 💰 資金流向")
    st.caption("美國投資人的錢在哪、台股法人怎麼佈局、兩邊連動多強。資料：Yahoo Finance、TWSE 官方（每日更新）。")

    top = st.columns([1, 1, 4])
    if not st.session_state.get("flows_on"):
        if top[0].button("📡 載入資金流向", type="primary", key="flows_load"):
            st.session_state["flows_on"] = True
            st.rerun()
        st.info("按下「載入資金流向」開始。第一次需抓台股近 20 日歷史，約 1~2 分鐘；之後每天只補新的一天。")
        return
    if top[0].button("🔄 重新整理", key="flows_refresh"):
        _load_us.clear()
        _load_tw.clear()
        st.rerun()

    with st.spinner("抓取美股 / 跨資產資料 …"):
        us = _load_us(cache_dir)
    with st.spinner("抓取台股三大法人 / 類股成交值（首次約 1~2 分鐘）…"):
        twd = _load_tw(cache_dir, tw_days)

    summ = F.build_summary(
        us_sec=us["sectors"] if us else None, us_cross=us["cross"] if us else None,
        risk_stats=us["ratio_stats"] if us else None, tw=twd["tw"],
        tw_share=twd["share"], tw_inst_sec=twd["inst_sec"], link=us["link"] if us else None)

    st.markdown("### 📌 現在錢往哪去（自動摘要）")
    c1, c2, c3 = st.columns(3)
    for col, title, key in ((c1, "🇺🇸 美國資金", "us"), (c2, "🇹🇼 台股資金", "tw"),
                            (c3, "🔗 台美連動", "link")):
        with col.container(border=True):
            st.markdown(f"**{title}**")
            lines = summ.get(key) or ["暫無資料"]
            st.markdown("\n".join(f"- {x}" for x in lines))
    asof = []
    if us and us.get("asof") is not None:
        asof.append(f"美股資料截至 {pd.Timestamp(us['asof']):%Y-%m-%d}")
    if not twd["tw"]["inst"].empty:
        asof.append(f"台股資料截至 {twd['tw']['inst'].index[-1]:%Y-%m-%d}")
    if asof:
        st.caption("；".join(asof))

    t_us, t_tw, t_link, t_help = st.tabs(["🇺🇸 美國資金", "🇹🇼 台股資金", "🔗 台美連動", "❓ 怎麼看"])
    with t_us:
        _render_us(us)
    with t_tw:
        _render_tw(twd)
    with t_link:
        _render_link(us)
    with t_help:
        st.markdown(_GUIDE)


def render():
    from twscanner.ui.state import get_base_config
    render_flows_tab(get_base_config()["data"]["cache_dir"])
