"""大樣本實證：選股訊號有沒有比隨機進場好？（資料：docs/research/strategy_study_2026-11.json）"""
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from twscanner.analysis.goal import capital_for_target
from twscanner.core.config import PROJECT_ROOT
from twscanner.ui.components.blocks import conclusion, kpi_row
from twscanner.ui.components.charts import plot
from twscanner.ui.format import fmt_pct

STUDY = PROJECT_ROOT / "docs" / "research" / "strategy_study_2026-11.json"
SHORT = {"中期動能（6 個月漲幅）": "6 個月漲幅", "短期動能（1 個月漲幅）": "1 個月漲幅",
         "短期反轉（1 個月跌深）": "1 個月跌深", "系統突破分數": "突破分數"}
CORE = PROJECT_ROOT / "docs" / "research" / "core_indicator_2026-11.json"
SERIES = [("breakout", "突破訊號（系統預設）", "#2563EB"),
          ("rs", "相對強度前 10%", "#B45309"),
          ("random", "隨機進場（對照組）", "#94A3B8")]


def _load(path=STUDY):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _bar_layout(fig, height):
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=12, b=8), plot_bgcolor="#FFFFFF",
                      paper_bgcolor="#FFFFFF", showlegend=False,
                      font=dict(family="Inter, Noto Sans TC, sans-serif", size=12))


