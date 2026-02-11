
import json
import requests
from pathlib import Path
import datetime

# Copy paste fetch_history and load_data logic from app/pc/param_search.py to debug
# Or import it? 
# Let's import it to be sure we test actual code.
import sys
sys.path.append('e:/AI Study/krx_alertor_modular')
from app.pc.param_search import load_data, UNIVERSE, CACHE_DIR

print("Budget Loading Data...")
data = load_data()
print(f"Loaded {len(data)} tickers.")

for t in UNIVERSE:
    if t in data:
        rows = data[t]
        print(f"Ticker {t}: {len(rows)} rows.")
        if rows:
            print(f"  Start: {rows[0]['date']}")
            print(f"  End:   {rows[-1]['date']}")
    else:
        print(f"Ticker {t}: MISSING")

# Check Cache File content directly
cache_file = CACHE_DIR / "param_search_data_cache.json"
if cache_file.exists():
    print("Cache file exists.")
    c = json.loads(cache_file.read_text())
    print(f"Cache keys: {list(c.keys())}")
else:
    print("Cache file NOT found.")
