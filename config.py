# --- Configuratie ---

TICKERS = {
    "ASML":      "ASML.AS",
    "Shell":     "SHELL.AS",
    "Philips":   "PHIA.AS",
    "AkzoNobel": "AKZA.AS",
    "Unilever":  "UNA.AS",
}

# Periode voor historische data
PERIOD = "3y"          # bijv. "6mo", "1y", "2y"
INTERVAL = "1d"

# Technische indicatoren
RSI_PERIOD      = 14
MACD_FAST       = 12
MACD_SLOW       = 26
MACD_SIGNAL     = 9
MA_SHORT        = 50
MA_LONG         = 200

# Drempelwaarden
RSI_OVERBOUGHT  = 70
RSI_OVERSOLD    = 30

# Uitvoer
OUTPUT_DIR      = "output"
