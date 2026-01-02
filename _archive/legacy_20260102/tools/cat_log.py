
import sys

def main():
    log_path = "fatal_error.log"
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            print(f.read())
    except Exception as e:
        print(f"Failed to read log: {e}")

if __name__ == "__main__":
    main()
