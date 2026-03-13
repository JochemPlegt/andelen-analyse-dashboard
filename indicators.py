"""Berekent technische indicatoren met de 'ta' library."""

import pandas as pd
import ta
from config import (
    RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    MA_SHORT, MA_LONG,
)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Voegt RSI, MACD, SMA-50 en SMA-200 toe aan een OHLCV DataFrame.
    Geeft een nieuwe DataFrame terug (origineel ongewijzigd).
    """
    df = df.copy()

    close = df["Close"].squeeze()  # zorg dat het een Series is

    # RSI
    df[f"RSI_{RSI_PERIOD}"] = ta.momentum.RSIIndicator(
        close=close, window=RSI_PERIOD
    ).rsi()

    # MACD
    macd_ind = ta.trend.MACD(
        close=close,
        window_fast=MACD_FAST,
        window_slow=MACD_SLOW,
        window_sign=MACD_SIGNAL,
    )
    df["MACD"]        = macd_ind.macd()
    df["MACD_signal"] = macd_ind.macd_signal()
    df["MACD_hist"]   = macd_ind.macd_diff()

    # Moving averages
    df[f"SMA_{MA_SHORT}"] = ta.trend.SMAIndicator(close=close, window=MA_SHORT).sma_indicator()
    df[f"SMA_{MA_LONG}"]  = ta.trend.SMAIndicator(close=close, window=MA_LONG).sma_indicator()

    return df
