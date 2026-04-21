import pickle
import traceback


def main():
    try:
        from utils.db_manager import get_db_connection

        db = get_db_connection()
        col = db["cache_us_stocks"]
        doc = col.find_one({"ticker": "VOO"})
        if doc:
            print("Found VOO")
            payload = doc.get("data")
            if payload:
                df = pickle.loads(payload)
                print("Total rows:", len(df))
                print("Min date:", df.index.min())
                print("Max date:", df.index.max())
        else:
            print("VOO not found in DB")

        from utils.cache_utils import _get_cache_start_date

        print("Cache start date:", _get_cache_start_date())
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
