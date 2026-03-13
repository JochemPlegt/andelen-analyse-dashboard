"""
AEX Aandelen Analyse
====================
Haalt koersdata op, berekent technische indicatoren en print signalen.

Gebruik:
    python main.py
"""

import sys
import io
from tabulate import tabulate

# Zorg voor UTF-8 output op Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from data_fetcher import fetch_all
from indicators import add_indicators
from signals import build_summary
from exporter import save_ticker_csv, save_summary_csv


def main() -> None:
    print("=== AEX Aandelen Analyse ===\n")

    # 1. Data ophalen
    print("Koersdata ophalen...")
    raw_data = fetch_all()
    if not raw_data:
        print("Geen data beschikbaar. Controleer je internetverbinding.")
        sys.exit(1)

    # 2. Indicatoren berekenen + opslaan per aandeel
    print("Indicatoren berekenen...\n")
    enriched: dict = {}
    for name, df in raw_data.items():
        df_ind = add_indicators(df)
        enriched[name] = df_ind
        path = save_ticker_csv(name, df_ind)
        print(f"  {name:12s} -> {path}")

    # 3. Signaloverzicht bouwen
    summary = build_summary(enriched)

    # 4. Overzicht printen
    print("\n--- Signaloverzicht (meest recente dag) ---\n")
    print(tabulate(summary, headers="keys", tablefmt="simple",
                   showindex=False, floatfmt=".2f"))

    # Markeer aandelen met opvallend signaal
    alerts = summary[summary["RSI-signaal"].isin(["OVERBOUGHT", "OVERSOLD"])]
    if not alerts.empty:
        print("\n[!] Let op:")
        for _, row in alerts.iterrows():
            print(f"    {row['Naam']:12s} RSI {row['RSI']:5.1f} -> {row['RSI-signaal']}")

    # 5. Overzicht opslaan
    path = save_summary_csv(summary)
    print(f"\nOverzicht opgeslagen als: {path}")


if __name__ == "__main__":
    main()
