"""Haalt koersdata op via yfinance."""

import yfinance as yf
import pandas as pd
from config import TICKERS, PERIOD, INTERVAL


def fetch_ticker(name: str, symbol: str) -> pd.DataFrame | None:
    """Download OHLCV-data voor één ticker. Geeft None terug bij fout."""
    try:
        df = yf.download(symbol, period=PERIOD, interval=INTERVAL,
                         progress=False, auto_adjust=True)
        if df.empty:
            print(f"[WAARSCHUWING] Geen data voor {name} ({symbol})")
            return None
        # Flatten multi-level columns die yfinance soms aanmaakt
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index)
        df.name = name
        return df
    except Exception as exc:
        print(f"[FOUT] {name} ({symbol}): {exc}")
        return None


def fetch_all() -> dict[str, pd.DataFrame]:
    """Download data voor alle tickers in config.TICKERS."""
    result = {}
    for name, symbol in TICKERS.items():
        df = fetch_ticker(name, symbol)
        if df is not None:
            result[name] = df
    return result
