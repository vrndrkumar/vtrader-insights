"""
verify_sector_symbols.py
=========================
Run this on your Mac (where yfinance already works) to verify which
sector index symbols are valid before we build the sector scoring engine.

Usage:
    cd backend
    source .venv/bin/activate
    python verify_sector_symbols.py

Copy the full output and send it back — I'll use it to build the
final, verified sector_index_symbol mapping for your stock_mstr table.
"""

import yfinance as yf
import warnings
warnings.filterwarnings("ignore")

# Candidate symbols — multiple options per sector to find what actually works
CANDIDATES = {
    "Nifty 50 (benchmark)":        ["^NSEI"],
    "Nifty 500 (broad fallback)":  ["^CRSLDX", "NIFTY500.NS"],
    "Bank":                        ["^NSEBANK", "NIFTYBANK.NS", "BANKNIFTY.NS"],
    "Auto":                        ["^CNXAUTO", "NIFTYAUTO.NS"],
    "I.T":                         ["^CNXIT", "NIFTYIT.NS"],
    "FMCG":                        ["^CNXFMCG", "NIFTYFMCG.NS"],
    "Metals & Mining":             ["^CNXMETAL", "NIFTYMETAL.NS"],
    "Realty":                      ["^CNXREALTY", "NIFTYREALTY.NS"],
    "Healthcare":                  ["^CNXPHARMA", "NIFTYPHARMA.NS", "NIFTYHEALTHCARE.NS"],
    "Energy":                      ["^CNXENERGY", "NIFTYENERGY.NS"],
    "Media":                       ["^CNXMEDIA", "NIFTYMEDIA.NS"],
    "Financials":                  ["^CNXFIN", "NIFTYFINSERVICE.NS", "NIFTY_FIN_SERVICE.NS"],
    "Industrials":                 ["^CNXINFRA", "NIFTYINFRA.NS"],
    "Services":                    ["^CNXSERVICE", "NIFTYSERVSECTOR.NS"],
    "Consumer Discretionary":      ["^CNXCONSUM", "NIFTYCONSUMPTION.NS"],
    "Chemicals":                   ["NIFTYCHEMICALS.NS"],
    "Aerospace & Defence":         ["NIFTYINDDEFENCE.NS", "NIFTYDEFENCE.NS"],
    "Telecom":                     ["NIFTYMEDIA.NS"],  # no dedicated telecom index, telecom often grouped here
}

print(f"{'Sector':30} {'Symbol Tried':25} {'Result':10} {'Last Close':>12}")
print("-" * 82)

results = {}
for sector, syms in CANDIDATES.items():
    found = None
    for sym in syms:
        try:
            t = yf.Ticker(sym)
            h = t.history(period="5d", auto_adjust=True)
            if not h.empty:
                found = (sym, float(h["Close"].iloc[-1]))
                break
        except Exception:
            continue

    if found:
        print(f"{sector:30} {found[0]:25} {'OK':10} {found[1]:12.2f}")
        results[sector] = found[0]
    else:
        tried = ", ".join(syms)
        print(f"{sector:30} {tried:25} {'FAILED':10} {'-':>12}")
        results[sector] = None

print()
print("=" * 82)
print("SUMMARY — copy this dict and send it back:")
print("=" * 82)
print(results)