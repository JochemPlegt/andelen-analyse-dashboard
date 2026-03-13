"""Plotly-grafieken voor het Streamlit-dashboard."""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from config import MA_SHORT, MA_LONG, RSI_OVERBOUGHT, RSI_OVERSOLD


def price_chart(df: pd.DataFrame, name: str) -> go.Figure:
    """Koersgrafiek met candlesticks + SMA-50 en SMA-200."""
    fig = make_subplots(rows=1, cols=1)

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=df["Close"],
        name="Koers", increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
    ))

    sma_s = f"SMA_{MA_SHORT}"
    sma_l = f"SMA_{MA_LONG}"
    if sma_s in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[sma_s],
            name=f"SMA {MA_SHORT}", line=dict(color="#f59e0b", width=1.5)
        ))
    if sma_l in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[sma_l],
            name=f"SMA {MA_LONG}", line=dict(color="#6366f1", width=1.5)
        ))

    fig.update_layout(
        title=f"{name} — Koers & Moving Averages",
        xaxis_rangeslider_visible=False,
        height=420, template="plotly_dark",
        legend=dict(orientation="h", y=1.08),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    return fig


def rsi_chart(df: pd.DataFrame, name: str) -> go.Figure:
    """RSI-grafiek met overbought/oversold zones."""
    rsi_col = f"RSI_14"
    fig = go.Figure()

    if rsi_col in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[rsi_col],
            name="RSI", line=dict(color="#38bdf8", width=1.8)
        ))

    fig.add_hline(y=RSI_OVERBOUGHT, line_dash="dash",
                  line_color="#ef5350", annotation_text="Overbought")
    fig.add_hline(y=RSI_OVERSOLD,   line_dash="dash",
                  line_color="#26a69a", annotation_text="Oversold")
    fig.add_hrect(y0=RSI_OVERBOUGHT, y1=100,
                  fillcolor="#ef5350", opacity=0.07, line_width=0)
    fig.add_hrect(y0=0, y1=RSI_OVERSOLD,
                  fillcolor="#26a69a", opacity=0.07, line_width=0)

    fig.update_layout(
        title=f"{name} — RSI ({14})",
        yaxis=dict(range=[0, 100]),
        height=250, template="plotly_dark",
        margin=dict(l=10, r=10, t=50, b=10),
        showlegend=False,
    )
    return fig


def macd_chart(df: pd.DataFrame, name: str) -> go.Figure:
    """MACD-lijn, signaallijn en histogram."""
    fig = go.Figure()

    if "MACD" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["MACD"],
            name="MACD", line=dict(color="#38bdf8", width=1.5)
        ))
    if "MACD_signal" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["MACD_signal"],
            name="Signaal", line=dict(color="#f59e0b", width=1.5)
        ))
    if "MACD_hist" in df.columns:
        colors = ["#26a69a" if v >= 0 else "#ef5350"
                  for v in df["MACD_hist"].fillna(0)]
        fig.add_trace(go.Bar(
            x=df.index, y=df["MACD_hist"],
            name="Histogram", marker_color=colors, opacity=0.7
        ))

    fig.update_layout(
        title=f"{name} — MACD",
        height=250, template="plotly_dark",
        legend=dict(orientation="h", y=1.15),
        margin=dict(l=10, r=10, t=50, b=10),
        barmode="relative",
    )
    return fig


def backtest_curve_chart(
    curve_strat: pd.Series,
    curve_bh: pd.Series,
    name: str,
    start_capital: float = 10_000,
) -> go.Figure:
    """Vergelijkingsgrafiek strategie vs buy-and-hold."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=curve_strat.index, y=curve_strat,
        name="MA Crossover", line=dict(color="#38bdf8", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=curve_bh.index, y=curve_bh,
        name="Buy & Hold", line=dict(color="#f59e0b", width=2, dash="dot")
    ))
    fig.add_hline(y=start_capital, line_dash="dash",
                  line_color="#6b7280", annotation_text="Startkapitaal")

    fig.update_layout(
        title=f"{name} — Strategie vs Buy & Hold (€{start_capital:,.0f})",
        yaxis_tickprefix="€",
        height=350, template="plotly_dark",
        legend=dict(orientation="h", y=1.08),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    return fig
