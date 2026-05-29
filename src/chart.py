"""K 線 + 技術指標圖（plotly）"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .indicators import add_indicators


def make_kline(df, title="", entry=None, stop=None, target1=None, target2=None,
               recent_bars=120):
    """
    K 棒 + MA + Volume + KD + MACD 四面板。
    可選標示進場價/停損/目標水平線。
    """
    if df is None or df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = add_indicators(df).dropna()
    if len(df) == 0:
        return None
    df = df.tail(recent_bars)

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        row_heights=[0.55, 0.15, 0.15, 0.15],
        vertical_spacing=0.02,
        subplot_titles=("", "成交量", "KD", "MACD"),
    )

    # ---- K 棒 ----
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"],
            increasing_line_color="#DC2626", decreasing_line_color="#059669",
            increasing_fillcolor="#DC2626", decreasing_fillcolor="#059669",
            name="K", showlegend=False,
        ),
        row=1, col=1,
    )

    # ---- 均線 ----
    for col, color, name in [
        ("MA5", "#F59E0B", "MA5"),
        ("MA20", "#4F46E5", "MA20"),
        ("MA60", "#94A3B8", "MA60"),
    ]:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df[col], mode="lines",
                line=dict(color=color, width=1.2),
                name=name,
            ),
            row=1, col=1,
        )

    # ---- 進場 / 停損 / 目標水平線 ----
    annot = []
    if entry is not None:
        fig.add_hline(y=entry, line=dict(color="#0F172A", width=1, dash="dot"),
                       row=1, col=1)
        annot.append(("進場", entry, "#0F172A"))
    if stop is not None:
        fig.add_hline(y=stop, line=dict(color="#DC2626", width=1, dash="dot"),
                       row=1, col=1)
        annot.append(("停損", stop, "#DC2626"))
    if target1 is not None:
        fig.add_hline(y=target1, line=dict(color="#059669", width=1, dash="dot"),
                       row=1, col=1)
        annot.append(("目標1", target1, "#059669"))
    if target2 is not None:
        fig.add_hline(y=target2, line=dict(color="#15803D", width=1, dash="dot"),
                       row=1, col=1)
        annot.append(("目標2", target2, "#15803D"))

    for label, y, color in annot:
        fig.add_annotation(
            x=df.index[-1], y=y, xref="x", yref="y",
            text=f"{label} {y}", showarrow=False,
            font=dict(color=color, size=10),
            xshift=4, xanchor="left", bgcolor="rgba(255,255,255,0.85)",
            row=1, col=1,
        )

    # ---- 成交量 ----
    colors = [
        "#DC2626" if c >= o else "#059669"
        for c, o in zip(df["Close"], df["Open"])
    ]
    fig.add_trace(
        go.Bar(
            x=df.index, y=df["Volume"], marker_color=colors,
            name="Volume", showlegend=False,
            marker_line_width=0,
        ),
        row=2, col=1,
    )

    # ---- KD ----
    fig.add_trace(
        go.Scatter(x=df.index, y=df["K"], mode="lines",
                   line=dict(color="#4F46E5", width=1.2), name="K"),
        row=3, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["D"], mode="lines",
                   line=dict(color="#F59E0B", width=1.2), name="D"),
        row=3, col=1,
    )
    fig.add_hline(y=80, line=dict(color="#94A3B8", width=0.5, dash="dot"), row=3, col=1)
    fig.add_hline(y=20, line=dict(color="#94A3B8", width=0.5, dash="dot"), row=3, col=1)

    # ---- MACD ----
    osc_colors = ["#DC2626" if v >= 0 else "#059669" for v in df["OSC"]]
    fig.add_trace(
        go.Bar(x=df.index, y=df["OSC"], marker_color=osc_colors,
               name="OSC", showlegend=False, marker_line_width=0),
        row=4, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["DIF"], mode="lines",
                   line=dict(color="#4F46E5", width=1.2), name="DIF"),
        row=4, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["MACD"], mode="lines",
                   line=dict(color="#F59E0B", width=1.2), name="MACD"),
        row=4, col=1,
    )

    fig.update_layout(
        title=dict(text=title, x=0.02, font=dict(size=14, color="#0F172A")),
        height=620,
        margin=dict(l=8, r=8, t=40, b=8),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                     xanchor="right", x=1, font=dict(size=10)),
        xaxis_rangeslider_visible=False,
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        font=dict(family="Inter, sans-serif", size=11, color="#0F172A"),
    )
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])],
                      showgrid=True, gridcolor="#F1F5F9")
    fig.update_yaxes(showgrid=True, gridcolor="#F1F5F9")

    return fig
