# -*- coding: utf-8 -*-
"""
scripts/maintenance/migrate_cache_index.py
캐시 파일의 인덱스 타입을 pd.Timestamp로 통일하는 마이그레이션 스크립트
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_cache_files(cache_dir: str, dry_run: bool = True):
    """
    캐시 파일의 인덱스 타입을 pd.Timestamp로 통일
    
    Args:
        cache_dir: 캐시 디렉토리 경로
        dry_run: True면 실제 수정 없이 검사만 수행
    """
    cache_path = Path(cache_dir)
    if not cache_path.exists():
        logger.error(f"캐시 디렉토리 없음: {cache_dir}")
        return
    
    parquet_files = list(cache_path.glob("*.parquet"))
    logger.info(f"총 {len(parquet_files)}개 파일 검사")
    
    stats = {
        "total": len(parquet_files),
        "needs_migration": 0,
        "already_ok": 0,
        "migrated": 0,
        "errors": 0
    }
    
    for file_path in parquet_files:
        try:
            df = pd.read_parquet(file_path)
            
            # 인덱스 타입 확인
            index_dtype = str(df.index.dtype)
            
            if index_dtype == "object":
                # datetime.date 또는 혼합 타입
                stats["needs_migration"] += 1
                logger.info(f"[마이그레이션 필요] {file_path.name}: index dtype={index_dtype}")
                
                if not dry_run:
                    # 인덱스를 pd.Timestamp로 변환
                    df.index = pd.to_datetime(df.index)
                    df.to_parquet(file_path)
                    stats["migrated"] += 1
                    logger.info(f"  -> 마이그레이션 완료")
                    
            elif "datetime" in index_dtype.lower():
                stats["already_ok"] += 1
                logger.debug(f"[정상] {file_path.name}: index dtype={index_dtype}")
            else:
                logger.warning(f"[알 수 없는 타입] {file_path.name}: index dtype={index_dtype}")
                
        except Exception as e:
            stats["errors"] += 1
            logger.error(f"[오류] {file_path.name}: {e}")
    
    # 결과 출력
    logger.info("=" * 50)
    logger.info("마이그레이션 결과:")
    logger.info(f"  총 파일: {stats['total']}")
    logger.info(f"  정상: {stats['already_ok']}")
    logger.info(f"  마이그레이션 필요: {stats['needs_migration']}")
    if not dry_run:
        logger.info(f"  마이그레이션 완료: {stats['migrated']}")
    logger.info(f"  오류: {stats['errors']}")
    
    if dry_run and stats["needs_migration"] > 0:
        logger.info("")
        logger.info("실제 마이그레이션을 수행하려면 --execute 옵션을 추가하세요:")
        logger.info("  python scripts/maintenance/migrate_cache_index.py --execute")
    
    return stats


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="캐시 인덱스 타입 마이그레이션")
    parser.add_argument(
        "--cache-dir",
        default="data/cache/ohlcv",
        help="캐시 디렉토리 경로 (기본: data/cache/ohlcv)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="실제 마이그레이션 수행 (기본: dry-run)"
    )
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    if dry_run:
        logger.info("=== DRY RUN 모드 (실제 수정 없음) ===")
    else:
        logger.info("=== 실행 모드 (파일 수정됨) ===")
    
    migrate_cache_files(args.cache_dir, dry_run=dry_run)


if __name__ == "__main__":
    main()
