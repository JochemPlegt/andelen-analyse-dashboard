"""Slaat resultaten op als CSV-bestanden."""

import os
import pandas as pd
from config import OUTPUT_DIR


def ensure_output_dir() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_ticker_csv(name: str, df: pd.DataFrame) -> str:
    """Sla volledige indicator-data op per aandeel. Geeft het pad terug."""
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, f"{name.lower()}_indicatoren.csv")
    df.to_csv(path)
    return path


def save_summary_csv(summary: pd.DataFrame) -> str:
    """Sla het signaloverzicht op als CSV. Geeft het pad terug."""
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, "overzicht_signalen.csv")
    summary.to_csv(path, index=False)
    return path
