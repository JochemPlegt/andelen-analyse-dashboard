"""Plotly-grafieken voor het Streamlit-dashboard."""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from config import MA_SHORT, MA_LONG, RSI_OVERBOUGHT, RSI_OVERSOLD


def price_chart(df: pd.DataFrame, name: str,
                show_bb: bool = True, dark: bool = True) -> go.Figure:
    """
    Koersgrafiek met:
      - Candlesticks
      - SMA-50 en SMA-200
      - Bollinger Bands (optioneel)
      - Koop/verkoop-pijltjes op MA-crossovers
      - Volume-balk onderaan
    """
    template = "plotly_dark" if dark else "plotly_white"

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.02,
    )

    # --- Candlesticks ---
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=df["Close"],
        name="Koers",
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
    ), row=1, col=1)

    # --- Bollinger Bands ---
    if show_bb and "BB_upper" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_upper"],
            name="BB Boven", line=dict(color="rgba(168,85,247,0.5)", width=1),
            showlegend=True,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_lower"],
            name="BB Onder", line=dict(color="rgba(168,85,247,0.5)", width=1),
            fill="tonexty", fillcolor="rgba(168,85,247,0.05)",
            showlegend=True,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_mid"],
            name="BB Midden", line=dict(color="rgba(168,85,247,0.4)", width=1, dash="dot"),
            showlegend=False,
        ), row=1, col=1)

    # --- Moving averages ---
    sma_s = f"SMA_{MA_SHORT}"
    sma_l = f"SMA_{MA_LONG}"
    if sma_s in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[sma_s],
            name=f"SMA {MA_SHORT}", line=dict(color="#f59e0b", width=1.5)
        ), row=1, col=1)
    if sma_l in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[sma_l],
            name=f"SMA {MA_LONG}", line=dict(color="#6366f1", width=1.5)
        ), row=1, col=1)

    # --- Crossover-pijltjes ---
    if sma_s in df.columns and sma_l in df.columns:
        above  = (df[sma_s] > df[sma_l]).astype(int)
        signal = above.diff()

        golden = df[signal == 1]   # koop
        death  = df[signal == -1]  # verkoop

        if not golden.empty:
            fig.add_trace(go.Scatter(
                x=golden.index,
                y=golden["Low"] * 0.98,
                mode="markers",
                name="Golden Cross (koop)",
                marker=dict(symbol="triangle-up", size=12,
                            color="#26a69a", line=dict(width=1, color="white")),
            ), row=1, col=1)

        if not death.empty:
            fig.add_trace(go.Scatter(
                x=death.index,
                y=death["High"] * 1.02,
                mode="markers",
                name="Death Cross (verkoop)",
                marker=dict(symbol="triangle-down", size=12,
                            color="#ef5350", line=dict(width=1, color="white")),
            ), row=1, col=1)

    # --- Volume ---
    if "Volume" in df.columns:
        vol_colors = [
            "#26a69a" if c >= o else "#ef5350"
            for c, o in zip(df["Close"], df["Open"])
        ]
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"],
            name="Volume", marker_color=vol_colors, opacity=0.6,
            showlegend=False,
        ), row=2, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)

    fig.update_layout(
        title=f"{name} — Koers, Moving Averages & Bollinger Bands",
        xaxis_rangeslider_visible=False,
        height=540, template=template,
        legend=dict(orientation="h", y=1.05, font=dict(size=11)),
        margin=dict(l=10, r=10, t=70, b=10),
    )
    return fig


def rsi_chart(df: pd.DataFrame, name: str, dark: bool = True) -> go.Figure:
    """RSI-grafiek met overbought/oversold zones."""
    template = "plotly_dark" if dark else "plotly_white"
    rsi_col  = "RSI_14"
    fig      = go.Figure()

    if rsi_col in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[rsi_col],
            name="RSI", line=dict(color="#38bdf8", width=1.8)
        ))

    fig.add_hline(y=RSI_OVERBOUGHT, line_dash="dash",
                  line_color="#ef5350", annotation_text="Overbought (70)")
    fig.add_hline(y=RSI_OVERSOLD,   line_dash="dash",
                  line_color="#26a69a", annotation_text="Oversold (30)")
    fig.add_hline(y=50, line_dash="dot",
                  line_color="gray", annotation_text="Neutraal")
    fig.add_hrect(y0=RSI_OVERBOUGHT, y1=100,
                  fillcolor="#ef5350", opacity=0.07, line_width=0)
    fig.add_hrect(y0=0, y1=RSI_OVERSOLD,
                  fillcolor="#26a69a", opacity=0.07, line_width=0)

    fig.update_layout(
        title=f"{name} — RSI (14)",
        yaxis=dict(range=[0, 100]),
        height=250, template=template,
        margin=dict(l=10, r=10, t=50, b=10),
        showlegend=False,
    )
    return fig


def macd_chart(df: pd.DataFrame, name: str, dark: bool = True) -> go.Figure:
    """MACD-lijn, signaallijn en histogram."""
    template = "plotly_dark" if dark else "plotly_white"
    fig      = go.Figure()

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
        title=f"{name} — MACD (12/26/9)",
        height=250, template=template,
        legend=dict(orientation="h", y=1.15),
        margin=dict(l=10, r=10, t=50, b=10),
        barmode="relative",
    )
    return fig


def backtest_curve_chart(
    results: list[dict],
    name: str,
    start_capital: float = 10_000,
    dark: bool = True,
) -> go.Figure:
    """
    Vergelijkingsgrafiek voor meerdere strategieën + buy-and-hold.
    `results` is een lijst van dicts met keys: label, curve (pd.Series), color.
    """
    template = "plotly_dark" if dark else "plotly_white"
    fig = go.Figure()

    for r in results:
        fig.add_trace(go.Scatter(
            x=r["curve"].index, y=r["curve"],
            name=r["label"],
            line=dict(color=r["color"], width=2,
                      dash=r.get("dash", "solid")),
        ))

    fig.add_hline(y=start_capital, line_dash="dash",
                  line_color="#6b7280", annotation_text="Startkapitaal")

    fig.update_layout(
        title=f"{name} — Strategie vergelijking (€{start_capital:,.0f})",
        yaxis_tickprefix="€",
        height=380, template=template,
        legend=dict(orientation="h", y=1.08),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    return fig
