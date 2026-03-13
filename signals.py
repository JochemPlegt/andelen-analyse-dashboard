"""Genereert handelssignalen op basis van indicatoren."""

import pandas as pd
from config import RSI_OVERBOUGHT, RSI_OVERSOLD, MA_SHORT, MA_LONG


def latest_signals(name: str, df: pd.DataFrame) -> dict:
    """
    Bepaalt signalen op basis van de meest recente rij.
    Geeft een dict terug met alle relevante waarden en signalen.
    """
    last = df.dropna(subset=[f"RSI_14", f"SMA_{MA_SHORT}"]).iloc[-1]
    close = last["Close"]
    rsi   = last.get("RSI_14", None)
    macd  = last.get("MACD", None)
    macd_sig = last.get("MACD_signal", None)
    sma50  = last.get(f"SMA_{MA_SHORT}", None)
    sma200 = last.get(f"SMA_{MA_LONG}", None)

    # RSI-signaal
    if rsi is None:
        rsi_signal = "onbekend"
    elif rsi >= RSI_OVERBOUGHT:
        rsi_signal = "OVERBOUGHT"
    elif rsi <= RSI_OVERSOLD:
        rsi_signal = "OVERSOLD"
    else:
        rsi_signal = "neutraal"

    # MACD-signaal
    if macd is None or macd_sig is None:
        macd_signal = "onbekend"
    elif macd > macd_sig:
        macd_signal = "bullish"
    else:
        macd_signal = "bearish"

    # Trend via golden/death cross
    if sma50 is None or sma200 is None:
        trend = "onbekend"
    elif sma50 > sma200:
        trend = "golden cross (bull)"
    else:
        trend = "death cross (bear)"

    return {
        "Naam":        name,
        "Koers":       round(float(close), 2),
        "RSI":         round(float(rsi), 1) if rsi is not None else "-",
        "RSI-signaal": rsi_signal,
        "MACD":        round(float(macd), 3) if macd is not None else "-",
        "MACD-signaal": macd_signal,
        f"SMA{MA_SHORT}":  round(float(sma50), 2) if sma50 is not None else "-",
        f"SMA{MA_LONG}":   round(float(sma200), 2) if sma200 is not None else "-",
        "Trend":       trend,
        "Datum":       df.dropna(subset=["RSI_14"]).index[-1].strftime("%Y-%m-%d"),
    }


def build_summary(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Bouwt een overzichtstabel van alle aandelen."""
    rows = []
    for name, df in data.items():
        try:
            rows.append(latest_signals(name, df))
        except Exception as exc:
            print(f"[WAARSCHUWING] Signalen voor {name} overgeslagen: {exc}")
    return pd.DataFrame(rows)
