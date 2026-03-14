# --- Configuratie ---

# Volledige AEX-25
TICKERS = {
    "ASML":             "ASML.AS",
    "Shell":            "SHELL.AS",
    "RELX":             "REN.AS",
    "Unilever":         "UNA.AS",
    "ING":              "INGA.AS",
    "Heineken":         "HEIA.AS",
    "Ahold Delhaize":   "AD.AS",
    "ABN AMRO":         "ABN.AS",
    "Wolters Kluwer":   "WKL.AS",
    "Adyen":            "ADYEN.AS",
    "ASM Int.":         "ASM.AS",
    "Philips":          "PHIA.AS",
    "AkzoNobel":        "AKZA.AS",
    "NN Group":         "NN.AS",
    "Aegon":            "AGN.AS",
    "ArcelorMittal":    "MT.AS",
    "Randstad":         "RAND.AS",
    "DSM-Firmenich":    "DSFIR.AS",
    "Stellantis":       "STLAM.AS",
    "Universal Music":  "UMG.AS",
    "Besi":             "BESI.AS",
    "IMCD":             "IMCD.AS",
    "Exor":             "EXO.AS",
    "Ferrari":          "RACE.AS",
    "JDE Peet's":       "JDEP.AS",
}

# Periode voor historische data
PERIOD = "3y"          # bijv. "6mo", "1y", "2y", "3y"
INTERVAL = "1d"

# Technische indicatoren
RSI_PERIOD      = 14
MACD_FAST       = 12
MACD_SLOW       = 26
MACD_SIGNAL     = 9
MA_SHORT        = 50
MA_LONG         = 200

# Bollinger Bands
BB_PERIOD       = 20
BB_STD          = 2

# Drempelwaarden
RSI_OVERBOUGHT  = 70
RSI_OVERSOLD    = 30

# Uitvoer
OUTPUT_DIR      = "output"
