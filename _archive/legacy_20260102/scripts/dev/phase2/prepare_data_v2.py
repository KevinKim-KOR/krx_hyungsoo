#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2 재테스트 - 2단계: 데이터 준비 (개선 버전)
예상 시간: 1~2시간
"""
import sys
from pathlib import Path
from datetime import date, datetime, timedelta
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
import pandas as pd
from tqdm import tqdm

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 로거 생성
from scripts.phase2.utils.logger import create_logger
logger = create_logger("2_prepare_data", PROJECT_ROOT)

logger.info("Phase 2 재테스트 - 2단계: 데이터 준비 (개선 버전)")
logger.info("예상 시간: 1~2시간")

# 1. ETF 목록 조회
logger.section("1. ETF 목록 조회")

try:
    from pykrx import stock
    
    # 전체 ETF 목록
    today = datetime.now(KST).strftime('%Y%m%d')
    etf_list = stock.get_etf_ticker_list(today)
    
    logger.info(f"전체 ETF 수: {len(etf_list)}개")
    
    # ETF 정보 수집 (전체 조회 - 시간이 걸림)
    etf_info = []
    logger.info("ETF 정보 수집 중... (시간이 걸립니다)")
    
    # 최근 1개월 데이터로 거래량 확인
    one_month_ago = (datetime.now(KST) - timedelta(days=30)).strftime('%Y%m%d')
    
    for ticker in tqdm(etf_list, desc="ETF 정보"):
        try:
            name = stock.get_etf_ticker_name(ticker)
            
            # 최근 1개월 거래량 확인
            df = stock.get_etf_ohlcv_by_date(
                fromdate=one_month_ago,
                todate=today,
                ticker=ticker
            )
            
            if df is not None and len(df) > 0:
                avg_volume = df['거래량'].mean()
                avg_value = (df['종가'] * df['거래량']).mean()  # 거래대금
                last_price = df['종가'].iloc[-1]
                
                etf_info.append({
                    'ticker': ticker,
                    'name': name,
                    'avg_volume': avg_volume,
                    'avg_value': avg_value,
                    'last_price': last_price
                })
        except Exception as e:
            logger.info(f"  {ticker} 조회 실패: {e}")
            continue
    
    etf_df = pd.DataFrame(etf_info)
    logger.success(f"정보 수집 완료: {len(etf_df)}개")
    
    # 수집된 ETF 정보 저장
    info_file = PROJECT_ROOT / 'data' / 'universe' / 'etf_info_raw.csv'
    etf_df.to_csv(info_file, index=False, encoding='utf-8-sig')
    logger.success(f"ETF 정보 저장: {info_file}")

except Exception as e:
    logger.fail(f"PyKRX 조회 실패: {e}")
    logger.info("대체 방법: 기존 수집된 정보 사용 또는 수동 목록 사용")
    
    # 기존 파일 확인
    info_file = PROJECT_ROOT / 'data' / 'universe' / 'etf_info_raw.csv'
    if info_file.exists():
        logger.info(f"기존 ETF 정보 파일 사용: {info_file}")
        etf_df = pd.read_csv(info_file, encoding='utf-8-sig')
    else:
        logger.fail("기존 ETF 정보 파일 없음. 스크립트를 종료합니다.")
        logger.info("해결 방법: PyKRX 설치 또는 네트워크 확인")
        logger.finish()
        sys.exit(1)

# 2. ETF 필터링
logger.section("2. ETF 필터링")

logger.info(f"필터링 전: {len(etf_df)}개")

# 제외 키워드 (레버리지, 인버스 등)
exclude_keywords = [
    '레버리지', '인버스', '곱버스', 'Short',
    '2X', '3X', '-1X', '-2X',
    'Leverage', 'Inverse'
]

# 이름 기반 필터링
filtered_df = etf_df.copy()
for keyword in exclude_keywords:
    filtered_df = filtered_df[~filtered_df['name'].str.contains(keyword, na=False)]

logger.info(f"레버리지/인버스 제외 후: {len(filtered_df)}개")

# 거래대금 필터링 (5억원 이상으로 완화)
if 'avg_value' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['avg_value'] > 500_000_000]
    logger.info(f"거래대금 필터링 후 (>5억): {len(filtered_df)}개")

# 거래대금 기준 정렬
if 'avg_value' in filtered_df.columns:
    filtered_df = filtered_df.sort_values('avg_value', ascending=False)

# 상위 60개 선택 (목표: 50개, 여유분 포함)
target_count = min(60, len(filtered_df))
filtered_df = filtered_df.head(target_count)

logger.success(f"최종 선택: {len(filtered_df)}개 ETF")

# 선택된 ETF 목록 출력
logger.info("\n선택된 ETF 목록 (상위 10개):")
for idx, row in filtered_df.head(10).iterrows():
    logger.info(f"  {row['ticker']} - {row['name'][:20]:20s} (거래대금: {row['avg_value']/1e8:.1f}억)")

# 유니버스 저장
universe_file = PROJECT_ROOT / 'data' / 'universe' / 'etf_universe.csv'
filtered_df.to_csv(universe_file, index=False, encoding='utf-8-sig')
logger.success(f"유니버스 저장: {universe_file}")

selected_tickers = filtered_df['ticker'].tolist()

# 3. 가격 데이터 수집
logger.section("3. 가격 데이터 수집 (2022-01-01 ~ 현재)")

start_date = date(2022, 1, 1)
end_date = date.today()

logger.info(f"기간: {start_date} ~ {end_date} (약 {(end_date - start_date).days}일)")
logger.info(f"종목 수: {len(selected_tickers)}개")
logger.info("데이터 로딩 중... (시간이 걸릴 수 있습니다)")

from infra.data.loader import load_price_data

try:
    price_data = load_price_data(selected_tickers, start_date, end_date)
    
    logger.success("데이터 로드 완료")
    logger.info(f"   Shape: {price_data.shape}")
    logger.info(f"   Columns: {price_data.columns.tolist()}")
    logger.info(f"   Index levels: {price_data.index.names}")
    
    # 4. 데이터 품질 확인
    logger.section("4. 데이터 품질 확인")
    
    # 종목별 데이터 수
    if isinstance(price_data.index, pd.MultiIndex):
        ticker_counts = price_data.groupby(level=0).size()
        
        logger.info("종목별 데이터 수 통계:")
        logger.info(f"  평균: {ticker_counts.mean():.0f}일")
        logger.info(f"  중앙값: {ticker_counts.median():.0f}일")
        logger.info(f"  최소: {ticker_counts.min():.0f}일")
        logger.info(f"  최대: {ticker_counts.max():.0f}일")
        
        # 데이터가 부족한 종목 (500일 미만)
        min_required = 500
        insufficient = ticker_counts[ticker_counts < min_required]
        
        if len(insufficient) > 0:
            logger.warn(f"데이터 부족 종목 ({len(insufficient)}개, <{min_required}일):")
            for ticker, count in insufficient.items():
                ticker_name = filtered_df[filtered_df['ticker'] == ticker]['name'].values
                name = ticker_name[0] if len(ticker_name) > 0 else "Unknown"
                logger.info(f"   {ticker} ({name[:15]:15s}): {count}일")
            
            # 부족한 종목 제외 여부 확인
            sufficient_tickers = ticker_counts[ticker_counts >= min_required].index.tolist()
            logger.info(f"\n충분한 데이터 종목: {len(sufficient_tickers)}개")
            
            if len(sufficient_tickers) >= 30:  # 최소 30개 확보
                logger.info("데이터 부족 종목을 제외하고 진행합니다.")
                price_data = price_data.loc[sufficient_tickers]
                selected_tickers = sufficient_tickers
                
                # 유니버스 업데이트
                filtered_df = filtered_df[filtered_df['ticker'].isin(selected_tickers)]
                filtered_df.to_csv(universe_file, index=False, encoding='utf-8-sig')
                logger.success(f"유니버스 업데이트: {len(selected_tickers)}개")
        else:
            logger.success("모든 종목이 충분한 데이터를 가지고 있습니다")
    
    # 결측치 확인
    missing = price_data.isnull().sum()
    if missing.sum() > 0:
        logger.warn("결측치 발견:")
        for col, count in missing[missing > 0].items():
            logger.info(f"   {col}: {count}개")
    else:
        logger.success("결측치 없음")
    
    # 샘플 데이터 출력
    logger.info("\n샘플 데이터 (최근 5일):")
    sample = price_data.tail(5)
    for idx, row in sample.iterrows():
        if isinstance(idx, tuple):
            ticker, dt = idx
            logger.info(f"   {ticker} {dt}: close={row['close']:.0f}, volume={row['volume']:,.0f}")
    
    # 5. 캐시 저장 확인
    logger.section("5. 캐시 저장 확인")
    
    cache_dir = PROJECT_ROOT / 'data' / 'cache' / 'ohlcv'
    parquet_files = list(cache_dir.glob('*.parquet'))
    stock_files = [f for f in parquet_files if not (f.stem.isdigit() and len(f.stem) == 8)]
    
    logger.info(f"캐시된 파일 수: {len(stock_files)}개")
    
    # 캐시 파일 크기 확인
    total_size = sum(f.stat().st_size for f in stock_files)
    logger.info(f"총 캐시 크기: {total_size / (1024**2):.1f} MB")
    
    # 6. 최종 요약
    logger.section("데이터 준비 완료")
    
    logger.success(f"선택된 ETF: {len(selected_tickers)}개")
    logger.success(f"데이터 기간: {start_date} ~ {end_date}")
    logger.success(f"데이터 Shape: {price_data.shape}")
    logger.success(f"캐시 파일: {len(stock_files)}개")
    logger.success(f"캐시 크기: {total_size / (1024**2):.1f} MB")
    
    # 다음 단계 안내
    logger.info("")
    logger.info("다음 단계: 기본 백테스트")
    logger.info("  python scripts/phase2/run_backtest.py")
    
    # 데이터 요약 저장
    summary = {
        'etf_count': len(selected_tickers),
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'data_shape': price_data.shape,
        'cache_files': len(stock_files),
        'cache_size_mb': total_size / (1024**2),
        'timestamp': datetime.now(KST).isoformat()
    }
    
    import json
    summary_file = PROJECT_ROOT / 'backtests' / 'phase2_retest' / 'data_summary.json'
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.success(f"데이터 요약 저장: {summary_file}")
    
except Exception as e:
    logger.fail(f"데이터 로드 실패: {e}")
    import traceback
    traceback.print_exc()
    
    logger.info("\n해결 방법:")
    logger.info("1. 네트워크 연결 확인")
    logger.info("2. PyKRX, FinanceDataReader 설치 확인")
    logger.info("3. 종목 코드 확인")
    logger.info("4. API 제한 확인 (잠시 후 재시도)")

logger.finish()
logger.info(f"\n로그 파일: {logger.log_file}")
