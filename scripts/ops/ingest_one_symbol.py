# scripts/ops/ingest_one_symbol.py
#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys, json
from providers.ohlcv import ingest_symbol

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--since", default=None)
    a = ap.parse_args()
    out = ingest_symbol(a.symbol, a.since)
    print(json.dumps(out, ensure_ascii=False))
    if out["status"] in ("ok","up_to_date","fetch_empty_or_failed"):
        sys.exit(0)
    sys.exit(3)

if __name__ == "__main__":
    main()
