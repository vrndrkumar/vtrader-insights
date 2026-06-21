"""Run this on the SERVER to check yfinance's actual session handling, not raw curl."""
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")

print("yfinance version:", yf.__version__)
print()

for sym in ["RELIANCE.NS", "^NSEI", "TCS.NS"]:
    try:
        t = yf.Ticker(sym)
        h = t.history(period="5d")
        if not h.empty:
            print(f"{sym:15} OK  — last close {h['Close'].iloc[-1]:.2f}")
        else:
            print(f"{sym:15} EMPTY result")
    except Exception as e:
        print(f"{sym:15} ERROR — {str(e)[:80]}")