"""
AEX Aandelen Dashboard — Streamlit

Starten:
    streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from data_fetcher import fetch_ticker, fetch_all
from indicators import add_indicators
from signals import build_summary, latest_signals
from backtest import run_backtest
from charts import price_chart, rsi_chart, macd_chart, backtest_curve_chart
from config import TICKERS

START_CAPITAL = 10_000

# ---------------------------------------------------------------------------
# Pagina-instellingen
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AEX Analyse Dashboard",
    page_icon="📈",
    layout="wide",
)

st.title("📈 AEX Aandelen Analyse Dashboard")
st.caption(f"Laatste update: {datetime.now().strftime('%d-%m-%Y %H:%M')}")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Instellingen")

    # Ververs-knop
    if st.button("🔄 Data verversen", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    # Keuze: bestaand aandeel of eigen ticker
    mode = st.radio("Aandeel kiezen", ["AEX-lijst", "Eigen ticker"])

    if mode == "AEX-lijst":
        selected_name = st.selectbox("Aandeel", list(TICKERS.keys()))
        selected_symbol = TICKERS[selected_name]
    else:
        custom = st.text_input(
            "Yahoo Finance ticker",
            placeholder="bijv. INGA.AS, ADYEN.AS, NVDA",
        ).strip().upper()
        selected_name   = custom or "—"
        selected_symbol = custom

    st.divider()
    period = st.select_slider(
        "Periode historische data",
        options=["6mo", "1y", "2y", "3y", "5y"],
        value="3y",
    )

# ---------------------------------------------------------------------------
# Data ophalen (gecached)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner="Data ophalen...")
def load_ticker(name: str, symbol: str, period: str):
    """Laad en verrijk data voor één ticker."""
    import yfinance as yf
    import pandas as pd

    try:
        df = yf.download(symbol, period=period, interval="1d",
                         progress=False, auto_adjust=True)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index)
    except Exception:
        return None

    return add_indicators(df)


@st.cache_data(ttl=3600, show_spinner="Alle aandelen laden...")
def load_all(period: str):
    """Laad en verrijk alle AEX-aandelen voor het overzicht."""
    raw = fetch_all()
    return {name: add_indicators(df) for name, df in raw.items()}

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_signals, tab_backtest, tab_overview = st.tabs(
    ["📊 Technische signalen", "🧪 Backtest", "🗂️ Overzicht alle aandelen"]
)

# ── Tab 1: Technische signalen ──────────────────────────────────────────────
with tab_signals:
    if not selected_symbol:
        st.info("Voer een ticker in via de sidebar.")
    else:
        df = load_ticker(selected_name, selected_symbol, period)

        if df is None:
            st.error(f"Geen data gevonden voor **{selected_symbol}**. "
                     "Controleer de ticker op Yahoo Finance.")
        else:
            # Signalen-samenvatting
            try:
                sig = latest_signals(selected_name, df)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Koers", f"€{sig['Koers']:.2f}")
                rsi_val = sig["RSI"]
                rsi_label = sig["RSI-signaal"].upper()
                rsi_delta_color = (
                    "inverse" if rsi_label == "OVERBOUGHT"
                    else "normal" if rsi_label == "OVERSOLD"
                    else "off"
                )
                c2.metric("RSI", f"{rsi_val}", rsi_label,
                          delta_color=rsi_delta_color)
                c3.metric("MACD-signaal", sig["MACD-signaal"].capitalize())
                c4.metric("Trend", sig["Trend"].split("(")[0].strip())
            except Exception:
                pass

            st.divider()

            # Grafieken
            st.plotly_chart(price_chart(df, selected_name),
                            use_container_width=True)

            col_rsi, col_macd = st.columns(2)
            with col_rsi:
                st.plotly_chart(rsi_chart(df, selected_name),
                                use_container_width=True)
            with col_macd:
                st.plotly_chart(macd_chart(df, selected_name),
                                use_container_width=True)

            # Ruwe data (inklapbaar)
            with st.expander("Ruwe data bekijken"):
                st.dataframe(
                    df[["Close", "Volume", "RSI_14",
                        "MACD", "MACD_signal",
                        f"SMA_50", f"SMA_200"]
                    ].tail(30).sort_index(ascending=False),
                    use_container_width=True,
                )

# ── Tab 2: Backtest ─────────────────────────────────────────────────────────
with tab_backtest:
    if not selected_symbol:
        st.info("Voer een ticker in via de sidebar.")
    else:
        df = load_ticker(selected_name, selected_symbol, period)

        if df is None:
            st.error(f"Geen data voor **{selected_symbol}**.")
        else:
            try:
                result = run_backtest(selected_name, df, START_CAPITAL)
                s = result["summary"]
                trades = result["trades"]

                # KPI-rij
                c1, c2, c3, c4, c5 = st.columns(5)
                strat_ret = s["Rendement strategie %"]
                bh_ret    = s["Rendement buy-hold %"]
                c1.metric("Rendement strategie",
                          f"{strat_ret:+.1f}%",
                          f"{strat_ret - bh_ret:+.1f}% vs B&H",
                          delta_color="normal")
                c2.metric("Buy & Hold", f"{bh_ret:+.1f}%")
                c3.metric("Max drawdown", f"{s['Max drawdown %']:.1f}%")
                c4.metric("Trades", s["Aantal trades"])
                c5.metric("Win-ratio",
                          f"{s['Win-ratio %']}%" if s["Win-ratio %"] else "—")

                st.divider()

                # Portfolio-curve
                st.plotly_chart(
                    backtest_curve_chart(
                        result["curve_strategy"],
                        result["curve_buyhold"],
                        selected_name,
                        START_CAPITAL,
                    ),
                    use_container_width=True,
                )

                # Trade-tabel
                if not trades.empty:
                    st.subheader("Individuele trades")
                    display_cols = [c for c in
                        ["entry_date", "exit_date", "entry_price",
                         "exit_price", "return_pct", "result", "open"]
                        if c in trades.columns]

                    def _color_result(val):
                        if val == "win":
                            return "color: #26a69a"
                        if val == "loss":
                            return "color: #ef5350"
                        return ""

                    st.dataframe(
                        trades[display_cols].style.map(
                            _color_result, subset=["result"]
                        ),
                        use_container_width=True,
                    )
                else:
                    st.info("Geen trades gegenereerd in deze periode "
                            "(te weinig crossovers).")

            except ValueError as exc:
                st.warning(f"Backtest niet mogelijk: {exc}")

# ── Tab 3: Overzicht alle aandelen ──────────────────────────────────────────
with tab_overview:
    with st.spinner("Alle AEX-aandelen laden..."):
        all_data = load_all(period)

    summary_df = build_summary(all_data)

    # Kleurcodering RSI-signaal
    def _highlight_rsi(val):
        if val == "OVERBOUGHT":
            return "background-color: #7f1d1d; color: white"
        if val == "OVERSOLD":
            return "background-color: #14532d; color: white"
        return ""

    st.subheader("Signaloverzicht (meest recente dag)")
    st.dataframe(
        summary_df.style.map(_highlight_rsi, subset=["RSI-signaal"]),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("Backtest vergelijking (MA Crossover vs Buy & Hold)")

    bt_rows = []
    for name, df in all_data.items():
        try:
            r = run_backtest(name, df, START_CAPITAL)
            s = r["summary"]
            bt_rows.append({
                "Aandeel":          name,
                "Strategie %":      s["Rendement strategie %"],
                "Buy & Hold %":     s["Rendement buy-hold %"],
                "Verschil %":       round(s["Rendement strategie %"] - s["Rendement buy-hold %"], 2),
                "Max Drawdown %":   s["Max drawdown %"],
                "Trades":           s["Aantal trades"],
                "Win-ratio %":      s["Win-ratio %"],
            })
        except Exception:
            pass

    if bt_rows:
        bt_df = pd.DataFrame(bt_rows)

        def _color_verschil(val):
            try:
                return "color: #26a69a" if float(val) >= 0 else "color: #ef5350"
            except Exception:
                return ""

        st.dataframe(
            bt_df.style.map(_color_verschil, subset=["Verschil %"]),
            use_container_width=True,
            hide_index=True,
        )
