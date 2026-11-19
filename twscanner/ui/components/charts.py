"""回測相關圖表：Edge 燈號條、累積 R + 回撤、月度報酬。"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_edge_meter(expectancy):
    """期望值 R 燈號條"""
    try:
        e = float(expectancy)
    except Exception:
        e = 0

    # 區間：< 0 紅、0-0.2 黃、> 0.2 綠
    val = max(min(e, 1.0), -0.5)
    pct = (val + 0.5) / 1.5 * 100  # 映射到 0-100

    if e < 0:
        label = "無 edge"
        color = "#DC2626"
    elif e < 0.2:
        label = "偏弱"
        color = "#D97706"
    elif e < 0.5:
        label = "有 edge"
        color = "#059669"
    else:
        label = "強 edge"
        color = "#15803D"

    st.markdown(
        f"""
<div style='background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:12px 16px;'>
  <div style='display:flex; justify-content:space-between; margin-bottom:8px;'>
    <span style='color:#64748B; font-size:0.78rem; font-weight:500;'>策略 Edge</span>
    <span style='color:{color}; font-size:0.85rem; font-weight:600;'>{label}（期望值 {e:.2f} R）</span>
  </div>
  <div style='background:#F1F5F9; height:8px; border-radius:4px; position:relative; overflow:hidden;'>
    <div style='position:absolute; left:{(0.5/1.5)*100:.0f}%; width:1px; height:100%; background:#94A3B8;'></div>
    <div style='position:absolute; left:0; top:0; bottom:0; width:{pct:.1f}%; background:{color}; border-radius:4px;'></div>
  </div>
  <div style='display:flex; justify-content:space-between; margin-top:4px;'>
    <span style='color:#94A3B8; font-size:0.7rem;'>-0.5</span>
    <span style='color:#94A3B8; font-size:0.7rem;'>0</span>
    <span style='color:#94A3B8; font-size:0.7rem;'>+1.0</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_drawdown_chart(trades):
    """累積 R 折線 + drawdown 區域子圖"""
    if len(trades) == 0:
        return

    trades = trades.copy().sort_values("entry_date")
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    trades["累積R"] = trades["r_multiple"].fillna(0).cumsum()
    trades["peak"] = trades["累積R"].cummax()
    trades["drawdown"] = trades["累積R"] - trades["peak"]

    from plotly.subplots import make_subplots
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.7, 0.3], vertical_spacing=0.03,
        subplot_titles=("累積 R", "Drawdown"),
    )
    fig.add_trace(
        go.Scatter(
            x=trades["entry_date"], y=trades["累積R"], mode="lines",
            line=dict(color="#4F46E5", width=2),
            fill="tozeroy", fillcolor="rgba(79, 70, 229, 0.08)",
            name="累積 R",
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=trades["entry_date"], y=trades["drawdown"], mode="lines",
            line=dict(color="#DC2626", width=1.5),
            fill="tozeroy", fillcolor="rgba(220, 38, 38, 0.15)",
            name="Drawdown",
        ),
        row=2, col=1,
    )
    fig.update_layout(
        height=380, showlegend=False,
        margin=dict(l=8, r=8, t=40, b=8),
        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
        font=dict(family="Inter, sans-serif", size=11, color="#0F172A"),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#F1F5F9")
    fig.update_yaxes(showgrid=True, gridcolor="#F1F5F9")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_monthly_returns(trades):
    """月度報酬柱狀圖"""
    if len(trades) == 0:
        return
    df = trades.copy()
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["month"] = df["entry_date"].dt.to_period("M").astype(str)
    monthly = df.groupby("month")["r_multiple"].sum().reset_index()
    colors = ["#059669" if v >= 0 else "#DC2626" for v in monthly["r_multiple"]]

    fig = go.Figure(go.Bar(
        x=monthly["month"], y=monthly["r_multiple"],
        marker_color=colors, marker_line_width=0,
    ))
    fig.update_layout(
        height=260, margin=dict(l=8, r=8, t=8, b=8),
        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
        font=dict(family="Inter, sans-serif", size=11),
        showlegend=False,
        yaxis_title="累積 R",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#F1F5F9")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
