#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2 재테스트 - 유니버스 조정
최신 테마 ETF 포함 (AI, 전력, 2차전지 등)
"""
import sys
from pathlib import Path
import pandas as pd

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 로거 생성
from scripts.phase2.utils.logger import create_logger
logger = create_logger("2_adjust_universe", PROJECT_ROOT)

logger.info("Phase 2 재테스트 - 유니버스 조정")
logger.info("최신 테마 ETF 포함 (AI, 전력, 2차전지 등)")

# 1. 기존 유니버스 로드
logger.section("1. 기존 유니버스 로드")

universe_file = PROJECT_ROOT / 'data' / 'universe' / 'etf_universe.csv'
existing_df = pd.read_csv(universe_file, encoding='utf-8-sig')

logger.info(f"기존 유니버스: {len(existing_df)}개")
logger.info(f"평균 거래대금: {existing_df['avg_value'].mean()/1e8:.1f}억")

# 2. 전체 ETF 정보 로드
logger.section("2. 전체 ETF 정보 로드")

etf_info_file = PROJECT_ROOT / 'data' / 'universe' / 'etf_info_raw.csv'
all_etf_df = pd.read_csv(etf_info_file, encoding='utf-8-sig')

logger.info(f"전체 ETF: {len(all_etf_df)}개")

# 3. 최신 테마 ETF 선별
logger.section("3. 최신 테마 ETF 선별")

# 테마 키워드 정의
theme_keywords = {
    'AI': ['AI', '인공지능', '생성형AI', '온디바이스AI'],
    '전력': ['전력', '원자력', '전기'],
    '2차전지': ['2차전지', '배터리', '양극재'],
    '반도체': ['반도체', '메모리', '비메모리'],
    '로봇': ['로봇', '자동화'],
    '우주항공': ['우주', '방산', 'K방산'],
}

# 테마별 ETF 찾기
theme_etfs = []
for theme, keywords in theme_keywords.items():
    logger.info(f"\n[{theme}] 테마 ETF 검색:")
    
    for keyword in keywords:
        matched = all_etf_df[all_etf_df['name'].str.contains(keyword, na=False)]
        
        if len(matched) > 0:
            logger.info(f"  '{keyword}' 키워드: {len(matched)}개")
            
            for idx, row in matched.head(5).iterrows():
                # 레버리지/인버스 제외
                if any(x in row['name'] for x in ['레버리지', '인버스', '2X', '3X', 'Short']):
                    continue
                
                # 거래대금 1억 이상
                if row['avg_value'] < 100_000_000:
                    continue
                
                theme_etfs.append({
                    'ticker': row['ticker'],
                    'name': row['name'],
                    'theme': theme,
                    'avg_value': row['avg_value'],
                    'avg_volume': row['avg_volume'],
                    'last_price': row['last_price']
                })
                
                logger.info(f"    {row['ticker']} - {row['name'][:30]:30s} (거래대금: {row['avg_value']/1e8:.1f}억)")

# 중복 제거
theme_df = pd.DataFrame(theme_etfs)
if len(theme_df) > 0:
    theme_df = theme_df.drop_duplicates(subset=['ticker'])
    logger.info(f"\n중복 제거 후: {len(theme_df)}개")

# 4. 유니버스 통합
logger.section("4. 유니버스 통합")

# 기존 유니버스 (44개)
existing_tickers = set(existing_df['ticker'].tolist())
logger.info(f"기존 유니버스: {len(existing_tickers)}개")

# 테마 ETF (신규)
if len(theme_df) > 0:
    theme_tickers = set(theme_df['ticker'].tolist())
    new_tickers = theme_tickers - existing_tickers
    
    logger.info(f"테마 ETF: {len(theme_tickers)}개")
    logger.info(f"신규 추가: {len(new_tickers)}개")
    
    if len(new_tickers) > 0:
        logger.info("\n신규 추가 ETF:")
        for ticker in new_tickers:
            row = theme_df[theme_df['ticker'] == ticker].iloc[0]
            logger.info(f"  {ticker} - {row['name'][:30]:30s} [{row['theme']}] (거래대금: {row['avg_value']/1e8:.1f}억)")
    
    # 통합
    combined_df = pd.concat([
        existing_df,
        theme_df[theme_df['ticker'].isin(new_tickers)]
    ], ignore_index=True)
    
    # 거래대금 기준 정렬
    combined_df = combined_df.sort_values('avg_value', ascending=False)
    
    logger.success(f"통합 유니버스: {len(combined_df)}개")
else:
    logger.warn("테마 ETF를 찾지 못했습니다. 기존 유니버스 유지")
    combined_df = existing_df

# 5. 데이터 수집 (신규 ETF만)
logger.section("5. 신규 ETF 데이터 수집")

if len(theme_df) > 0 and len(new_tickers) > 0:
    from datetime import date
    from infra.data.loader import load_price_data
    
    start_date = date(2022, 1, 1)
    end_date = date.today()
    
    logger.info(f"기간: {start_date} ~ {end_date}")
    logger.info(f"신규 종목 수: {len(new_tickers)}개")
    logger.info("데이터 로딩 중...")
    
    try:
        new_price_data = load_price_data(list(new_tickers), start_date, end_date)
        
        logger.success("데이터 로드 완료")
        logger.info(f"   Shape: {new_price_data.shape}")
        
        # 데이터 수 확인
        if isinstance(new_price_data.index, pd.MultiIndex):
            ticker_counts = new_price_data.groupby(level=0).size()
            
            logger.info("\n신규 종목별 데이터 수:")
            for ticker, count in ticker_counts.items():
                row = theme_df[theme_df['ticker'] == ticker].iloc[0]
                logger.info(f"  {ticker} ({row['name'][:20]:20s}): {count}일")
            
            # 데이터 부족 종목 (300일 미만)
            min_required = 300  # 최신 ETF는 기준 완화
            insufficient = ticker_counts[ticker_counts < min_required]
            
            if len(insufficient) > 0:
                logger.warn(f"\n데이터 부족 종목 ({len(insufficient)}개, <{min_required}일):")
                for ticker, count in insufficient.items():
                    logger.info(f"   {ticker}: {count}일")
                
                # 부족한 종목 제외
                sufficient_tickers = ticker_counts[ticker_counts >= min_required].index.tolist()
                logger.info(f"충분한 데이터 종목: {len(sufficient_tickers)}개")
                
                # 유니버스에서 제외
                combined_df = combined_df[
                    ~combined_df['ticker'].isin(insufficient.index) | 
                    combined_df['ticker'].isin(existing_tickers)
                ]
                logger.info(f"최종 유니버스: {len(combined_df)}개")
            else:
                logger.success("모든 신규 종목이 충분한 데이터를 가지고 있습니다")
        
    except Exception as e:
        logger.fail(f"데이터 로드 실패: {e}")
        logger.warn("신규 ETF 추가를 건너뜁니다")
        combined_df = existing_df
else:
    logger.info("신규 ETF가 없습니다")

# 6. 최종 유니버스 저장
logger.section("6. 최종 유니버스 저장")

# 백업
backup_file = PROJECT_ROOT / 'data' / 'universe' / 'etf_universe_backup.csv'
existing_df.to_csv(backup_file, index=False, encoding='utf-8-sig')
logger.success(f"기존 유니버스 백업: {backup_file}")

# 저장
combined_df.to_csv(universe_file, index=False, encoding='utf-8-sig')
logger.success(f"최종 유니버스 저장: {universe_file}")

# 7. 요약
logger.section("최종 요약")

logger.success(f"최종 유니버스: {len(combined_df)}개")
logger.info(f"  - 기존 유지: {len(existing_tickers)}개")
if len(theme_df) > 0:
    logger.info(f"  - 신규 추가: {len(combined_df) - len(existing_tickers)}개")
logger.info(f"평균 거래대금: {combined_df['avg_value'].mean()/1e8:.1f}억")

# 테마별 분포
if 'theme' in combined_df.columns:
    logger.info("\n테마별 분포:")
    theme_counts = combined_df['theme'].value_counts()
    for theme, count in theme_counts.items():
        logger.info(f"  {theme}: {count}개")

logger.info("\n다음 단계: 기본 백테스트")
logger.info("  python scripts/phase2/run_backtest.py")

# 데이터 요약 업데이트
import json
summary_file = PROJECT_ROOT / 'backtests' / 'phase2_retest' / 'data_summary.json'
if summary_file.exists():
    with open(summary_file, 'r', encoding='utf-8') as f:
        summary = json.load(f)
    
    summary['etf_count'] = len(combined_df)
    summary['adjusted'] = True
    summary['theme_etfs_added'] = len(combined_df) - len(existing_tickers)
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.success(f"데이터 요약 업데이트: {summary_file}")

logger.finish()
logger.info(f"\n로그 파일: {logger.log_file}")
