"""
Backtest runner — MA Crossover strategie voor alle AEX-aandelen.

Gebruik:
    python -X utf8 run_backtest.py
"""

import sys
import io
import os
import pandas as pd
from tabulate import tabulate

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from data_fetcher import fetch_all
from indicators import add_indicators
from backtest import run_backtest

OUTPUT_DIR = "output"
START_CAPITAL = 10_000  # euro


def print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def main() -> None:
    print("=== AEX Backtest: MA Crossover (SMA50 vs SMA200) ===\n")

    # 1. Data + indicatoren
    print("Data ophalen en indicatoren berekenen...")
    raw = fetch_all()
    enriched = {name: add_indicators(df) for name, df in raw.items()}

    summaries = []
    all_trades: dict[str, pd.DataFrame] = {}

    # 2. Backtest per aandeel
    for name, df in enriched.items():
        try:
            result = run_backtest(name, df, start_capital=START_CAPITAL)
            summaries.append(result["summary"])
            all_trades[name] = result["trades"]
        except Exception as exc:
            print(f"[FOUT] {name}: {exc}")

    if not summaries:
        print("Geen resultaten beschikbaar.")
        sys.exit(1)

    # 3. Overzichtstabel
    print_section("Resultaten overzicht")
    overview_cols = [
        "Naam", "Rendement strategie %", "Rendement buy-hold %",
        "Max drawdown %", "Aantal trades", "Win-ratio %",
    ]
    overview = pd.DataFrame(summaries)[overview_cols]
    print(tabulate(overview, headers="keys", tablefmt="simple",
                   showindex=False, floatfmt=".2f"))

    # 4. Detail per aandeel
    print_section("Detail per aandeel")
    for s in summaries:
        name = s["Naam"]
        print(f"\n--- {name} ---")
        for k, v in s.items():
            if k != "Naam":
                label = f"{k}:"
                print(f"  {label:<30} {v}")

        trades = all_trades.get(name)
        if trades is not None and not trades.empty:
            print(f"\n  Trades ({len(trades)}):")
            trade_cols = ["entry_date", "exit_date", "entry_price",
                          "exit_price", "return_pct", "result"]
            available = [c for c in trade_cols if c in trades.columns]
            print(tabulate(trades[available], headers="keys",
                           tablefmt="simple", showindex=False, floatfmt=".2f"))
        else:
            print("  Geen trades gegenereerd in deze periode.")

    # 5. Opslaan
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    summary_path = os.path.join(OUTPUT_DIR, "backtest_overzicht.csv")
    pd.DataFrame(summaries).to_csv(summary_path, index=False)
    print(f"\nOverzicht opgeslagen: {summary_path}")

    for name, trades in all_trades.items():
        if not trades.empty:
            path = os.path.join(OUTPUT_DIR, f"backtest_{name.lower()}_trades.csv")
            trades.to_csv(path, index=False)
            print(f"Trades opgeslagen:    {path}")

    # 6. Winnaar / verliezer
    print_section("Strategie vs Buy-and-Hold")
    for s in summaries:
        strat = s["Rendement strategie %"]
        bh    = s["Rendement buy-hold %"]
        diff  = strat - bh
        emoji = "+" if diff >= 0 else "-"
        print(f"  {s['Naam']:12s}  strategie {strat:+.1f}%  |  "
              f"buy-hold {bh:+.1f}%  |  verschil {diff:+.1f}% [{emoji}]")


if __name__ == "__main__":
    main()
