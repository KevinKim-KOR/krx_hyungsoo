# -*- coding: utf-8 -*-
"""
scripts/create_sample_parquet.py
테스트용 샘플 parquet 파일 생성

Phase 1.9 Real 운영 루프 테스트를 위한 샘플 데이터 생성
"""
import pandas as pd
import numpy as np
from datetime import date, timedelta
from pathlib import Path


def generate_ohlcv_data(
    ticker: str,
    start_date: date,
    end_date: date,
    seed: int = 42,
) -> pd.DataFrame:
    """
    랜덤 OHLCV 데이터 생성
    
    Args:
        ticker: 티커 코드
        start_date: 시작일
        end_date: 종료일
        seed: 랜덤 시드
        
    Returns:
        OHLCV DataFrame
    """
    np.random.seed(seed + hash(ticker) % 1000)
    
    # 거래일 생성 (주말 제외)
    dates = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # 월~금
            dates.append(current)
        current += timedelta(days=1)
    
    n_days = len(dates)
    
    # 가격 생성 (랜덤 워크)
    initial_price = np.random.uniform(10000, 100000)
    returns = np.random.normal(0.0005, 0.02, n_days)
    prices = initial_price * np.cumprod(1 + returns)
    
    # OHLCV 생성
    data = {
        "Date": dates,
        "Open": prices * np.random.uniform(0.99, 1.01, n_days),
        "High": prices * np.random.uniform(1.00, 1.03, n_days),
        "Low": prices * np.random.uniform(0.97, 1.00, n_days),
        "Close": prices,
        "Volume": np.random.randint(100000, 10000000, n_days),
    }
    
    df = pd.DataFrame(data)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date")
    
    # High >= max(Open, Close), Low <= min(Open, Close) 보정
    df["High"] = df[["Open", "High", "Close"]].max(axis=1)
    df["Low"] = df[["Open", "Low", "Close"]].min(axis=1)
    
    # 컬럼 타입 명시적 지정 (parquet 호환성)
    df = df.astype({
        "Open": "float64",
        "High": "float64",
        "Low": "float64",
        "Close": "float64",
        "Volume": "int64",
    })
    
    return df


def create_sample_parquets(
    output_dir: Path,
    tickers: list,
    start_date: date,
    end_date: date,
):
    """
    샘플 parquet 파일들 생성
    
    Args:
        output_dir: 출력 디렉토리
        tickers: 티커 리스트
        start_date: 시작일
        end_date: 종료일
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for ticker in tickers:
        df = generate_ohlcv_data(ticker, start_date, end_date)
        filepath = output_dir / f"{ticker}.parquet"
        df.to_parquet(filepath)
        print(f"  생성: {filepath.name} ({len(df)} rows)")
    
    print(f"\n총 {len(tickers)}개 파일 생성 완료: {output_dir}")


if __name__ == "__main__":
    # ETF 대형 10종 (run_phase15_realdata.py의 UNIVERSE_PRESETS["A"])
    etf_tickers = [
        "069500",  # KODEX 200
        "102110",  # TIGER 200
        "229200",  # KODEX 코스닥150
        "114800",  # KODEX 인버스
        "122630",  # KODEX 레버리지
        "233740",  # KODEX 코스닥150 레버리지
        "252670",  # KODEX 200선물인버스2X
        "261240",  # KODEX WTI원유선물(H)
        "305720",  # KODEX 2차전지산업
        "091160",  # KODEX 반도체
    ]
    
    # 추가 티커 (다른 유니버스용)
    additional_tickers = [
        "005930",  # 삼성전자
        "000660",  # SK하이닉스
        "035420",  # NAVER
        "035720",  # 카카오
        "051910",  # LG화학
    ]
    
    all_tickers = etf_tickers + additional_tickers
    
    output_dir = Path(__file__).parent.parent / "data" / "price"
    start_date = date(2019, 1, 1)  # 충분한 warmup 기간
    end_date = date(2024, 12, 20)
    
    print("=" * 60)
    print("샘플 Parquet 파일 생성")
    print("=" * 60)
    print(f"  출력 디렉토리: {output_dir}")
    print(f"  기간: {start_date} ~ {end_date}")
    print(f"  티커 수: {len(all_tickers)}")
    print()
    
    create_sample_parquets(output_dir, all_tickers, start_date, end_date)
