"""
AEX Aandelen Dashboard — Streamlit

Starten:
    python -m streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data_fetcher import fetch_all
from indicators import add_indicators
from signals import build_summary, latest_signals
from backtest import run_backtest, run_rsi_backtest, max_drawdown
from charts import price_chart, rsi_chart, macd_chart, backtest_curve_chart
from config import TICKERS
from screener import scan_alle

START_CAPITAL = 10_000

# ---------------------------------------------------------------------------
# Pagina-instellingen
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AEX Analyse Dashboard",
    page_icon="📈",
    layout="wide",
)

# Uitleg van indicatoren (voor beginners)
UITLEG = {
    "RSI": """
**RSI (Relative Strength Index)** meet hoe snel en sterk een koers beweegt.
- **Boven 70**: aandeel is mogelijk *overbought* — te snel gestegen, correctie mogelijk
- **Onder 30**: aandeel is mogelijk *oversold* — te snel gedaald, herstel mogelijk
- **Neutraal (30–70)**: geen extreem signaal
""",
    "MACD": """
**MACD (Moving Average Convergence Divergence)** laat zien of de trend versterkt of verzwakt.
- **MACD-lijn boven signaallijn**: bullish momentum (koers stijgt)
- **MACD-lijn onder signaallijn**: bearish momentum (koers daalt)
- **Histogram**: hoe groot het verschil is — groter = sterker signaal
""",
    "Bollinger Bands": """
**Bollinger Bands** tonen de normale prijsbandbreedte rondom een gemiddelde.
- **Koers raakt bovenband**: mogelijk overbought, of juist uitbraak omhoog
- **Koers raakt onderband**: mogelijk oversold, of uitbraak omlaag
- **Smalle banden**: lage volatiliteit — vaak voorloper van een grote beweging
""",
    "MA Crossover": """
**Moving Average Crossover** vergelijkt twee gemiddelden:
- **Golden Cross** (SMA-50 kruist SMA-200 omhoog): klassiek koopsignaal
- **Death Cross** (SMA-50 kruist SMA-200 omlaag): klassiek verkoopsignaal
- Werkt het beste over langere periodes en in trending markten
""",
    "Backtest": """
