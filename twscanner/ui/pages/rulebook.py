"""實證規則：買哪幾檔、何時買、何時賣（資料：docs/research/portfolio_study_2026-11.json）。"""
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from twscanner.analysis.revenue_surprise import BUY_HIGH_PCT, CHECK_DAY, KEEP_HIGH_PCT, RULE_N
from twscanner.core.config import PROJECT_ROOT
from twscanner.services.jobs import load_rulebook
from twscanner.services.rulebook import build_rulebook
from twscanner.storage import cloud as store
from twscanner.ui.components.blocks import callout, conclusion, empty, kpi_row
from twscanner.ui.components.charts import plot
from twscanner.ui.format import fmt_pct
from twscanner.ui.settings import build_cfg
from twscanner.ui.state import cloud_owner

STUDY = PROJECT_ROOT / "docs" / "research" / "portfolio_study_2026-11.json"
INK, GREY, MID = "#18181B", "#D4D4D8", "#2563EB"
FONT = dict(family="Inter, Noto Sans TC, sans-serif", size=12)


def _load():
    try:
        return json.loads(STUDY.read_text(encoding="utf-8"))
    except Exception:
        return None


def _layout(fig, height, legend=True):
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=12, b=8), plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                      font=FONT, showlegend=legend, legend=dict(orientation="h", y=-0.2, x=0))


def _rules_section():
    st.markdown("### 規則")
    st.markdown(
        f"1. **什麼時候看**：每月 {CHECK_DAY} 日之後的第一個交易日收盤後（營收在每月 10 日前公布），一個月只看這一次。\n"
        f"2. **買哪幾檔**：距一年高點 ≥ {BUY_HIGH_PCT:.0f}% 的股票裡，營收驚喜最高的 {RULE_N} 檔，每檔金額一樣，隔天開盤買。\n"
        f"3. **什麼時候賣**：下次檢查時，持股的距一年高點掉到 {KEEP_HIGH_PCT:.0f}% 以下，或營收驚喜轉負，就賣掉換名單上的下一檔；"
        "其餘繼續抱。\n"
        "4. **不做的事**：不設停損、不設停利、不因大盤轉弱全部出場。符合條件的股票不夠時，空位留現金。")
    st.caption("營收驚喜＝最新月營收年增率比這家公司自己過去一年的平均高出多少（除以波動，讓不同公司可以比較）。")


def _table(rows, extra=()):
    df = pd.DataFrame([{"股票": f"{r['code']} {r.get('name') or ''}".strip(), "收盤價": r.get("close"),
                        "距一年高點%": r.get("high_1y", r.get("hi52_pct")), "營收驚喜": r.get("sur"),
                        "營收年增%": r.get("yoy_pct"), **{k: r.get(v) for k, v in extra}} for r in rows])
    st.dataframe(df, hide_index=True, use_container_width=True, column_config={
        "收盤價": st.column_config.NumberColumn(format="%.2f"), "距一年高點%": st.column_config.NumberColumn(format="%.0f%%"),
        "營收驚喜": st.column_config.NumberColumn(format="%+.2f"), "營收年增%": st.column_config.NumberColumn(format="%+.1f%%")})


def _live_section(data):
    st.markdown("### 現在的名單")
    res = st.session_state.get("result")
    partial = bool(st.session_state.get("_result_partial"))
    scan_df = res.get("df") if res and not partial else None
    held = st.session_state.get("holdings_df")
    codes = [str(c).strip() for c in held["股票代號"].dropna()] if held is not None and "股票代號" in held else []
    if scan_df is not None and len(scan_df):
        st.caption(f"用目前的掃描結果（{len(scan_df)} 檔）計算。範圍選「全台股」名單才完整。"
                   "會逐檔抓月營收歷史，第一次約需一兩分鐘。")
        if st.button("算出現在的名單", type="primary", key="rulebook_run"):
            bar = st.progress(0.0, text="抓月營收歷史")
            cfg = build_cfg()
            st.session_state["rulebook"] = build_rulebook(
                scan_df, cfg["data"]["cache_dir"], holding_codes=codes,
                progress_cb=lambda p, msg: bar.progress(min(1.0, p), text=msg))
            bar.empty()
    if partial:
        st.caption("目前表格是排程掃描載入的，只有進場與觀察的股票，無法在這裡重算；下面用排程算好的名單。"
                   "要自己重算，請先到「找標的」按「開始掃描」。")
    rb = st.session_state.get("rulebook")
    if rb is None and store.is_enabled() and cloud_owner():
        rb = load_rulebook(cloud_owner())
        if rb:
            st.caption(f"排程計算於 {str(rb.get('at', ''))[:16].replace('T', ' ')}（營收月份 {rb['month']}）。")
    if rb:
        if rb["candidates"]:
            st.markdown(f"**買進名單**（營收月份 {rb['month']}；距一年高點 ≥ {BUY_HIGH_PCT:.0f}% 的有 {rb['near_high']} 檔，"
                        f"其中 {rb['eligible']} 檔算得出營收驚喜）")
            _table(rb["candidates"])
            if len(rb["candidates"]) < RULE_N:
                st.caption(f"符合條件的不足 {RULE_N} 檔：照規則只買這幾檔，每檔仍是總資金的 1/{RULE_N}，其餘留現金。")
        else:
            empty("現在沒有符合條件的股票", "照規則留現金，下個月營收公布後再看。")
        if rb["holdings"]:
            st.markdown("**持股檢查**")
            _table(rb["holdings"], extra=(("動作", "action"), ("理由", "reason")))
        if rb["missing"]:
            st.caption(f"{len(rb['missing'])} 檔抓不到足夠的營收歷史（新上市或來源流量上限），沒有列入。")
        return
    picks = data["picks"]
    st.markdown(f"**研究資料截止日（{picks['as_of']}）的名單**：符合條件的只有 {picks['eligible']} 檔。")
    _table(picks["list"])
    st.caption("這是研究跑完當天的靜態名單，不會自動更新。到「找標的」掃描全台股後回到這裡，可以算出最新名單與持股檢查。")


