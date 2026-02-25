"""
data_loader.py
단순한 데이터 로딩 - yfinance 중심
친구 코드 구조 참고
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# yfinance 선택적 import (NAS Python 3.8 호환성)
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except (ImportError, TypeError) as e:
    logging.warning(f"yfinance 사용 불가: {e}")
    YFINANCE_AVAILABLE = False
    yf = None

# FinanceDataReader 선택적 import (Python 3.8 호환, KOSPI 지수용)
try:
    import FinanceDataReader as fdr
    FDR_AVAILABLE = True
except ImportError:
    logging.warning("FinanceDataReader 사용 불가")
    FDR_AVAILABLE = False
    fdr = None

# PyKRX import (한국 시장 데이터, Python 3.8 호환)
try:
    from pykrx import stock as krx_stock
    PYKRX_AVAILABLE = True
except ImportError:
    logging.warning("PyKRX 사용 불가")
    PYKRX_AVAILABLE = False
    krx_stock = None

log = logging.getLogger(__name__)

CACHE_DIR = Path("data/cache/ohlcv")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _read_cache(symbol: str) -> Optional[pd.DataFrame]:
    """캐시에서 데이터 읽기"""
    cache_file = CACHE_DIR / f"{symbol}.parquet"
    if not cache_file.exists():
        return None
    try:
        df = pd.read_parquet(cache_file)
        if df.empty:
            return None
        return df
    except Exception as e:
        log.warning(f"Cache read failed for {symbol}: {e}")
        return None


def _write_cache(symbol: str, df: pd.DataFrame):
    """캐시에 데이터 저장"""
    if df is None or df.empty:
        return
    try:
        cache_file = CACHE_DIR / f"{symbol}.parquet"
        df.to_parquet(cache_file)
    except Exception as e:
        log.warning(f"Cache write failed for {symbol}: {e}")


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame 정규화"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    # yfinance 0.2.x MultiIndex columns: ('Close', 'TICKER') → 'Close'
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # 인덱스를 DatetimeIndex로 변환
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    # 타임존 제거
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    
    # 정렬 및 중복 제거
    df = df.sort_index()
    df = df[~df.index.duplicated(keep='last')]
    
    # 컬럼명 정규화
    df = df.rename(columns={
        # yfinance
        'Adj Close': 'AdjClose',
        'adj_close': 'AdjClose',
        # PyKRX 한글 컬럼명
        '시가': 'Open',
        '고가': 'High',
        '저가': 'Low',
        '종가': 'Close',
        '거래량': 'Volume',
        '거래대금': 'Value',
        '상장시가총액': 'MarketCap',
    })
    
    # AdjClose 컬럼 추가 (없으면 Close 사용)
    if 'AdjClose' not in df.columns and 'Close' in df.columns:
        df['AdjClose'] = df['Close']
    
    return df


def get_ohlcv(symbol: str, start, end, use_cache: bool = True) -> pd.DataFrame:
    """
    OHLCV 데이터 로딩 - 단순 버전
    
    Args:
        symbol: 종목 코드 (예: '005930.KS', 'AAPL')
        start: 시작일
        end: 종료일
        use_cache: 캐시 사용 여부
    
    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume, AdjClose
    """
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    
    # 1. 캐시 확인
    if use_cache:
        cached = _read_cache(symbol)
        if cached is not None and not cached.empty:
            # 캐시에 필요한 데이터가 모두 있으면 반환
            if start >= cached.index.min() and end <= cached.index.max():
                result = cached.loc[start:end]
                if not result.empty:
                    return result
    
    # 2. yfinance로 다운로드 (사용 가능한 경우)
    if not YFINANCE_AVAILABLE:
        log.warning(f"yfinance 사용 불가 - 네이버 금융 폴백 시도: {symbol}")
        return get_ohlcv_naver_fallback(symbol, start, end)
    
    try:
        log.info(f"Downloading {symbol} from {start.date()} to {end.date()}")
        df = yf.download(
            symbol,
            start=start,
            end=end + pd.Timedelta(days=1),  # end는 inclusive하게
            progress=False,
            auto_adjust=False
        )
        
        if df.empty:
            log.warning(f"No data for {symbol}")
            return pd.DataFrame()
        
        # 정규화
        df = _normalize_df(df)
        
        # 3. 캐시 업데이트
        if use_cache:
            # 기존 캐시와 병합
            if cached is not None and not cached.empty:
                df = pd.concat([cached, df]).sort_index()
                df = df[~df.index.duplicated(keep='last')]
            _write_cache(symbol, df)
        
        # 요청 범위만 반환
        return df.loc[start:end]
        
    except Exception as e:
        log.error(f"Failed to download {symbol}: {e}")
        log.info(f"네이버 금융 폴백 시도: {symbol}")
        return get_ohlcv_naver_fallback(symbol, start, end)


def get_ohlcv_safe(symbol: str, start, end) -> pd.DataFrame:
    """
    안전한 OHLCV 로딩 - 에러 시 빈 DataFrame 반환
    하위 호환성을 위한 래퍼
    """
    try:
        return get_ohlcv(symbol, start, end)
    except Exception as e:
        log.warning(f"get_ohlcv_safe failed for {symbol}: {e}")
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])


def get_current_price_naver(code: str) -> Optional[float]:
    """
    네이버 금융에서 현재가 조회 (한국 주식)
    
    Args:
        code: 종목 코드 (예: '005930')
    
    Returns:
        현재가 (float) 또는 None
    """
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 현재가 추출
        price_element = soup.select_one('.no_today .blind')
        if price_element:
            price_text = price_element.text.strip().replace(',', '')
            return float(price_text)
        
        # 대체 방법
        price_element = soup.select_one('.p11 .blind')
        if price_element:
            price_text = price_element.text.strip().replace(',', '')
            return float(price_text)
        
        log.warning(f"현재가 요소를 찾을 수 없음: {code}")
        return None
        
    except Exception as e:
        log.error(f"네이버 금융 현재가 조회 실패 ({code}): {e}")
        return None


def get_kospi_index_naver() -> Optional[float]:
    """
    네이버 금융에서 KOSPI 지수 조회
    
    Returns:
        KOSPI 지수 (float) 또는 None
    """
    try:
        url = "https://finance.naver.com/sise/sise_index.naver?code=KOSPI"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # KOSPI 지수 추출
        index_element = soup.select_one('#now_value')
        if index_element:
            index_text = index_element.text.strip().replace(',', '')
            return float(index_text)
        
        log.warning("KOSPI 지수 요소를 찾을 수 없음")
        return None
        
    except Exception as e:
        log.error(f"네이버 금융 KOSPI 지수 조회 실패: {e}")
        return None


def get_ohlcv_naver_fallback(symbol: str, start, end) -> pd.DataFrame:
    """
    폴백 데이터 로더 (yfinance 실패 시)
    1. PyKRX 시도 (KOSPI 지수, 한국 주식 - 기존 시스템 활용!)
    2. FinanceDataReader 시도 (KOSPI 지수, 한국 주식)
    3. 네이버 금융 시도 (현재가만)
    
    Args:
        symbol: 종목 코드
        start: 시작일
        end: 종료일
    
    Returns:
        DataFrame with OHLCV data
    """
    log.info(f"폴백 데이터 로더 시도: {symbol}")
    
    # 1. PyKRX 시도 (Python 3.8 호환, 기존 시스템!)
    if PYKRX_AVAILABLE:
        try:
            log.info(f"PyKRX로 {symbol} 조회 시도")
            
            # KOSPI 지수
            if symbol == '^KS11':
                start_str = start.strftime("%Y%m%d") if hasattr(start, 'strftime') else start
                end_str = end.strftime("%Y%m%d") if hasattr(end, 'strftime') else end
                
                df = krx_stock.get_index_ohlcv(start_str, end_str, "1001")  # KOSPI
                
                if df is not None and not df.empty:
                    log.info(f"PyKRX KOSPI 성공: {len(df)}행")
                    
                    # 정규화 (한글 컬럼명 → 영문, AdjClose 자동 추가)
                    df = _normalize_df(df)
                    
                    return df
            
            # 한국 주식
            elif symbol.endswith('.KS'):
                code = symbol.replace('.KS', '')
                start_str = start.strftime("%Y%m%d") if hasattr(start, 'strftime') else start
                end_str = end.strftime("%Y%m%d") if hasattr(end, 'strftime') else end
                
                df = krx_stock.get_market_ohlcv(start_str, end_str, code)
                
                if df is not None and not df.empty:
                    log.info(f"PyKRX {code} 성공: {len(df)}행")
                    
                    # 정규화 (한글 컬럼명 → 영문, AdjClose 자동 추가)
                    df = _normalize_df(df)
                    
                    return df
            
        except Exception as e:
            log.warning(f"PyKRX 실패: {e}")
    
    # 2. FinanceDataReader 시도 (Python 3.8 호환)
    if FDR_AVAILABLE:
        try:
            log.info(f"FinanceDataReader로 {symbol} 조회 시도")
            
            # 심볼 변환 (yfinance → FDR)
            fdr_symbol = symbol
            if symbol == '^KS11':
                fdr_symbol = 'KS11'  # KOSPI 지수
            elif symbol == '^KQ11':
                fdr_symbol = 'KQ11'  # KOSDAQ 지수
            elif symbol.endswith('.KS'):
                fdr_symbol = symbol.replace('.KS', '')  # 한국 주식
            
            df = fdr.DataReader(fdr_symbol, start, end)
            
            if df is not None and not df.empty:
                log.info(f"FinanceDataReader 성공: {len(df)}행")
                
                # 정규화
                df = _normalize_df(df)
                
                # AdjClose 컬럼 추가 (없으면)
                if 'AdjClose' not in df.columns and 'Close' in df.columns:
                    df['AdjClose'] = df['Close']
                
                return df
            
        except Exception as e:
            log.warning(f"FinanceDataReader 실패: {e}")
    
    # 3. 네이버 금융 시도 (현재가만)
    log.info(f"네이버 금융으로 현재가 조회 시도: {symbol}")
    
    # 한국 주식 코드 추출 (예: '005930.KS' -> '005930')
    code = symbol.split('.')[0].replace('^', '')
    
    # KOSPI 지수
    if symbol == '^KS11' or code == 'KS11':
        current_price = get_kospi_index_naver()
    else:
        current_price = get_current_price_naver(code)
    
    if current_price:
        # 현재 날짜로 단일 행 DataFrame 생성
        today = pd.Timestamp.now().normalize()
        df = pd.DataFrame({
            'Open': [current_price],
            'High': [current_price],
            'Low': [current_price],
            'Close': [current_price],
            'Volume': [0],
            'AdjClose': [current_price]
        }, index=[today])
        
        log.info(f"네이버 금융 현재가 조회 성공: {current_price}")
        return df
    
    log.error(f"모든 폴백 실패: {symbol}")
    return pd.DataFrame()


# ─── P167-R: 튜닝용 캐시 + 프리페치 ─────────────────────────────────────

# In-memory cache to avoid redundant disk reads within single process
_OHLCV_MEM_CACHE: dict = {}

TUNE_CACHE_DIR = Path("data/cache/ohlcv/tune")
TUNE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _tune_cache_path(ticker: str, start, end) -> Path:
    """튜닝용 캐시 파일 경로 (ticker + date range)"""
    s = pd.Timestamp(start).strftime("%Y%m%d")
    e = pd.Timestamp(end).strftime("%Y%m%d")
    return TUNE_CACHE_DIR / f"{ticker}_{s}_{e}.parquet"


def load_ohlcv_cached(
    ticker: str, start, end
) -> Optional[pd.DataFrame]:
    """
    P167-R: 튜닝용 OHLCV 로드 (캐시 우선)

    반환: MultiIndex(code, date) DataFrame — BacktestRunner 입력 형식과 동일

    1. 인메모리 캐시 HIT → 즉시 반환
    2. 디스크 캐시 HIT → 로드 후 인메모리에 저장
    3. MISS → 다운로드 후 디스크+인메모리 저장
    """
    cache_key = f"{ticker}_{start}_{end}"

    # 1. In-memory
    if cache_key in _OHLCV_MEM_CACHE:
        return _OHLCV_MEM_CACHE[cache_key]

    # 2. Disk
    disk_path = _tune_cache_path(ticker, start, end)
    if disk_path.exists():
        try:
            df = pd.read_parquet(disk_path)
            if not df.empty:
                _OHLCV_MEM_CACHE[cache_key] = df
                log.info(f"[TUNE_CACHE] HIT (disk): {ticker}")
                return df
        except Exception as e:
            log.warning(f"[TUNE_CACHE] Disk read failed {ticker}: {e}")

    # 3. Download (via existing get_ohlcv which has its own cache layer)
    log.info(f"[TUNE_CACHE] MISS → downloading: {ticker}")

    # yfinance symbol conversion: 6-digit code → .KS/.KQ
    if ticker.isdigit() and len(ticker) == 6:
        suffixes = [".KS", ".KQ"]
    elif ticker.isdigit():
        suffixes = [".KS"]
    else:
        suffixes = [""]

    raw_df = None
    for suffix in suffixes:
        symbol = f"{ticker}{suffix}"
        try:
            df = get_ohlcv(symbol, start, end, use_cache=True)
            if df is not None and not df.empty:
                raw_df = df
                break
        except Exception as e:
            log.warning(f"[TUNE_CACHE] {symbol} failed: {e}")

    if raw_df is None or raw_df.empty:
        log.warning(f"[TUNE_CACHE] No data for {ticker}")
        return None

    # Normalize to MultiIndex(code, date)
    raw_df.columns = [c.lower() if isinstance(c, str) else c for c in raw_df.columns]
    if "close" not in raw_df.columns:
        log.warning(f"[TUNE_CACHE] {ticker}: 'close' column missing")
        return None

    raw_df["code"] = ticker
    raw_df.index.name = "date"
    result = raw_df.reset_index().set_index(["code", "date"]).sort_index()

    # Save to disk + memory
    try:
        result.to_parquet(disk_path)
    except Exception as e:
        log.warning(f"[TUNE_CACHE] Disk write failed {ticker}: {e}")

    _OHLCV_MEM_CACHE[cache_key] = result
    log.info(f"[TUNE_CACHE] Cached {ticker}: {len(result)} rows")
    return result


def prefetch_ohlcv(
    tickers: list, start, end
) -> pd.DataFrame:
    """
    P167-R: 유니버스 전체 OHLCV 프리페치 (1회)

    모든 종목을 미리 다운로드+캐시 → 튜닝 trial에서는 다운로드 없음.
    반환: 전체 종목 합친 MultiIndex DataFrame
    """
    log.info(f"[PREFETCH] Starting prefetch for {len(tickers)} tickers...")
    frames = []
    for i, ticker in enumerate(tickers, 1):
        df = load_ohlcv_cached(ticker, start, end)
        if df is not None and not df.empty:
            frames.append(df)
            log.info(f"[PREFETCH] ({i}/{len(tickers)}) {ticker}: OK ({len(df)} rows)")
        else:
            log.warning(f"[PREFETCH] ({i}/{len(tickers)}) {ticker}: FAILED")

    if not frames:
        raise RuntimeError(
            f"프리페치 완전 실패. tickers={tickers}, "
            f"start={start}, end={end}. 네트워크 확인 필요."
        )

    combined = pd.concat(frames).sort_index()
    log.info(
        f"[PREFETCH] Complete: {len(combined)} rows, "
        f"{len(frames)}/{len(tickers)} tickers OK"
    )
    return combined