**Backtesting** simuleert hoe een strategie in het *verleden* zou hebben gepresteerd.
- Het is **geen garantie** voor de toekomst
- Vergelijk altijd met buy-and-hold als benchmark
- Let op **max drawdown** — hoe diep ging de dip?
""",
}

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Instellingen")

    # Dag/nacht modus
    dark_mode = st.toggle("Donker thema", value=True)

    st.divider()

    # Auto-refresh
    import time
    auto_refresh = st.toggle("Auto-refresh", value=False)
    if auto_refresh:
        interval_label = st.selectbox(
            "Interval",
            ["5 minuten", "15 minuten", "30 minuten", "1 uur", "4 uur"],
            index=2,
        )
        interval_secs = {
            "5 minuten": 300, "15 minuten": 900,
            "30 minuten": 1800, "1 uur": 3600, "4 uur": 14400,
        }[interval_label]

        if "last_refresh" not in st.session_state:
            st.session_state["last_refresh"] = time.time()
        elif time.time() - st.session_state["last_refresh"] > interval_secs:
            st.cache_data.clear()
            st.session_state["last_refresh"] = time.time()
            st.rerun()

        elapsed  = time.time() - st.session_state["last_refresh"]
        remaining = max(0, int((interval_secs - elapsed) / 60))
        secs_rem  = max(0, int((interval_secs - elapsed) % 60))
        st.caption(f"Volgende refresh over ~{remaining}m {secs_rem}s")

    if st.button("🔄 Nu verversen", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    # Aandeel kiezen
    mode = st.radio("Aandeel kiezen", ["AEX-lijst", "Eigen ticker"])
    if mode == "AEX-lijst":
        selected_name   = st.selectbox("Aandeel", list(TICKERS.keys()))
        selected_symbol = TICKERS[selected_name]
    else:
        custom = st.text_input(
            "Yahoo Finance ticker",
            placeholder="bijv. ADYEN.AS, NVDA, AAPL",
        ).strip().upper()
        selected_name   = custom or "—"
        selected_symbol = custom

    st.divider()

    period = st.select_slider(
        "Periode historische data",
        options=["6mo", "1y", "2y", "3y", "5y"],
        value="3y",
    )

    show_bb = st.checkbox("Bollinger Bands tonen", value=True)

    st.divider()
    st.caption(f"Laatste update: {datetime.now().strftime('%d-%m-%Y %H:%M')}")

# CSS voor licht thema override
if not dark_mode:
    st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #1e293b; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Data ophalen (gecached)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner="Data ophalen...")
def load_ticker(symbol: str, period: str):
    try:
        df = yf.download(symbol, period=period, interval="1d",
                         progress=False, auto_adjust=True)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index)
        return add_indicators(df)
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner="Alle AEX-aandelen laden...")
def load_all(period: str):
    raw = fetch_all()
    return {name: add_indicators(df) for name, df in raw.items()}


@st.cache_data(ttl=1800, show_spinner="Nieuws ophalen...")
def load_nieuws(symbol: str, max_items: int = 8) -> list:
    """Haalt nieuws op via yfinance. Normaliseert de nieuwe API-structuur."""
    try:
        ticker = yf.Ticker(symbol)
        raw = ticker.news or []
        items = []
        for n in raw[:max_items]:
            # Nieuwe structuur: content is genest in 'content'-key
            c = n.get("content", n)
            pub = c.get("provider", {})
            url_obj = c.get("canonicalUrl") or c.get("clickThroughUrl") or {}
            pub_date = c.get("pubDate", "")
            try:
                ts = int(datetime.strptime(pub_date[:19], "%Y-%m-%dT%H:%M:%S").timestamp())
            except Exception:
                ts = 0
            items.append({
                "title":               c.get("title", "Geen titel"),
                "link":                url_obj.get("url", "#"),
                "publisher":           pub.get("displayName", "") if isinstance(pub, dict) else str(pub),
                "summary":             c.get("summary", ""),
                "providerPublishTime": ts,
            })
        return items
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner="Intraday data ophalen...")  # 5 min cache
def load_intraday(symbol: str, interval: str = "5m"):
    """
    Haalt intraday koersdata op via yfinance.
    Vertraging: ~15 minuten (Yahoo Finance limiet).
    Beschikbare intervallen: 1m (7d), 5m (60d), 15m (60d), 1h (730d)
    """
    try:
        period = "1d" if interval in ("1m", "5m", "15m") else "5d"
        df = yf.download(symbol, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_live, tab_signals, tab_backtest, tab_overview, tab_screener, tab_uitleg = st.tabs([
    "📡 Live koers",
    "📊 Technische signalen",
    "🧪 Backtest",
    "🗂️ Overzicht AEX",
    "🎯 Strategiematches",
    "📚 Wat betekent dit?",
])

# ── Tab 0: Live koers ────────────────────────────────────────────────────────
with tab_live:
    st.title(f"📡 Live koers — {selected_name}")
    st.caption("⚠️ Data via Yahoo Finance heeft ~15 minuten vertraging. "
               "Buiten handelstijd zie je de laatste beschikbare koers.")

    if not selected_symbol:
        st.info("Voer een ticker in via de sidebar.")
    else:
        # Interval-keuze
        col_int, col_ref = st.columns([3, 1])
        with col_int:
            intraday_interval = st.radio(
                "Interval",
                ["1m", "5m", "15m", "1h"],
                index=1,
                horizontal=True,
                captions=["1 min (vandaag)", "5 min (vandaag)",
                          "15 min (vandaag)", "1 uur (5 dagen)"],
            )
        with col_ref:
            st.write("")
            if st.button("🔄 Verversen", key="live_refresh"):
                st.cache_data.clear()
                st.rerun()

        df_intra = load_intraday(selected_symbol, intraday_interval)

        if df_intra is None or df_intra.empty:
            st.warning("Geen intraday data beschikbaar. "
                       "De markt is mogelijk gesloten of de ticker is onbekend.")
        else:
            # KPI's
            last      = df_intra.iloc[-1]
            first     = df_intra.iloc[0]
            cur_price = float(last["Close"])
            day_open  = float(first["Open"])
            day_high  = float(df_intra["High"].max())
            day_low   = float(df_intra["Low"].min())
            change    = cur_price - day_open
            change_pct = (change / day_open) * 100

            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Huidige koers",  f"€{cur_price:.2f}",
                      f"{change:+.2f} ({change_pct:+.2f}%)",
                      delta_color="normal" if change >= 0 else "inverse")
            k2.metric("Daghoog",  f"€{day_high:.2f}")
            k3.metric("Daglaag",  f"€{day_low:.2f}")
            k4.metric("Opening",  f"€{day_open:.2f}")
            k5.metric("Laatste update",
                      df_intra.index[-1].strftime("%H:%M"),
                      "~15 min vertraging", delta_color="off")

            st.divider()

            # Intraday candlestick grafiek
            template = "plotly_dark" if dark_mode else "plotly_white"
            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                row_heights=[0.75, 0.25], vertical_spacing=0.02,
            )
            fig.add_trace(go.Candlestick(
                x=df_intra.index,
                open=df_intra["Open"], high=df_intra["High"],
                low=df_intra["Low"],   close=df_intra["Close"],
                name="Koers",
                increasing_line_color="#26a69a",
                decreasing_line_color="#ef5350",
            ), row=1, col=1)

            # Daggemiddelde lijn
            avg = df_intra["Close"].mean()
            fig.add_hline(y=avg, line_dash="dot", line_color="#f59e0b",
                          annotation_text=f"Gem. €{avg:.2f}", row=1, col=1)

            # Volume
            if "Volume" in df_intra.columns:
                vol_colors = [
                    "#26a69a" if c >= o else "#ef5350"
                    for c, o in zip(df_intra["Close"], df_intra["Open"])
                ]
                fig.add_trace(go.Bar(
                    x=df_intra.index, y=df_intra["Volume"],
                    name="Volume", marker_color=vol_colors,
                    opacity=0.6, showlegend=False,
                ), row=2, col=1)

            fig.update_layout(
                title=f"{selected_name} — Intraday ({intraday_interval}, ~15 min vertraging)",
                xaxis_rangeslider_visible=False,
                height=500, template=template,
                margin=dict(l=10, r=10, t=60, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Ruwe intraday data
            with st.expander("📋 Intraday data"):
                st.dataframe(
                    df_intra[["Open", "High", "Low", "Close", "Volume"]]
                    .sort_index(ascending=False),
                    use_container_width=True,
                )


# ── Tab 1: Technische signalen ───────────────────────────────────────────────
with tab_signals:
    st.title(f"📈 {selected_name}")

    if not selected_symbol:
        st.info("Voer een ticker in via de sidebar.")
    else:
        df = load_ticker(selected_symbol, period)

        if df is None:
            st.error(f"Geen data gevonden voor **{selected_symbol}**.")
        else:
            # KPI-metrics
            try:
                sig = latest_signals(selected_name, df)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Koers", f"€{sig['Koers']:.2f}")

                rsi_val   = sig["RSI"]
                rsi_label = sig["RSI-signaal"].upper()
                delta_col = ("inverse" if rsi_label == "OVERBOUGHT"
                             else "normal" if rsi_label == "OVERSOLD" else "off")
                c2.metric("RSI", f"{rsi_val}", rsi_label, delta_color=delta_col)
                c3.metric("MACD", sig["MACD-signaal"].capitalize())
                c4.metric("Trend", sig["Trend"].split("(")[0].strip())
            except Exception:
                pass

            # ── Signaaluitleg (contextgebonden) ──────────────────────────────
            try:
                rsi_val    = sig["RSI"]
                macd_sig_v = sig["MACD-signaal"]
                trend_v    = sig["Trend"]
                rsi_signal = sig["RSI-signaal"]

                # RSI-tekst
                if rsi_signal == "OVERBOUGHT":
                    rsi_kleur = "🔴"
                    rsi_tekst = (
                        f"**RSI {rsi_val} — Overbought (>70)**  \n"
                        "De koers is de afgelopen periode sterk gestegen. "
                        "Een RSI boven 70 betekent dat het aandeel mogelijk *te snel gestegen* is. "
                        "Dit hoeft geen crash te betekenen, maar de kans op een correctie neemt toe.  \n"
                        "💡 *Advies: wacht op een daling of bevestiging voordat je instapt.*"
                    )
                elif rsi_signal == "OVERSOLD":
                    rsi_kleur = "🟢"
                    rsi_tekst = (
                        f"**RSI {rsi_val} — Oversold (<30)**  \n"
                        "De koers is de afgelopen periode sterk gedaald. "
                        "Een RSI onder 30 kan wijzen op een *overdreven daling* — de koers kan terugveren. "
                        "Maar een dalende trend kan ook aanhouden.  \n"
                        "💡 *Advies: mogelijk koopkans, maar wacht op een bevestiging van herstel.*"
                    )
                elif isinstance(rsi_val, float) and 40 <= rsi_val <= 65:
                    rsi_kleur = "🟡"
                    rsi_tekst = (
                        f"**RSI {rsi_val} — Momentum koopzone (40–65)**  \n"
                        "De RSI zit in een gezonde zone: niet overbought, niet oversold. "
                        "Dit is vaak een gunstig instapgebied voor momentumbeleggers.  \n"
                        "💡 *Advies: combineer met andere signalen (MACD, trend) voor bevestiging.*"
                    )
                else:
                    rsi_kleur = "⚪"
                    rsi_tekst = (
                        f"**RSI {rsi_val} — Neutraal**  \n"
                        "Geen uitgesproken signaal. De koers beweegt in een normaal tempo.  \n"
                        "💡 *Advies: wacht op een duidelijker signaal.*"
                    )

                # MACD-tekst
                if macd_sig_v == "bullish":
                    macd_kleur = "🟢"
                    macd_tekst = (
                        "**MACD — Bullish**  \n"
                        "De MACD-lijn staat boven de signaallijn. "
                        "Dit betekent dat het *kortetermijnmomentum sterker is dan het langetermijngemiddelde* — "
                        "een teken dat de koers aan kracht wint.  \n"
                        "💡 *Advies: dit is een positief teken, zeker in combinatie met een golden cross.*"
                    )
                elif macd_sig_v == "bearish":
                    macd_kleur = "🔴"
                    macd_tekst = (
                        "**MACD — Bearish**  \n"
                        "De MACD-lijn staat onder de signaallijn. "
                        "Het momentum verzwakt — de koers verliest kracht.  \n"
                        "💡 *Advies: wees voorzichtig met instappen; wacht tot de MACD omslaat naar bullish.*"
                    )
                else:
                    macd_kleur = "⚪"
                    macd_tekst = "**MACD — Onbekend**  \nOnvoldoende data beschikbaar."

                # Trend-tekst
                if "golden" in trend_v:
                    trend_kleur = "🟢"
                    trend_tekst = (
                        "**Trend — Golden Cross**  \n"
                        "De SMA-50 staat boven de SMA-200. "
                        "Dit is het klassieke *koopsignaal op langere termijn*. "
                        "De kortetermijntrend is sterker dan de langetermijntrend.  \n"
                        "💡 *Advies: positieve trend — ondersteunt een koopbeslissing.*"
                    )
                elif "death" in trend_v:
                    trend_kleur = "🔴"
                    trend_tekst = (
                        "**Trend — Death Cross**  \n"
                        "De SMA-50 staat onder de SMA-200. "
                        "Dit is het klassieke *verkoopsignaal op langere termijn*. "
                        "De kortetermijntrend is zwakker dan de langetermijntrend.  \n"
                        "💡 *Advies: wees voorzichtig — de langetermijntrend is bearish.*"
                    )
                else:
                    trend_kleur = "⚪"
                    trend_tekst = "**Trend — Onbekend**  \nOnvoldoende data beschikbaar."

                st.subheader("🔍 Wat betekenen deze signalen nu?")
                col_rsi_u, col_macd_u, col_trend_u = st.columns(3)
                with col_rsi_u:
                    st.markdown(f"{rsi_kleur} {rsi_tekst}")
                with col_macd_u:
                    st.markdown(f"{macd_kleur} {macd_tekst}")
                with col_trend_u:
                    st.markdown(f"{trend_kleur} {trend_tekst}")

            except Exception:
                pass

            st.divider()

            # Koersgrafiek
            st.plotly_chart(
                price_chart(df, selected_name, show_bb=show_bb, dark=dark_mode),
                use_container_width=True,
            )

            # RSI + MACD naast elkaar
            col_rsi, col_macd = st.columns(2)
            with col_rsi:
                st.plotly_chart(rsi_chart(df, selected_name, dark=dark_mode),
                                use_container_width=True)
            with col_macd:
                st.plotly_chart(macd_chart(df, selected_name, dark=dark_mode),
                                use_container_width=True)

            with st.expander("📋 Ruwe data (laatste 30 dagen)"):
                cols = [c for c in ["Close", "Volume", "RSI_14", "MACD",
                                    "MACD_signal", "SMA_50", "SMA_200",
                                    "BB_upper", "BB_lower"] if c in df.columns]
                st.dataframe(df[cols].tail(30).sort_index(ascending=False),
                             use_container_width=True)

            st.divider()

            # Nieuws
            st.subheader(f"📰 Laatste nieuws — {selected_name}")
            nieuws = load_nieuws(selected_symbol)
            if not nieuws:
                st.info("Geen recent nieuws gevonden.")
            else:
                for item in nieuws:
                    ts = item.get("providerPublishTime", 0)
                    datum = datetime.fromtimestamp(ts).strftime("%d-%m-%Y %H:%M") if ts else "—"
                    titel = item.get("title", "Geen titel")
                    url   = item.get("link", "#")
                    bron  = item.get("publisher", "")
                    st.markdown(
                        f"**[{titel}]({url})**  \n"
                        f"<span style='color:gray;font-size:0.85em'>{bron} · {datum}</span>",
                        unsafe_allow_html=True,
                    )

# ── Tab 2: Backtest ──────────────────────────────────────────────────────────
with tab_backtest:
    st.title(f"🧪 Backtest — {selected_name}")

    if not selected_symbol:
        st.info("Voer een ticker in via de sidebar.")
    else:
        df = load_ticker(selected_symbol, period)

        if df is None:
            st.error(f"Geen data voor **{selected_symbol}**.")
        else:
            try:
                r_ma  = run_backtest(selected_name, df, START_CAPITAL)
                r_rsi = run_rsi_backtest(selected_name, df, START_CAPITAL)

                # --- KPI-vergelijking ---
                st.subheader("Strategie vergelijking")
                kpi_cols = st.columns(3)
                for col, result, label in zip(
                    kpi_cols,
                    [r_ma, r_rsi],
                    ["MA Crossover", "RSI Strategie"],
                ):
                    s = result["summary"]
                    with col:
                        st.markdown(f"**{label}**")
                        st.metric("Rendement", f"{s['Rendement strategie %']:+.1f}%",
                                  f"{s['Rendement strategie %'] - s['Rendement buy-hold %']:+.1f}% vs B&H")
                        st.metric("Max Drawdown", f"{s['Max drawdown %']:.1f}%")
                        st.metric("Win-ratio",
                                  f"{s['Win-ratio %']}%" if s["Win-ratio %"] else "—")
                        st.metric("Trades", s["Aantal trades"])

                with kpi_cols[2]:
                    st.markdown("**Buy & Hold**")
                    st.metric("Rendement", f"{r_ma['summary']['Rendement buy-hold %']:+.1f}%")
                    st.metric("Max Drawdown", f"{max_drawdown(r_ma['curve_buyhold']):.1f}%")

                st.divider()

                # --- Portfolio-curve grafiek ---
                curve_data = [
                    {"label": "MA Crossover",  "curve": r_ma["curve_strategy"],
                     "color": "#38bdf8", "dash": "solid"},
                    {"label": "RSI Strategie", "curve": r_rsi["curve_strategy"],
                     "color": "#f59e0b", "dash": "solid"},
                    {"label": "Buy & Hold",    "curve": r_ma["curve_buyhold"],
                     "color": "#9ca3af", "dash": "dot"},
                ]
                st.plotly_chart(
                    backtest_curve_chart(curve_data, selected_name,
                                         START_CAPITAL, dark=dark_mode),
                    use_container_width=True,
                )

                # --- Trade-tabellen ---
                col_ma, col_rsi_t = st.columns(2)
                for col, result, label in [
                    (col_ma, r_ma, "MA Crossover trades"),
                    (col_rsi_t, r_rsi, "RSI Strategie trades"),
                ]:
                    with col:
                        st.subheader(label)
                        trades = result["trades"]
                        if not trades.empty:
                            show_cols = [c for c in
                                ["entry_date", "exit_date", "entry_price",
                                 "exit_price", "return_pct", "result"]
                                if c in trades.columns]
                            def _color(val):
                                return ("color: #26a69a" if val == "win"
                                        else "color: #ef5350" if val == "loss" else "")
                            st.dataframe(
                                trades[show_cols].style.map(_color, subset=["result"]),
                                use_container_width=True,
                            )
                        else:
                            st.info("Geen trades in deze periode.")

            except Exception as exc:
                st.warning(f"Backtest niet mogelijk: {exc}")

# ── Tab 3: Overzicht AEX ─────────────────────────────────────────────────────
with tab_overview:
    st.title("🗂️ AEX-25 Overzicht")

    with st.spinner("Alle aandelen laden (dit duurt ~30 seconden)..."):
        all_data = load_all(period)

    # Signalentabel
    summary_df = build_summary(all_data)

    def _hl_rsi(val):
        if val == "OVERBOUGHT": return "background-color:#7f1d1d;color:white"
        if val == "OVERSOLD":   return "background-color:#14532d;color:white"
        return ""

    st.subheader("Signalen (meest recente dag)")
    st.dataframe(
        summary_df.style.map(_hl_rsi, subset=["RSI-signaal"]),
        use_container_width=True, hide_index=True,
    )

    st.divider()

    # Backtest-vergelijking
    st.subheader("MA Crossover vs RSI Strategie vs Buy & Hold")
    bt_rows = []
    progress = st.progress(0)
    tickers_list = list(all_data.items())
    for i, (name, df) in enumerate(tickers_list):
        try:
            r_ma  = run_backtest(name, df, START_CAPITAL)
            r_rsi = run_rsi_backtest(name, df, START_CAPITAL)
            bt_rows.append({
                "Aandeel":        name,
                "MA %":           r_ma["summary"]["Rendement strategie %"],
                "RSI %":          r_rsi["summary"]["Rendement strategie %"],
                "Buy & Hold %":   r_ma["summary"]["Rendement buy-hold %"],
                "MA vs B&H":      round(r_ma["summary"]["Rendement strategie %"] -
                                        r_ma["summary"]["Rendement buy-hold %"], 1),
                "RSI vs B&H":     round(r_rsi["summary"]["Rendement strategie %"] -
                                        r_ma["summary"]["Rendement buy-hold %"], 1),
                "Max DD MA %":    r_ma["summary"]["Max drawdown %"],
            })
        except Exception:
            pass
        progress.progress((i + 1) / len(tickers_list))

    if bt_rows:
        bt_df = pd.DataFrame(bt_rows)
        def _color_diff(val):
            try:
                return "color:#26a69a" if float(val) >= 0 else "color:#ef5350"
            except Exception:
                return ""
        st.dataframe(
            bt_df.style.map(_color_diff, subset=["MA vs B&H", "RSI vs B&H"]),
            use_container_width=True, hide_index=True,
        )

    st.divider()

    # Correlatiematrix
    st.subheader("🔗 Correlatiematrix — dagrendementen")
    st.caption(
        "Waarden dicht bij **+1**: aandelen bewegen gelijktijdig (minder spreiding). "
        "Waarden dicht bij **0** of **-1**: betere spreiding in je portefeuille."
    )

    # Bouw een DataFrame van slotkoersen voor alle beschikbare aandelen
    close_df = pd.DataFrame({
        name: df["Close"].squeeze()
        for name, df in all_data.items()
        if "Close" in df.columns
    })
    returns_df = close_df.pct_change().dropna()
    corr = returns_df.corr().round(2)

    template_corr = "plotly_dark" if dark_mode else "plotly_white"
    fig_corr = go.Figure(go.Heatmap(
        z=corr.values,
        x=corr.columns.tolist(),
        y=corr.index.tolist(),
        colorscale="RdBu",
        zmid=0,
        zmin=-1, zmax=1,
        text=corr.values.round(2),
        texttemplate="%{text}",
        textfont=dict(size=9),
        colorbar=dict(title="Correlatie"),
    ))
    fig_corr.update_layout(
        height=600, template=template_corr,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(tickangle=-45),
    )
    st.plotly_chart(fig_corr, use_container_width=True)


# ── Tab 4: Strategiematches ──────────────────────────────────────────────────
with tab_screener:
    st.title("🎯 Strategiematches — Momentumscanner")
    st.markdown(
        "De scanner beoordeelt elk AEX-aandeel op **5 criteria**. "
        "Aandelen met de hoogste score voldoen aan de meeste voorwaarden voor momentum."
    )

    with st.expander("ℹ️ Hoe werkt de scanner?", expanded=False):
        st.markdown("""
