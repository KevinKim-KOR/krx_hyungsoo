import logging
from datetime import date
from typing import Optional
import pandas as pd

from app.backtest.infra.providers.base import DataProvider

try:
    import FinanceDataReader as fdr

    FDR_AVAILABLE = True
except ImportError:
    FDR_AVAILABLE = False
    fdr = None

logger = logging.getLogger(__name__)


class FDRProvider(DataProvider):
    """FinanceDataReader 기반 데이터 제공자"""

    @property
    def name(self) -> str:
        return "fdr"

    def fetch_ohlcv(
        self, ticker: str, start: date, end: date
    ) -> Optional[pd.DataFrame]:
        if not FDR_AVAILABLE:
            logger.warning("FinanceDataReader is not installed.")
            return None

        try:
            # FDR requires YYYY-MM-DD
            start_str = start.strftime("%Y-%m-%d")
            end_str = end.strftime("%Y-%m-%d")

            df = fdr.DataReader(ticker, start_str, end_str)
            if df is not None and not df.empty:
                return df
            return None
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to fetch {ticker}: {e}")
            return None
