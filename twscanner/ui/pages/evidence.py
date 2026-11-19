"""大樣本實證：選股訊號有沒有比隨機進場好？（資料：docs/research/strategy_study_2026-11.json）"""
import json

import plotly.graph_objects as go
import streamlit as st

from twscanner.core.config import PROJECT_ROOT
from twscanner.ui.components.blocks import conclusion
from twscanner.ui.components.charts import plot

STUDY = PROJECT_ROOT / "docs" / "research" / "strategy_study_2026-11.json"
SERIES = [("breakout", "突破訊號（系統預設）", "#2563EB"),
          ("rs", "相對強度前 10%", "#B45309"),
          ("random", "隨機進場（對照組）", "#94A3B8")]


def _load():
    try:
        return json.loads(STUDY.read_text(encoding="utf-8"))
    except Exception:
        return None


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


def render():
    data = _load()
    if not data:
        st.caption("找不到研究資料。")
        return
    conclusion("過去兩年，系統的選股訊號沒有比隨機挑股更好",
               f"{data['universe']}、{data['period']}。樣本內（{data['split']['is']}）多數策略賺錢，"
               f"但隨機進場也一樣賺；樣本外（{data['split']['oos']}）全部轉為持平或虧損。"
               f"{data['grid']['variants']} 種參數組合中，沒有一種在樣本外有顯著優勢。", "stop")
    oos_share = data["regime_share"]["OOS"]
    is_share = data["regime_share"]["IS"]
    _chart(data, "OOS", "樣本外（最近 6 個月）：三種方法都在 0 附近或以下")
    _chart(data, "IS", "樣本內（前 15 個月）：隨機進場也賺，代表賺的是行情，不是選股")
    st.caption(f"大盤空頭天數比例：樣本內 {is_share.get('bear', 0) * 100:.0f}% → 樣本外 {oos_share.get('bear', 0) * 100:.0f}%。"
               f"規則：{data['rules']}。")

    st.markdown("### 這對你的意思")
    st.markdown(
        "1. **賺錢的來源是「多頭時持有強勢股」，不是選中哪一檔。** 前 15 個月，只要在大盤非空頭時買站上 MA60 的股票，"
        "隨機挑也有正報酬；行情轉弱後，沒有一種挑法有顯著獲利。所以最重要的開關是頁首的大盤燈號。\n"
        "2. **系統最有價值的部分是風險控制。** 每筆固定風險、照停損出場、空頭不開新倉、月虧損上限，"
        "決定的是你在壞行情裡少賠多少，這比選股更能保護「每月一萬」的目標。\n"
        "3. **月目標要先用小部位驗證。** 先用最小單位（例如 1 張或零股）照計畫操作，累積 30 筆以上實戰紀錄，"
        "看「策略驗證 → 實戰績效」的期望值是否為正，再放大到正常部位。\n"
        "4. **評分當作「篩選清單」，不要當成「預測」。** 系統的條件能把明顯不該碰的股票（下跌趨勢、流動性差、"
        "財報地雷）排除掉，但在合格清單裡，排名第一和第十的表現沒有可靠差別。")
    with st.expander("研究方法與重跑方式"):
        st.markdown(
            "- 對每一種策略，都用同樣的品質過濾、大盤閘門與出場規則，另做一組「隨機進場、頻率相同」的對照組。"
            "策略必須贏過對照組，才算有選股能力。\n"
            "- 前 70% 交易日用來挑參數（樣本內），後 30% 只用來檢驗（樣本外），挑完就不再調整。\n"
            "- 程式在 `scripts/strategy_study/`，資料摘要在 `docs/research/strategy_study_2026-11.json`。"
            "建議每季重跑一次，市場環境改變時結論可能不同。")