| # | Criterium | Vereiste |
|---|-----------|---------|
| 1 | **RSI momentum** | RSI tussen 40–65 (koopzone zonder overbought), of net hersteld van oversold (<30 → >30) |
| 2 | **Relatief volume** | Huidig volume > 1,5× het 20-daags gemiddelde |
| 3 | **Nieuws aanwezig** | Minstens 1 nieuwsbericht in de afgelopen 3 dagen |
| 4 | **MACD bullish** | MACD-lijn staat boven de signaallijn |
| 5 | **Boven SMA-50** | Slotkoers staat boven het 50-daags voortschrijdend gemiddelde |
        """)

    st.divider()

    min_score = st.slider("Minimale score om te tonen", min_value=1, max_value=5, value=3)

    with st.spinner("Alle AEX-aandelen analyseren..."):
        all_data_sc = load_all(period)
        nieuws_map  = {}
        progress_sc = st.progress(0)
        ticker_items = list(TICKERS.items())
        for i, (name, symbol) in enumerate(ticker_items):
            nieuws_map[name] = load_nieuws(symbol)
            progress_sc.progress((i + 1) / len(ticker_items))

        matches = scan_alle(all_data_sc, nieuws_map, TICKERS, min_score=min_score)

    if not matches:
        st.info(f"Geen aandelen gevonden met score ≥ {min_score}. Verlaag de drempel.")
    else:
        st.success(f"**{len(matches)} aandelen** voldoen aan minimaal {min_score}/5 criteria.")

        # ── Overzichtstabel ──
        tabel_rows = []
        for r in matches:
            score = r["Score"]
            sterren = "⭐" * score + "☆" * (5 - score)
            tabel_rows.append({
                "Score": f"{score}/5  {sterren}",
                "Naam":   r["Naam"],
                "Ticker": r["Ticker"],
                "Koers":  f"€{r['Koers']:.2f}",
                "Gap %":  f"{r['Gap %']:+.2f}%",
                "Volume": f"{r['Volume']:,}",
                "RSI":    f"{r['RSI']:.1f}" if r["RSI"] else "—",
            })

        st.dataframe(pd.DataFrame(tabel_rows), use_container_width=True, hide_index=True)

        st.divider()

        # ── Detail per aandeel ──
        st.subheader("Detail per aandeel")
        for r in matches:
            score = r["Score"]
            with st.expander(f"**{r['Naam']}** ({r['Ticker']}) — {score}/5 criteria ✓"):
                col_info, col_check = st.columns([1, 2])

                with col_info:
                    st.metric("Koers",  f"€{r['Koers']:.2f}")
                    st.metric("Gap %",  f"{r['Gap %']:+.2f}%")
                    st.metric("Volume", f"{r['Volume']:,}")
                    if r["RSI"]:
                        st.metric("RSI", f"{r['RSI']:.1f}")

                with col_check:
                    st.markdown("**Criterium-checklist:**")
                    for criterium, (ok, uitleg) in r["checks"].items():
                        icoon = "✅" if ok else "❌"
                        st.markdown(f"{icoon} **{criterium}** — {uitleg}")

                # Laatste nieuws
                if r.get("nieuws"):
                    st.markdown("---")
                    st.markdown("**Recent nieuws:**")
                    for item in r["nieuws"]:
                        ts    = item.get("providerPublishTime", 0)
                        datum = datetime.fromtimestamp(ts).strftime("%d-%m-%Y") if ts else "—"
                        titel = item.get("title", "Geen titel")
                        url   = item.get("link", "#")
                        bron  = item.get("publisher", "")
                        st.markdown(
                            f"• **[{titel}]({url})**  "
                            f"<span style='color:gray;font-size:0.85em'>{bron} · {datum}</span>",
                            unsafe_allow_html=True,
                        )


# ── Tab 5: Uitleg ────────────────────────────────────────────────────────────
with tab_uitleg:
    st.title("📚 Wat betekenen deze indicatoren?")
    st.markdown(
        "Als je net begint met aandelen handelen, kunnen technische indicatoren "
        "overweldigend zijn. Hier vind je een simpele uitleg van alles wat dit "
        "dashboard gebruikt."
    )
    st.divider()

    for titel, tekst in UITLEG.items():
        with st.expander(f"📖 {titel}", expanded=False):
            st.markdown(tekst)

    st.divider()
    st.subheader("⚠️ Belangrijke kanttekeningen")
    st.warning("""
- Technische analyse is **geen kristallen bol** — het geeft kansen aan, geen zekerheden
- Backtesting laat zien hoe een strategie *in het verleden* had gewerkt, niet wat er *morgen* gebeurt
- Combineer altijd meerdere signalen — vertrouw nooit op één indicator
- Houd rekening met transactiekosten bij het handelen
- Dit dashboard is een **leermiddel**, geen beleggingsadvies
""")

    st.subheader("📖 Aanbevolen om verder te leren")
    st.markdown("""
- **Boek**: *Het grote boek van technische analyse* — Martin Pring
- **Gratis**: Investopedia.com heeft uitleg over elke indicator
- **Praktisch**: Probeer eerst met een papieren portefeuille (zonder echt geld)
""")
