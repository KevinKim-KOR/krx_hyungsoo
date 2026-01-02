#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2 재테스트 - 2단계: 데이터 준비
예상 시간: 1~2시간 (네트워크 속도에 따라 다름)
"""
import sys
from pathlib import Path
from datetime import date, datetime
import pandas as pd
from tqdm import tqdm

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

print("=" * 70)
print("Phase 2 재테스트 - 2단계: 데이터 준비")
print("=" * 70)
print()

# 1. ETF 목록 조회
print("1. ETF 목록 조회")
print("-" * 70)

try:
    from pykrx import stock
    
    # 전체 ETF 목록
    today = datetime.now().strftime('%Y%m%d')
    etf_list = stock.get_etf_ticker_list(today)
    
    print(f"전체 ETF 수: {len(etf_list)}개")
    
    # ETF 정보 수집
    etf_info = []
    print("ETF 정보 수집 중...")
    
    for ticker in tqdm(etf_list[:100], desc="ETF 정보"):  # 처음 100개만 (시간 절약)
        try:
            name = stock.get_etf_ticker_name(ticker)
            
            # 거래량 확인 (최근 5일 평균)
            df = stock.get_etf_ohlcv_by_date(
                fromdate=(date.today().replace(day=1)).strftime('%Y%m%d'),
                todate=today,
                ticker=ticker
            )
            
            if df is not None and len(df) > 0:
                avg_volume = df['거래량'].mean()
                avg_value = (df['종가'] * df['거래량']).mean()  # 거래대금
                
                etf_info.append({
                    'ticker': ticker,
                    'name': name,
                    'avg_volume': avg_volume,
                    'avg_value': avg_value
                })
        except Exception as e:
            continue
    
    etf_df = pd.DataFrame(etf_info)
    print(f"정보 수집 완료: {len(etf_df)}개")
    print()

except Exception as e:
    print(f"❌ PyKRX 조회 실패: {e}")
    print("대체 방법으로 진행합니다...")
    
    # 수동으로 주요 ETF 목록 정의
    major_etfs = [
        '069500',  # KODEX 200
        '102110',  # TIGER 200
        '091160',  # KODEX 반도체
        '091180',  # KODEX 자동차
        '091170',  # KODEX 은행
        '091230',  # KODEX 철강
        '102780',  # KODEX 삼성그룹
        '114800',  # KODEX 인버스
        '122630',  # KODEX 레버리지
        '133690',  # TIGER 미국S&P500
        '138230',  # TIGER 미국나스닥100
        '143850',  # TIGER 미국다우존스30
        '148070',  # KOSEF 국고채10년
        '152100',  # ARIRANG 200
        '157490',  # TIGER 2차전지테마
        '182480',  # TIGER 200IT
        '192090',  # TIGER 200건설
        '217770',  # TIGER 200에너지화학
        '227540',  # TIGER 200중공업
        '237350',  # TIGER 200생활소비재
        '251340',  # KODEX 코스닥150
        '252670',  # KODEX 200선물인버스2X
        '253150',  # TIGER 코스닥150
        '261140',  # KODEX KRX300
        '278530',  # KODEX 200TR
        '292150',  # TIGER 200선물인버스2X
        '305720',  # KODEX 2차전지산업
        '364690',  # KBSTAR 200
        '365040',  # TIGER 200선물레버리지
        '371460',  # TIGER 차이나전기차SOLACTIVE
    ]
    
    etf_df = pd.DataFrame({'ticker': major_etfs})
    print(f"수동 ETF 목록: {len(etf_df)}개")
    print()

# 2. ETF 필터링
print("2. ETF 필터링")
print("-" * 70)

# 제외 키워드
exclude_keywords = ['레버리지', '인버스', '곱버스', '2X', '3X', '-1X', 'Short']

if 'name' in etf_df.columns:
    # 이름 기반 필터링
    filtered_df = etf_df[~etf_df['name'].str.contains('|'.join(exclude_keywords), na=False)]
    
    # 거래대금 필터링 (10억원 이상)
    if 'avg_value' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['avg_value'] > 1_000_000_000]
    
    print(f"필터링 후: {len(filtered_df)}개")
    print()
    
    # 상위 50개 선택
    if 'avg_value' in filtered_df.columns:
        filtered_df = filtered_df.nlargest(50, 'avg_value')
    else:
        filtered_df = filtered_df.head(50)
else:
    # 수동 목록은 그대로 사용
    filtered_df = etf_df

selected_tickers = filtered_df['ticker'].tolist()
print(f"최종 선택: {len(selected_tickers)}개 ETF")
print()

# 유니버스 저장
universe_file = PROJECT_ROOT / 'data' / 'universe' / 'etf_universe.csv'
universe_file.parent.mkdir(parents=True, exist_ok=True)
filtered_df.to_csv(universe_file, index=False, encoding='utf-8-sig')
print(f"✅ 유니버스 저장: {universe_file}")
print()

# 3. 가격 데이터 수집
print("3. 가격 데이터 수집 (2022-01-01 ~ 2025-11-07)")
print("-" * 70)

start_date = date(2022, 1, 1)
end_date = date.today()

print(f"기간: {start_date} ~ {end_date}")
print(f"종목 수: {len(selected_tickers)}개")
print()

from infra.data.loader import load_price_data

try:
    print("데이터 로딩 중... (시간이 걸릴 수 있습니다)")
    price_data = load_price_data(selected_tickers, start_date, end_date)
    
    print(f"✅ 데이터 로드 완료")
    print(f"   Shape: {price_data.shape}")
    print(f"   Columns: {price_data.columns.tolist()}")
    print(f"   Index levels: {price_data.index.names}")
    print()
    
    # 데이터 품질 확인
    print("4. 데이터 품질 확인")
    print("-" * 70)
    
    # 종목별 데이터 수
    if isinstance(price_data.index, pd.MultiIndex):
        ticker_counts = price_data.groupby(level=0).size()
        print(f"종목별 데이터 수:")
        print(ticker_counts.describe())
        print()
        
        # 데이터가 부족한 종목
        min_required = 500  # 최소 500일 (약 2년)
        insufficient = ticker_counts[ticker_counts < min_required]
        if len(insufficient) > 0:
            print(f"⚠️ 데이터 부족 종목 ({len(insufficient)}개):")
            for ticker, count in insufficient.items():
                print(f"   {ticker}: {count}일")
            print()
    
    # 결측치 확인
    missing = price_data.isnull().sum()
    if missing.sum() > 0:
        print("⚠️ 결측치:")
        print(missing[missing > 0])
        print()
    else:
        print("✅ 결측치 없음")
        print()
    
    # 샘플 데이터 출력
    print("샘플 데이터:")
    print(price_data.head(10))
    print()
    
    # 5. 캐시 저장 확인
    print("5. 캐시 저장 확인")
    print("-" * 70)
    
    cache_dir = PROJECT_ROOT / 'data' / 'cache' / 'ohlcv'
    parquet_files = list(cache_dir.glob('*.parquet'))
    stock_files = [f for f in parquet_files if not f.stem.isdigit() or len(f.stem) != 8]
    
    print(f"캐시된 파일 수: {len(stock_files)}개")
    print()
    
    # 6. 요약
    print("=" * 70)
    print("데이터 준비 완료")
    print("=" * 70)
    print(f"✅ 선택된 ETF: {len(selected_tickers)}개")
    print(f"✅ 데이터 기간: {start_date} ~ {end_date}")
    print(f"✅ 데이터 Shape: {price_data.shape}")
    print(f"✅ 캐시 파일: {len(stock_files)}개")
    print()
    print("다음 단계: 기본 백테스트")
    print("  python scripts/phase2/run_backtest.py")
    print()
    
except Exception as e:
    print(f"❌ 데이터 로드 실패: {e}")
    import traceback
    traceback.print_exc()
    print()
    print("해결 방법:")
    print("1. 네트워크 연결 확인")
    print("2. PyKRX, FinanceDataReader 설치 확인")
    print("3. 종목 코드 확인")

print("=" * 70)
print("2단계 완료")
print("=" * 70)
