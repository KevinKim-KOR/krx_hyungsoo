import logging
from datetime import date, timedelta
from typing import Optional
import pandas as pd

from app.backtest.infra.providers.base import DataProvider

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    yf = None

logger = logging.getLogger(__name__)

class YFinanceProvider(DataProvider):
    """yfinance 기반 데이터 제공자 (Fallback)"""
    
    @property
    def name(self) -> str:
        return "yfinance"
        
    def fetch_ohlcv(self, ticker: str, start: date, end: date) -> Optional[pd.DataFrame]:
        if not YFINANCE_AVAILABLE:
            logger.warning("yfinance is not installed.")
            return None
            
        try:
            # yfinance는 한국 주식의 경우 심볼에 .KS 또는 .KQ가 필요함
            symbols_to_try = []
            if ticker.isdigit() and len(ticker) == 6:
                symbols_to_try = [f"{ticker}.KS", f"{ticker}.KQ"]
            else:
                symbols_to_try = [ticker]
                
            for symbol in symbols_to_try:
                # yfinance API limits end date to exclusive, so add 1 day
                df = yf.download(
                    symbol,
                    start=start.strftime("%Y-%m-%d"),
                    end=(end + timedelta(days=1)).strftime("%Y-%m-%d"),
                    progress=False,
                    auto_adjust=False
                )
                
                if df is not None and not df.empty:
                    # MultiIndex columns 처리 (yfinance 0.2.x 이상)
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                        
                    # 타임존 제거
                    if hasattr(df.index, 'tz') and df.index.tz is not None:
                        df.index = df.index.tz_localize(None)
                    
                    return df
            
            return None
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to fetch {ticker}: {e}")
            return None
