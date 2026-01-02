
from pykrx import stock
import datetime
import pandas as pd

def test_load():
    start = datetime.date(2021, 1, 1)
    end = datetime.date(2021, 1, 10)
    
    print(f"Loading KODEX 200 (069500) from {start} to {end}...")
    try:
        df = stock.get_market_ohlcv_by_date(
            start.strftime("%Y%m%d"),
            end.strftime("%Y%m%d"),
            "069500"
        )
        print("Success!")
        print(f"Columns: {df.columns}")
        print(df.head())
        
        # Test rename
        column_map = {
            "시가": "open",
            "고가": "high",
            "저가": "low",
            "종가": "close",
            "거래량": "volume",
        }
        df = df.rename(columns=column_map)
        print("Renamed Columns:", df.columns)
        
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import sys
    sys.stdout = open("diagnose_output.txt", "w", encoding="utf-8")
    sys.stderr = sys.stdout
    test_load()
