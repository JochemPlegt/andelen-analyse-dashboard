"""
Backtesting engine — twee strategieën:

1. MA Crossover  : koop bij golden cross (SMA50 > SMA200), verkoop bij death cross
2. RSI Strategie : koop wanneer RSI de oversold-zone verlaat (< 30 → > 30),
                   verkoop wanneer RSI de overbought-zone verlaat (> 70 → < 70)
"""

from __future__ import annotations
import pandas as pd
from config import MA_SHORT, MA_LONG, RSI_OVERBOUGHT, RSI_OVERSOLD


# ---------------------------------------------------------------------------
# Gedeelde hulpfuncties
# ---------------------------------------------------------------------------

def _extract_trades(df: pd.DataFrame, signal_col: str) -> list[dict]:
    """Bouwt lijst van trades op basis van een signaalkolom (1=koop, -1=verkoop)."""
    trades = []
    entry_price = None
    entry_date  = None
    in_position = False

    for date, row in df.iterrows():
        sig   = row[signal_col]
        price = float(row["Close"])

        if sig == 1 and not in_position:
            entry_price = price
            entry_date  = date
            in_position = True
        elif sig == -1 and in_position:
            ret = (price - entry_price) / entry_price
            trades.append({
                "entry_date":  entry_date,
                "exit_date":   date,
                "entry_price": round(entry_price, 4),
                "exit_price":  round(price, 4),
                "return_pct":  round(ret * 100, 2),
                "result":      "win" if ret > 0 else "loss",
            })
            in_position = False

    if in_position:
        price = float(df["Close"].iloc[-1])
        ret   = (price - entry_price) / entry_price
        trades.append({
            "entry_date":  entry_date,
            "exit_date":   df.index[-1],
            "entry_price": round(entry_price, 4),
            "exit_price":  round(price, 4),
            "return_pct":  round(ret * 100, 2),
            "result":      "win" if ret > 0 else "loss",
            "open":        True,
        })
    return trades


def _portfolio_curve(df: pd.DataFrame, signal_col: str,
                     start_capital: float = 10_000) -> pd.Series:
    """Bouw positie op via signalen: 1=koop, -1=verkoop."""
    pos    = []
    in_pos = False
    for sig in df[signal_col]:
        if sig == 1:
            in_pos = True
        elif sig == -1:
            in_pos = False
        pos.append(1 if in_pos else 0)

    position  = pd.Series(pos, index=df.index).shift(1).fillna(0)
    daily_ret = df["Close"].pct_change().fillna(0)
    return start_capital * (1 + position * daily_ret).cumprod()


def max_drawdown(curve: pd.Series) -> float:
    """Publieke wrapper voor max drawdown (bruikbaar in dashboard)."""
    return _max_drawdown(curve)


def _buyhold_curve(df: pd.DataFrame, start_capital: float = 10_000) -> pd.Series:
    daily_ret = df["Close"].pct_change().fillna(0)
    return start_capital * (1 + daily_ret).cumprod()


def _max_drawdown(curve: pd.Series) -> float:
    roll_max  = curve.cummax()
    drawdown  = (curve - roll_max) / roll_max
    return round(float(drawdown.min() * 100), 2)


def _total_return(curve: pd.Series, start_capital: float) -> float:
    return round((float(curve.iloc[-1]) / start_capital - 1) * 100, 2)


def _win_loss(trades: list[dict]) -> dict:
    if not trades:
        return {"wins": 0, "losses": 0, "ratio": None}
    wins   = sum(1 for t in trades if t["result"] == "win")
    losses = len(trades) - wins
    return {"wins": wins, "losses": losses,
            "ratio": round(wins / len(trades) * 100, 1)}


def _build_summary(name, strategy_name, df, signal_col, start_capital):
    trades      = _extract_trades(df, signal_col)
    curve_strat = _portfolio_curve(df, signal_col, start_capital)
    curve_bh    = _buyhold_curve(df, start_capital)
    wl          = _win_loss(trades)
    return {
        "summary": {
            "Naam":                  name,
            "Strategie":             strategy_name,
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
        },
        "trades":         pd.DataFrame(trades) if trades else pd.DataFrame(),
        "curve_strategy": curve_strat,
        "curve_buyhold":  curve_bh,
    }


# ---------------------------------------------------------------------------
# Strategie 1: MA Crossover
# ---------------------------------------------------------------------------

def run_backtest(name: str, df: pd.DataFrame,
                 start_capital: float = 10_000) -> dict:
    """MA Crossover: koop bij golden cross, verkoop bij death cross."""
    sma_s = f"SMA_{MA_SHORT}"
    sma_l = f"SMA_{MA_LONG}"
    if sma_s not in df.columns or sma_l not in df.columns:
        raise ValueError(f"Kolommen {sma_s}/{sma_l} ontbreken.")

    df = df.copy()
    above       = (df[sma_s] > df[sma_l]).astype(int)
    df["_ma_sig"] = above.diff()
    # Zet als koop/verkoop: 1 bij golden cross, -1 bij death cross
    df["_ma_buy"]  = (df["_ma_sig"] == 1).astype(int)
    df["_ma_sell"] = (df["_ma_sig"] == -1).astype(int) * -1
    df["ma_signal"] = df["_ma_buy"] + df["_ma_sell"]

    return _build_summary(name, "MA Crossover", df, "ma_signal", start_capital)


# ---------------------------------------------------------------------------
# Strategie 2: RSI
# ---------------------------------------------------------------------------

def run_rsi_backtest(name: str, df: pd.DataFrame,
                     start_capital: float = 10_000) -> dict:
    """
    RSI-strategie:
      - Koop wanneer RSI de oversold-zone verlaat (kruist omhoog door RSI_OVERSOLD)
      - Verkoop wanneer RSI de overbought-zone verlaat (kruist omlaag door RSI_OVERBOUGHT)
    """
    rsi_col = "RSI_14"
    if rsi_col not in df.columns:
        raise ValueError(f"Kolom {rsi_col} ontbreekt.")

    df = df.copy()
    rsi = df[rsi_col]

    # Koop: RSI was ≤ oversold en is nu > oversold
    buy_signal  = ((rsi > RSI_OVERSOLD) & (rsi.shift(1) <= RSI_OVERSOLD)).astype(int)
    # Verkoop: RSI was ≥ overbought en is nu < overbought
    sell_signal = ((rsi < RSI_OVERBOUGHT) & (rsi.shift(1) >= RSI_OVERBOUGHT)).astype(int) * -1

    df["rsi_signal"] = buy_signal + sell_signal

    return _build_summary(name, "RSI Strategie", df, "rsi_signal", start_capital)
