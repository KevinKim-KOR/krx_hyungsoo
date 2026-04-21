import re

import pandas as pd
from pykrx import stock


def main():
    # 1. Read removed tickers
    tickers = []
    names = {}
    try:
        with open(
            "/Users/jason/.gemini/antigravity/brain/be92e73c-5f8f-49ba-9993-a6bfefa9d6f8/removed_stocks_list.md",
            encoding="utf-8",
        ) as f:
            for line in f:
                match = re.search(r"- ([0-9A-Z]+) \((.+)\)", line)
                if match:
                    code, name = match.groups()
                    tickers.append(code)
                    names[code] = name
    except Exception as e:
        print(f"Error reading list: {e}")
        return

    print(f"Fetching data for {len(tickers)} tickers using pykrx...")

    # Fetch data range: End of 2025 to Now
    start_date = "20251220"
    end_date = pd.Timestamp.now().strftime("%Y%m%d")

    results = []

    # Batch processing or loop? pykrx is per ticker usually for specific range.
    # To be fast, maybe we can fetch all? No, removed tickers are random list.

    for i, ticker in enumerate(tickers):
        try:
            # Add small delay to avoid blocking if strictly rate limited, though pykrx scrapes Naver
            # time.sleep(0.05)

            df = stock.get_market_ohlcv(start_date, end_date, ticker, adjusted=True)

            if df is None or df.empty:
                continue

            # Find last trading day of 2025
            df_2025 = df[df.index.year == 2025]
            if df_2025.empty:
                # If listed in 2026, use first day of 2026
                base_price = df.iloc[0]["시가"]  # Use Open of first day
                base_date = df.index[0]
            else:
                base_price = df_2025.iloc[-1]["종가"]
                base_date = df_2025.index[-1]

            # Current price (Last row)
            current_price = df.iloc[-1]["종가"]
            current_date = df.index[-1]

            if base_price > 0:
                ytd = (current_price / base_price - 1) * 100.0

                results.append(
                    {
                        "ticker": ticker,
                        "name": names.get(ticker, ticker),
                        "ytd": ytd,
                        "base_price": base_price,
                        "current_price": current_price,
                        "base_date": base_date.strftime("%Y-%m-%d"),
                        "current_date": current_date.strftime("%Y-%m-%d"),
                    }
                )

                # Debug 471760
                if ticker == "471760":
                    print(
                        f"[DEBUG 471760] Base ({base_date}): {base_price} -> Cur ({current_date}): {current_price} = {ytd:.2f}%"
                    )

        except Exception:
            # print(f"Error fetching {ticker}: {e}")
            pass

    # Sort
    results.sort(key=lambda x: x["ytd"], reverse=True)

    print(f"\n=== Deleted Stocks YTD Top Performers (pykrx) Total {len(results)} ===")
    for rank, item in enumerate(results, 1):
        print(f"{rank}. {item['name']} ({item['ticker']}): {item['ytd']:.2f}% (Price: {item['current_price']:,.0f})")


if __name__ == "__main__":
    main()
