"""
Script to update stock metadata for ticker pools.
Usage:
  python scripts/stock_meta_cache_updater.py
  python scripts/stock_meta_cache_updater.py <ticker_type>
"""

import sys
from pathlib import Path

# Add project root to sys.path to allow imports from utils
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

import argparse

from utils.logger import get_app_logger
from utils.stock_meta_updater import update_stock_metadata


def main():
    parser = argparse.ArgumentParser(description="Update stock metadata.")
    parser.add_argument("target", nargs="?", help="Ticker Pool ID (optional)")
    args = parser.parse_args()

    target = (args.target or "").strip().lower()  # None if not provided

    logger = get_app_logger()

    try:
        if target:
            logger.info(f"Target ticker pool specified: {target}")
            update_stock_metadata(target)
        else:
            logger.info("No target specified. Updating all configured ticker pools.")
            update_stock_metadata(None)

    except Exception as e:
        logger.error(f"Failed to update stock metadata: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