def _core_section():
    """核心指標：8 個候選指標的比較，以及「距一年高點」的門檻與逐年結果。"""
    core = _load(CORE)
    if not core:
        return False
    th = core["threshold"]
    nb, bear = th["non_bear"], th["bear"]
    conclusion("最值得用的一個指標：距一年高點（收盤 ÷ 一年最高價）",
               f"大盤不是空頭時，收盤 ≥ 一年高點 90% 的股票，之後 1 個月平均 {nb['t90']:+.2f}%（已扣成本），"
               f"全部可交易股 {nb['all']:+.2f}%，離高點 30% 以上的 {nb['low']:+.2f}%；"
               f"{nb['beat_avg_pct']:.0f}% 的週數跑贏平均，每一年都跑贏（壞年份仍會賠，只是賠得少）。大盤空頭時沒有優勢。", "go")
    kpi_row([
        ("強勢區 1 個月", fmt_pct(nb["t90"]), "大盤非空頭、扣成本"),
        ("全部可交易股", fmt_pct(nb["all"]), "同期平均"),
        ("跑贏平均的週數", f"{nb['beat_avg_pct']:.0f}%", f"{nb['weeks']} 週"),
        ("平均每週符合", f"{nb['avg_count']:.0f} 檔", "可交易股中"),
    ])

    st.markdown("**8 個指標比一比：前 20% 的股票，1 個月比平均多賺幾 %**")
    rk = sorted(core["ranking"], key=lambda r: -r["all"]["excess_pct"])
    names = [SHORT.get(r["name"], r["name"]) for r in rk]
    vals = [r["all"]["excess_pct"] for r in rk]
    fig = go.Figure(go.Bar(
        x=vals, y=names, orientation="h",
        marker_color=["#18181B" if r["name"] == "距一年高點" else "#D4D4D8" for r in rk],
        text=[f"{v:+.2f}%" for v in vals], textposition="outside", cliponaxis=False,
        hovertext=[f"{r['name']}<br>t 值 {r['all']['t']:.1f}<br>非空頭 {r['non_bear']['excess_pct']:+.2f}% · "
                   f"空頭 {r['bear']['excess_pct']:+.2f}%" for r in rk], hoverinfo="text"))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="比平均多賺 %", zeroline=True, zerolinecolor="#94A3B8",
                     gridcolor="#F1F5F9", range=[min(vals) - 0.35, max(vals) + 0.4])
    _bar_layout(fig, 300)
    plot(fig)
    top = next(r for r in rk if r["name"] == "距一年高點")["all"]
    st.caption(f"距一年高點最高也最穩：{top['years_pos']}/{top['years']} 年為正、t 值 {top['t']:.1f}"
               "（> 2 代表不太可能是運氣）。動能類指標（漲幅、站上季線）也有效但較不穩；"
               "「跌深買反彈」與「低波動」在台股反而落後。")

    st.markdown("**離一年高點越近，之後 1 個月越好（扣成本）**")
    groups = [("離高點 30%+", "low"), ("全部", "all"), ("≥ 85%", "t85"), ("≥ 90%", "t90"), ("≥ 95%", "t95")]
    fig = go.Figure()
    for label, src, color in (("大盤非空頭", nb, "#18181B"), ("大盤空頭", bear, "#D4D4D8")):
        ys = [src[k] for _, k in groups]
        fig.add_trace(go.Bar(name=label, x=[g for g, _ in groups], y=ys, marker_color=color,
                             text=[f"{v:+.1f}" for v in ys], textposition="outside", cliponaxis=False,
                             textfont=dict(size=10)))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="1 個月平均 %", gridcolor="#F1F5F9", zeroline=True, zerolinecolor="#94A3B8")
    _bar_layout(fig, 280)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.2, x=0))
    plot(fig)
    st.caption("大盤非空頭時，越接近一年高點、之後越好；大盤空頭時各組差不多，所以空頭時這個指標不用。")

    st.markdown("**逐年檢查：強勢區 vs 全部（大盤非空頭時）**")
    yr = core["yearly_non_bear"]
    years = list(yr)
    xs = [f"'{y[2:]}" for y in years]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="強勢區 ≥ 90%", x=xs, y=[yr[y]["t90"] for y in years], marker_color="#18181B"))
    fig.add_trace(go.Bar(name="全部可交易股", x=xs, y=[yr[y]["all"] for y in years], marker_color="#D4D4D8"))
    fig.update_layout(barmode="group")
    fig.update_xaxes(type="category", tickangle=0)
    fig.update_yaxes(title="1 個月平均 %", gridcolor="#F1F5F9", zeroline=True, zerolinecolor="#94A3B8")
    _bar_layout(fig, 260)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.2, x=0))
    plot(fig)

    st.markdown("### 怎麼用在每天的操作")
    st.markdown(
        "1. **先看大盤燈號**：空頭就不開新倉（這個指標在空頭沒有優勢）。\n"
        "2. **候選股只看強勢區**（距一年高點 ≥ 90%）。找標的、今日決策都已依此排序，個股健檢會直接顯示。\n"
        "3. **進場價、停損、張數照交易計畫卡**；指標只負責「挑哪幾檔」，不負責「何時賣」。\n"
        "4. **分散 3–5 檔、每檔固定風險**：研究結果是一群股票的平均，單一檔仍可能賠錢。\n"
        "5. **用自己的紀錄驗證**：做滿 30 筆後，看「實戰績效」的期望值是不是正的。")
    with st.expander("研究方法、限制與重跑方式"):
        st.markdown(
            f"- 資料：{core['stocks']} 檔目前上市股，{core['period']}，共 {core['weeks']} 週；每週排名一次。\n"
            "- 可交易：股價 ≥ 10 元、20 日均量 ≥ 500 張。**隔天收盤才買**，持有 20 個交易日，含息。\n"
            f"- 成本：來回 {core['cost_pct']:.3f}%（手續費 ×2、證交稅、滑價 ×2）。\n"
            "- 大盤空頭：加權指數收盤 < MA20 且 MA5 < MA20（系統既有定義，沒有為研究調整）。\n"
            "- **限制**：只含目前仍上市的股票（下市股不在內，絕對報酬會偏高，比較強弱的影響較小）；"
            "過去十年台股以多頭為主；每週平均約 130 檔符合，一般人只會買其中幾檔，結果會比平均更分散。\n"
            "- 程式：`scripts/strategy_study/core_indicator.py`（資料用 `download10y.py` 抓）。建議每季重跑。")
    return True


