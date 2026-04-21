def main():
    from utils.db_manager import get_db_connection

    db = get_db_connection()
    col = db["cache_us_stocks"]
    col.drop()
    print("us cache dropped")


if __name__ == "__main__":
    main()
