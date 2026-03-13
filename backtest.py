"""
Backtesting engine: Moving Average Crossover strategie.

Strategie:
  - Koop wanneer SMA-50 de SMA-200 van onder kruist (golden cross)
  - Verkoop wanneer SMA-50 de SMA-200 van boven kruist (death cross)
  - Volledig geïnvesteerd (100%) of volledig cash — geen gedeeltelijke posities
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from config import MA_SHORT, MA_LONG


# ---------------------------------------------------------------------------
# Signalen genereren
# ---------------------------------------------------------------------------

def _generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Voeg koop/verkoop-signalen toe op basis van MA-crossover."""
    sma_s = f"SMA_{MA_SHORT}"
    sma_l = f"SMA_{MA_LONG}"

    if sma_s not in df.columns or sma_l not in df.columns:
        raise ValueError(f"Kolommen {sma_s} en/of {sma_l} ontbreken. "
                         "Roep eerst add_indicators() aan.")

    df = df.copy()
    df["_above"] = (df[sma_s] > df[sma_l]).astype(int)
    # Crossover: 1 = golden cross (koop), -1 = death cross (verkoop)
    df["signal"] = df["_above"].diff()
    df.drop(columns=["_above"], inplace=True)
    return df


# ---------------------------------------------------------------------------
# Trades reconstrueren
# ---------------------------------------------------------------------------

def _extract_trades(df: pd.DataFrame) -> list[dict]:
    """
    Loop door signalen en bouw een lijst van trades:
    elke trade heeft een koop- en verkoopprijs + rendement.
    """
    trades = []
    entry_price = None
    entry_date = None
    in_position = False

    for date, row in df.iterrows():
        sig = row["signal"]
        price = row["Close"]

        if sig == 1 and not in_position:          # golden cross → kopen
            entry_price = price
            entry_date = date
            in_position = True

        elif sig == -1 and in_position:            # death cross → verkopen
            ret = (price - entry_price) / entry_price
            trades.append({
                "entry_date":  entry_date,
                "exit_date":   date,
                "entry_price": round(float(entry_price), 4),
                "exit_price":  round(float(price), 4),
                "return_pct":  round(ret * 100, 2),
                "result":      "win" if ret > 0 else "loss",
            })
            in_position = False

    # Open positie aan het einde: sluit op laatste koers
    if in_position:
        price = df["Close"].iloc[-1]
        date  = df.index[-1]
        ret   = (price - entry_price) / entry_price
        trades.append({
            "entry_date":  entry_date,
            "exit_date":   date,
            "entry_price": round(float(entry_price), 4),
            "exit_price":  round(float(price), 4),
            "return_pct":  round(ret * 100, 2),
            "result":      "win" if ret > 0 else "loss",
            "open":        True,
        })

    return trades


# ---------------------------------------------------------------------------
# Portfolio-waardeverloop berekenen
# ---------------------------------------------------------------------------

def _portfolio_curve(df: pd.DataFrame, start_capital: float = 10_000) -> pd.Series:
    """
    Bereken dagelijkse portfoliowaarde voor de strategie.
    Buiten een positie staat het kapitaal stil (cash, geen rente).
    """
    df = df.copy()
    sma_s = f"SMA_{MA_SHORT}"
    sma_l = f"SMA_{MA_LONG}"

    # Positie: 1 als boven crossover, 0 anders (vertraagd met 1 dag)
    df["position"] = (df[sma_s] > df[sma_l]).astype(int).shift(1).fillna(0)
    daily_ret = df["Close"].pct_change().fillna(0)
    strat_ret = df["position"] * daily_ret

    curve = start_capital * (1 + strat_ret).cumprod()
    return curve


def _buyhold_curve(df: pd.DataFrame, start_capital: float = 10_000) -> pd.Series:
    """Buy-and-hold: koop op de eerste dag, houd tot het einde."""
    daily_ret = df["Close"].pct_change().fillna(0)
    return start_capital * (1 + daily_ret).cumprod()


# ---------------------------------------------------------------------------
# Metrics berekenen
# ---------------------------------------------------------------------------

def _max_drawdown(curve: pd.Series) -> float:
    """Maximum drawdown in procenten."""
    roll_max = curve.cummax()
    drawdown = (curve - roll_max) / roll_max
    return round(float(drawdown.min() * 100), 2)


def _total_return(curve: pd.Series, start_capital: float = 10_000) -> float:
    return round((float(curve.iloc[-1]) / start_capital - 1) * 100, 2)


def _win_loss(trades: list[dict]) -> dict:
    if not trades:
        return {"wins": 0, "losses": 0, "ratio": None}
    wins   = sum(1 for t in trades if t["result"] == "win")
    losses = sum(1 for t in trades if t["result"] == "loss")
    ratio  = round(wins / len(trades) * 100, 1)
    return {"wins": wins, "losses": losses, "ratio": ratio}


# ---------------------------------------------------------------------------
# Publieke interface
# ---------------------------------------------------------------------------

def run_backtest(
    name: str,
    df: pd.DataFrame,
    start_capital: float = 10_000,
) -> dict:
    """
    Voert de MA-crossover backtest uit voor één aandeel.

    Geeft een dict terug met:
      - summary: de belangrijkste metrics
      - trades:  lijst van individuele trades (als DataFrame)
      - curve_strategy: dagelijkse portfoliowaarde (Series)
      - curve_buyhold:  dagelijkse buy-and-hold waarde (Series)
    """
    df = _generate_signals(df)

    trades       = _extract_trades(df)
    curve_strat  = _portfolio_curve(df, start_capital)
    curve_bh     = _buyhold_curve(df, start_capital)
    wl           = _win_loss(trades)

    summary = {
        "Naam":                  name,
        "Periode":               f"{df.index[0].date()} → {df.index[-1].date()}",
        "Startkapitaal":         f"€{start_capital:,.0f}",
        "Eindwaarde strategie":  f"€{curve_strat.iloc[-1]:,.2f}",
        "Eindwaarde buy-hold":   f"€{curve_bh.iloc[-1]:,.2f}",
        "Rendement strategie %": _total_return(curve_strat, start_capital),
        "Rendement buy-hold %":  _total_return(curve_bh, start_capital),
        "Max drawdown %":        _max_drawdown(curve_strat),
        "Aantal trades":         len(trades),
        "Wins":                  wl["wins"],
        "Losses":                wl["losses"],
        "Win-ratio %":           wl["ratio"],
    }

    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()

    return {
        "summary":          summary,
        "trades":           trades_df,
        "curve_strategy":   curve_strat,
        "curve_buyhold":    curve_bh,
    }
