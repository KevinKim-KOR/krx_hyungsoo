# -*- coding: utf-8 -*-
"""
scripts/update_cache.py
ETF 가격 캐시 업데이트 스크립트

사용법:
    python scripts/update_cache.py

crontab 설정 (매일 장 마감 후 17:00):
    0 17 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python scripts/update_cache.py
"""
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from pykrx import stock

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def get_etf_tickers():
    """유효한 ETF 티커 목록 반환"""
    from core.data.filtering import get_filtered_universe

    return get_filtered_universe()


def update_cache(days_back: int = 30):
    """
    캐시 데이터 업데이트

    Args:
        days_back: 업데이트할 기간 (일)
    """
    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    tickers = get_etf_tickers()
    logger.info(f"업데이트 대상: {len(tickers)}개 ETF")

    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    updated = 0
    failed = 0

    for ticker in tickers:
        try:
            cache_file = cache_dir / f"{ticker}.parquet"

            # 기존 캐시 로드
            if cache_file.exists():
                existing = pd.read_parquet(cache_file)
                last_date = existing.index.max()

                if isinstance(last_date, pd.Timestamp):
                    last_date = last_date.date()

                # 이미 최신이면 스킵
                if last_date >= end_date:
                    continue

                fetch_start = last_date + timedelta(days=1)
            else:
                existing = None
                fetch_start = start_date

            # 새 데이터 가져오기
            new_data = stock.get_etf_ohlcv_by_date(
                fetch_start.strftime("%Y%m%d"),
                end_date.strftime("%Y%m%d"),
                ticker,
            )

            if new_data.empty:
                continue

            # 인덱스를 datetime으로 변환
            new_data.index = pd.to_datetime(new_data.index)
            new_data.index.name = "날짜"

            # 컬럼명 변환 (한글 → 영문)
            column_map = {
                "시가": "open",
                "고가": "high",
                "저가": "low",
                "종가": "close",
                "거래량": "volume",
                "거래대금": "value",
                "NAV": "NAV",
            }
            new_data = new_data.rename(columns=column_map)

            # 기존 데이터와 병합
            if existing is not None:
                # 기존 컬럼 유지
                for col in existing.columns:
                    if col not in new_data.columns:
                        new_data[col] = 0

                combined = pd.concat([existing, new_data])
                combined = combined[~combined.index.duplicated(keep="last")]
                combined = combined.sort_index()
            else:
                combined = new_data

            # 저장
            combined.to_parquet(cache_file)
            updated += 1

            if updated % 50 == 0:
                logger.info(f"진행: {updated}/{len(tickers)}")

        except Exception as e:
            logger.warning(f"{ticker} 업데이트 실패: {e}")
            failed += 1

    logger.info(f"완료: {updated}개 업데이트, {failed}개 실패")
    return updated, failed


if __name__ == "__main__":
    logger.info("=== ETF 캐시 업데이트 시작 ===")
    updated, failed = update_cache()
    logger.info(f"=== 완료: {updated}개 업데이트, {failed}개 실패 ===")