def _chart(data, period, title):
    """每種出場規則一列：各策略的期望值點 + 95% 信賴區間，0 為參考線。"""
    fig = go.Figure()
    rows = [c["exit"] for c in data["comparisons"]]
    for offset, (key, name, color) in zip((-0.22, 0.0, 0.22), SERIES):
        xs, ys, lo, hi, txt = [], [], [], [], []
        for k, c in enumerate(data["comparisons"]):
            s = (c.get(key) or {}).get(period)
            if not s or not s.get("n"):
                continue
            xs.append(s["E"])
            ys.append(k + offset)
            lo.append(s["E"] - s["ci"][0])
            hi.append(s["ci"][1] - s["E"])
            txt.append(f"{name}<br>{c['exit']}<br>期望值 {s['E']:+.2f}R · {s['n']} 筆 · 勝率 {s['win%']:.0f}%"
                       f"<br>95% 區間 [{s['ci'][0]:+.2f}, {s['ci'][1]:+.2f}]")
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers", name=name, marker=dict(size=10, color=color),
            error_x=dict(type="data", symmetric=False, array=hi, arrayminus=lo, color=color, thickness=1.5, width=0),
            hovertext=txt, hoverinfo="text"))
    fig.add_vline(x=0, line=dict(color="#64748B", width=1, dash="dot"))
    fig.update_yaxes(tickmode="array", tickvals=list(range(len(rows))), ticktext=rows, autorange="reversed",
                     showgrid=False)
    fig.update_xaxes(title="平均每筆 R（已扣成本）", zeroline=False, gridcolor="#F1F5F9")
    fig.update_layout(height=320, margin=dict(l=8, r=8, t=40, b=8), plot_bgcolor="#FFFFFF",
                      paper_bgcolor="#FFFFFF", title=dict(text=title, font=dict(size=14)),
                      legend=dict(orientation="h", y=-0.28, x=0),
                      font=dict(family="Inter, Noto Sans TC, sans-serif", size=12))
    plot(fig)


