"""
Strategiematches screener — aangepaste momentumcriteria voor AEX-aandelen.

Criteria (elk levert 1 punt op, max score = 5):
  1. RSI in koopzone      : RSI tussen 40–65 (momentum zonder overbought)
                            OF RSI net hersteld van oversold (vorige dag < 30, nu > 30)
  2. Relatief volume      : huidig volume > 1.5× het 20-daags gemiddelde
  3. Nieuws aanwezig      : er is nieuws gepubliceerd in de afgelopen 3 dagen
  4. MACD bullish         : MACD-lijn boven de signaallijn
  5. Koers boven SMA-50   : bullish kortetermijntrend
"""

from __future__ import annotations
import pandas as pd
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Individuele criterium-checks
# ---------------------------------------------------------------------------

def _check_rsi(df: pd.DataFrame) -> tuple[bool, str]:
    rsi = df["RSI_14"]
    cur  = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
    prev = float(rsi.iloc[-2]) if len(rsi) > 1 and not pd.isna(rsi.iloc[-2]) else None

    if cur is None:
        return False, "RSI niet beschikbaar"
    if 40 <= cur <= 65:
        return True, f"RSI {cur:.1f} — momentum koopzone (40–65)"
    if prev is not None and prev <= 30 and cur > 30:
        return True, f"RSI hersteld van oversold ({prev:.1f} → {cur:.1f})"
    if cur > 65:
        return False, f"RSI {cur:.1f} — overbought (>65)"
    return False, f"RSI {cur:.1f} — nog geen momentum (<40)"


def _check_rel_volume(df: pd.DataFrame, min_factor: float = 1.5) -> tuple[bool, str]:
    vol = df["Volume"].squeeze()
    avg_vol = float(vol.rolling(20).mean().iloc[-1])
    cur_vol = float(vol.iloc[-1])

    if avg_vol == 0:
        return False, "Volumedata niet beschikbaar"

    rel = cur_vol / avg_vol
    if rel >= min_factor:
        return True, f"Relatief volume {rel:.1f}× (gem. {avg_vol:,.0f})"
    return False, f"Relatief volume {rel:.1f}× — te laag (<{min_factor}×)"


def _check_nieuws(nieuws: list, max_dagen: int = 3) -> tuple[bool, str]:
    if not nieuws:
        return False, "Geen recent nieuws gevonden"

    grens = datetime.now() - timedelta(days=max_dagen)
    recent = [
        n for n in nieuws
        if datetime.fromtimestamp(n.get("providerPublishTime", 0)) >= grens
    ]
    if recent:
        titel = recent[0].get("title", "")[:60]
        return True, f'"{titel}..."'
    return False, f"Geen nieuws in afgelopen {max_dagen} dagen"


def _check_macd(df: pd.DataFrame) -> tuple[bool, str]:
    if "MACD" not in df.columns or "MACD_signal" not in df.columns:
        return False, "MACD niet beschikbaar"
    macd   = float(df["MACD"].iloc[-1])
    signal = float(df["MACD_signal"].iloc[-1])
    diff   = round(macd - signal, 4)
    if macd > signal:
        return True, f"MACD bullish (verschil: +{diff})"
    return False, f"MACD bearish (verschil: {diff})"


def _check_sma50(df: pd.DataFrame) -> tuple[bool, str]:
    if "SMA_50" not in df.columns:
        return False, "SMA-50 niet beschikbaar"
    koers = float(df["Close"].iloc[-1])
    sma   = float(df["SMA_50"].iloc[-1])
    pct   = (koers - sma) / sma * 100
    if koers > sma:
        return True, f"Koers {pct:+.1f}% boven SMA-50 (€{sma:.2f})"
    return False, f"Koers {pct:+.1f}% onder SMA-50 (€{sma:.2f})"


# ---------------------------------------------------------------------------
# Gap berekenen
# ---------------------------------------------------------------------------

def _gap_pct(df: pd.DataFrame) -> float:
    """Dagelijkse koersverandering t.o.v. vorige slotkoers."""
    if len(df) < 2:
        return 0.0
    prev = float(df["Close"].iloc[-2])
    cur  = float(df["Close"].iloc[-1])
    return round((cur - prev) / prev * 100, 2) if prev else 0.0


# ---------------------------------------------------------------------------
# Publieke interface
# ---------------------------------------------------------------------------

def scan_aandeel(
    name: str,
    symbol: str,
    df: pd.DataFrame,
    nieuws: list,
) -> dict:
    """
    Beoordeelt één aandeel op alle 5 criteria.
    Geeft een dict terug met score, details per criterium en metadata.
    """
    checks = {
        "RSI momentum":    _check_rsi(df),
        "Relatief volume": _check_rel_volume(df),
        "Nieuws":          _check_nieuws(nieuws),
        "MACD bullish":    _check_macd(df),
        "Boven SMA-50":    _check_sma50(df),
    }

    score  = sum(1 for ok, _ in checks.values() if ok)
    koers  = float(df["Close"].iloc[-1])
    vol    = float(df["Volume"].squeeze().iloc[-1])
    rsi    = float(df["RSI_14"].iloc[-1]) if "RSI_14" in df.columns else None
    gap    = _gap_pct(df)

    return {
        "Naam":    name,
        "Ticker":  symbol,
        "Koers":   round(koers, 2),
        "Gap %":   gap,
        "Volume":  int(vol),
        "RSI":     round(rsi, 1) if rsi else None,
        "Score":   score,
        "checks":  checks,   # detail per criterium
        "nieuws":  nieuws[:3] if nieuws else [],
    }


def scan_alle(
    data: dict[str, pd.DataFrame],
    nieuws_map: dict[str, list],
    symbols: dict[str, str],
    min_score: int = 3,
) -> list[dict]:
    """
    Scant alle aandelen en geeft een gesorteerde lijst terug
    van aandelen die minimaal `min_score` criteria halen.
    """
    results = []
    for name, df in data.items():
        symbol = symbols.get(name, "")
        nieuws = nieuws_map.get(name, [])
        try:
            r = scan_aandeel(name, symbol, df, nieuws)
            if r["Score"] >= min_score:
                results.append(r)
        except Exception:
            pass

    return sorted(results, key=lambda x: x["Score"], reverse=True)