def _evidence_section(data):
    rule, bm = data["rule"], data["benchmarks"]
    st.markdown("### 證據")
    cv = rule["curve"]
    fig = go.Figure()
    for key, name, color, width in (("rule", "實證規則", INK, 2.2), ("0050", "0050 含息", MID, 1.6),
                                    ("avg", "可交易股平均", GREY, 1.6)):
        fig.add_trace(go.Scatter(x=cv["dates"], y=cv[key], name=name, mode="lines", line=dict(color=color, width=width)))
    fig.update_yaxes(type="log", title="1 元變成幾元（對數刻度）", gridcolor="#F1F5F9")
    fig.update_xaxes(showgrid=False)
    fig.update_layout(title="投入 1 元的累積結果（扣成本）")
    _layout(fig, 320)
    plot(fig)

    yr = rule["yearly"]
    years = list(yr)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="實證規則", x=[f"'{y[2:]}" for y in years], y=[yr[y]["rule"] for y in years], marker_color=INK))
    fig.add_trace(go.Bar(name="0050 含息", x=[f"'{y[2:]}" for y in years], y=[yr[y]["0050"] for y in years],
                         marker_color=GREY))
    fig.update_layout(barmode="group", title="逐年報酬 %")
    fig.update_xaxes(type="category", tickangle=0)
    fig.update_yaxes(gridcolor="#F1F5F9", zeroline=True, zerolinecolor="#94A3B8")
    _layout(fig, 280)
    plot(fig)
    lost = [y for y in years if yr[y]["rule"] < yr[y]["0050"]]
    neg = [y for y in years if yr[y]["rule"] < 0]
    st.caption(f"{len(years)} 年中 {len(years) - len(lost)} 年贏過 0050；落後的年份：{'、'.join(lost)}。"
               f"虧損的年份：{'、'.join(neg)}。{data['benchmark_note']}。")

    st.markdown("**兩個獨立時段都成立**")
    rows = []
    for key, label in (("A", "2005–2017"), ("B", "2018–2026"), ("ALL", "全期")):
        r = rule["by_period"][key]
        rows.append({"時段": label, "規則年化%": r["cagr"], "0050%": bm[key]["0050"], "股票平均%": bm[key]["avg"],
                     "最大回撤%": r["mdd"], "每筆勝率%": r["win_pct"], "賺的平均%": r["avg_win"], "賠的平均%": r["avg_loss"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                 column_config={c: st.column_config.NumberColumn(format="%.1f") for c in rows[0] if c != "時段"})
    allp = rule["by_period"]["ALL"]
    st.caption(f"全期 {allp['trades']:,} 筆交易，平均持有 {allp['avg_days']:.0f} 個交易日，每年換手約 {allp['turnover']:.0f} 次。"
               "勝率只有五成出頭，獲利來自賺的比賠的大。")

    st.markdown("**加上停損或大盤擇時，報酬都變差**")
    base = rule["robustness"][0]["ALL"]
    ov = [{"外加規則": "不加（實證規則）", "全期年化%": base["cagr"], "最大回撤%": base["mdd"]}]
    ov += [{"外加規則": o["name"], "全期年化%": o["ALL"]["cagr"], "最大回撤%": o["ALL"]["mdd"]} for o in rule["overlays"]]
    st.dataframe(pd.DataFrame(ov), hide_index=True, use_container_width=True,
                 column_config={c: st.column_config.NumberColumn(format="%.1f") for c in ("全期年化%", "最大回撤%")})
    st.caption("「大盤跌破 MA20：不買新的」就是系統的大盤燈號：報酬幾乎不變、回撤略小，可以保留。"
               "停損與「空頭全部出場」都讓報酬變低。")

    xs = {x["name"]: x for x in data["revenue_xs"]["all"]}
    nh = {x["name"]: x for x in data["revenue_xs"]["within_near_high"]}
    s, n = xs["營收驚喜"]["h20"], nh["營收驚喜"]["h20"]
    odds = data["price_only"]["single_stock_odds"]["20d"]
    st.markdown("**為什麼是這兩個條件**")
    st.markdown(
        f"- **營收驚喜**：公布後一個月，前 20% 的股票比平均多賺 {s['A']['top_excess_pct']:+.2f}%（2004–2017）與 "
        f"{s['B']['top_excess_pct']:+.2f}%（2018–2026），t 值 {s['A']['t']:.1f} 與 {s['B']['t']:.1f}"
        "（高於 3 就很難用運氣解釋）。\n"
        f"- **再加上距一年高點 ≥ {BUY_HIGH_PCT:.0f}%**：多賺 {n['A']['top_excess_pct']:+.2f}% 與 {n['B']['top_excess_pct']:+.2f}%。\n"
        f"- **只看價格不夠**：近高股票裡任選一檔，一個月後贏過 0050 的機率只有 {odds['beat_0050_pct']:.0f}%，"
        f"賺錢的機率 {odds['positive_pct']:.0f}%。")

    with st.expander("改一個條件還成不成立（穩健性）"):
        rb = [{"改動": o["name"], "全期年化%": o["ALL"]["cagr"], "2005–17%": o["A"]["cagr"], "2018–26%": o["B"]["cagr"],
               "最大回撤%": o["ALL"]["mdd"]} for o in rule["robustness"]]
        st.dataframe(pd.DataFrame(rb), hide_index=True, use_container_width=True,
                     column_config={c: st.column_config.NumberColumn(format="%.1f") for c in rb[0] if c != "改動"})
        st.caption(f"每一列只改一個條件。全期 0050 含息年化 {bm['ALL']['0050']:.1f}%。"
                   "越晚換股越差，符合「營收公布後股價慢慢反應」的機制。持股越少，回撤越深。")
    with st.expander("研究方法、限制與重跑方式"):
        st.markdown(
            f"- 資料：{data['stocks']:,} 檔目前上市股的日線與月營收，2005 年起；資料截止 {data['as_of']}。\n"
            f"- 模擬一個真的帳戶：收盤決定、隔天開盤成交；一字漲停買不到、跌停鎖死賣不掉；來回成本 {data['cost_pct']:.3f}%。\n"
            "- 可交易：股價 ≥ 10 元、20 日均量 ≥ 500 張。營收保守用每月 13 日後才視為已知。\n"
            "- **限制**：只含目前仍上市的股票（下市股不在內，報酬偏樂觀）；常買到中小型股，資金大時優勢會變小"
            "（流動性門檻提高到 2,000 張，全期年化降到約 21%）；公開的做法之後通常會變弱；只測上市、沒有上櫃。\n"
            "- 程式：`scripts/strategy_study/portfolio_study.py`；完整報告：`reports/台股波段買賣規則實證研究.md`。建議每季重跑。")


def render():
    data = _load()
    if not data:
        st.caption("找不到研究資料。")
        return
    rule, bm = data["rule"], data["benchmarks"]
    allp = rule["by_period"]["ALL"]
    yr = rule["yearly"]
    wins = sum(v["rule"] > v["0050"] for v in yr.values())
    conclusion(f"有實證的做法：每月營收公布後，買接近一年高點、營收驚喜最高的 {RULE_N} 檔",
               f"2005–2026 年扣成本年化 {allp['cagr']:.1f}%，同期 0050 含息 {bm['ALL']['0050']:.1f}%；"
               f"{len(yr)} 年中 {wins} 年贏過 0050。這是一籃子股票的統計優勢，不是單一檔的預測："
               f"最大回撤仍有 {allp['mdd']:.0f}%，最近兩年落後 0050。", "go")
    kpi_row([
        ("規則年化", fmt_pct(allp["cagr"], 1), "2005–2026，扣成本"),
        ("0050 含息", fmt_pct(bm["ALL"]["0050"], 1), "同期"),
        ("最大回撤", fmt_pct(allp["mdd"], 0), f"0050 為 {bm['ALL']['0050_mdd']:.0f}%"),
        ("任一年落後 0050", f"{rule['lag_0050_pct']['1y']:.0f}%", f"任三年 {rule['lag_0050_pct']['3y']:.0f}%"),
    ])
    callout("回測不是保證。這套規則只在「分散買滿、每月照做、不臨場加減」時才有統計意義；"
            f"只買其中兩三檔，結果主要看運氣。曾經連續約 {rule['longest_underwater_months']} 個月沒有創新高。")
    _rules_section()
    _live_section(data)
    _evidence_section(data)