def _index_section(data, target):
    """十年大盤基準：有證據的報酬來源，以及「每月一萬」需要的本金。"""
    it = data.get("index_timing")
    if not it:
        return
    st.markdown("### 有十年證據的基準：大盤本身")
    rows = []
    for key, label in (("TWII", "加權"), ("00631L", "正2")):
        for how, short in (("買進持有", "持有"), ("燈號擇時", "擇時")):
            m = it[key][how]
            rows.append({"方式": f"{label}·{short}", "年化%": m["年化"], "最大回撤%": m["最大回撤"],
                         "最差月%": m["最差月"], "賺錢月%": m["月勝率"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                 column_config={c: st.column_config.NumberColumn(format="%.1f")
                                for c in ("年化%", "最大回撤%", "最差月%")}
                 | {"賺錢月%": st.column_config.NumberColumn(format="%.0f")})
    tw = it["TWII"]
    st.caption(f"加權＝加權指數，正2＝台灣50正2（兩倍槓桿 ETF）。{it['period']}。{it['rule']}。"
               f"{it['note']}。成本已扣。")
    st.markdown(
        f"- **燈號擇時是風險工具，不是報酬工具。** 加權指數最大回撤由 {tw['買進持有']['最大回撤']:.0f}% 降到 "
        f"{tw['燈號擇時']['最大回撤']:.0f}%，但年化報酬由 {tw['買進持有']['年化']:.0f}% 降到 "
        f"{tw['燈號擇時']['年化']:.0f}%（常在反彈初期還沒進場）。\n"
        "- **兩倍槓桿的回撤超過一半**，不適合拿來追固定月收入。\n"
        "- 這十年台股大多頭，年化 16% 以上不能當成未來的預期；長期規劃用 6–10% 比較穩妥。")
    caps = [(f"{r * 100:.0f}%", capital_for_target(target, r)) for r in (0.06, 0.08, 0.10, 0.12)]
    st.markdown(f"**平均每月賺 {target:,.0f} 元，需要多少本金？**")
    st.dataframe(pd.DataFrame([{"假設年報酬": a, "需要本金（元）": b} for a, b in caps]), hide_index=True,
                 column_config={"需要本金（元）": st.column_config.NumberColumn(format="localized")})
    st.caption("短線選股在上面的研究裡沒有證明能穩定超過大盤，所以本金不足時，"
               "提高單筆風險或改用槓桿並不能讓目標變得可行，只會讓虧損月份更深。")


def render():
    data = _load()
    if not data:
        st.caption("找不到研究資料。")
        return
    has_core = _core_section()
    head = "過去兩年，「突破訊號 + 停損停利」沒有比隨機進場更好"
    body = (f"{data['universe']}、{data['period']}。樣本內（{data['split']['is']}）多數策略賺錢，"
            f"但同樣站上季線、隨機進場也一樣賺；樣本外（{data['split']['oos']}）全部轉為持平或虧損。"
            f"{data['grid']['variants']} 種參數組合中，沒有一種在樣本外有顯著優勢。"
            "也就是說：賺錢來自「股票本身夠強」，突破那一天才買沒有額外好處。")
    if has_core:
        st.markdown("---")
        st.markdown(f"### 附：{head}")
        st.markdown(body)
    else:
        conclusion(head, body, "stop")
    oos_share = data["regime_share"]["OOS"]
    is_share = data["regime_share"]["IS"]
    _chart(data, "OOS", "樣本外（最近 6 個月）：三種方法都在 0 附近或以下")
    _chart(data, "IS", "樣本內（前 15 個月）：隨機進場也賺，代表賺的是行情，不是選股")
    st.caption(f"大盤空頭天數比例：樣本內 {is_share.get('bear', 0) * 100:.0f}% → 樣本外 {oos_share.get('bear', 0) * 100:.0f}%。"
               f"規則：{data['rules']}。")

    st.markdown("### 這對你的意思")
    st.markdown(
        "1. **賺錢的來源是「多頭時持有強勢股」，不是突破那一天的訊號。** 前 15 個月，只要在大盤非空頭時買站上 MA60 的股票，"
        "隨機挑也有正報酬；行情轉弱後，沒有一種挑法有顯著獲利。所以先看大盤燈號，再用「距一年高點」挑最強的。\n"
        "2. **系統最有價值的部分是風險控制。** 每筆固定風險、照停損出場、空頭不開新倉、月虧損上限，"
        "決定的是你在壞行情裡少賠多少，這比選股更能保護「每月一萬」的目標。\n"
        "3. **月目標要先用小部位驗證。** 先用最小單位（例如 1 張或零股）照計畫操作，累積 30 筆以上實戰紀錄，"
        "看「策略驗證 → 實戰績效」的期望值是否為正，再放大到正常部位。\n"
        "4. **評分當作「篩選清單」，排序交給核心指標。** 評分的條件能把明顯不該碰的股票（下跌趨勢、流動性差、"
        "財報地雷）排除掉，但用評分排第一和第十沒有可靠差別；所以系統改用「距一年高點」排序。")
    _index_section(data, float(st.session_state.get("month_target", 10_000)))
    with st.expander("研究方法與重跑方式"):
        st.markdown(
            "- 對每一種策略，都用同樣的品質過濾、大盤閘門與出場規則，另做一組「隨機進場、頻率相同」的對照組。"
            "策略必須贏過對照組，才算有選股能力。\n"
            "- 前 70% 交易日用來挑參數（樣本內），後 30% 只用來檢驗（樣本外），挑完就不再調整。\n"
            "- 程式在 `scripts/strategy_study/`，資料摘要在 `docs/research/strategy_study_2026-11.json`。"
            "建議每季重跑一次，市場環境改變時結論可能不同。")
