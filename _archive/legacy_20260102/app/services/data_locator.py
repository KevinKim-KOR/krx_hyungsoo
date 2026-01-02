# -*- coding: utf-8 -*-
"""
app/services/data_locator.py
실데이터 파일 위치 해결 어댑터

여러 파일명 규약을 하나의 인터페이스로 흡수:
- {ticker}.parquet (예: 069500.parquet)
- A{ticker}.parquet (예: A069500.parquet)
- {ticker}_daily.parquet (예: 069500_daily.parquet)
- {ticker}/{ticker}.parquet (예: 069500/069500.parquet)
"""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DataLocatorConfig:
    """DataLocator 설정"""

    # 데이터 루트 디렉토리
    data_root: Path

    # 지원하는 파일명 패턴 (우선순위 순)
    # {ticker}는 실제 티커 코드로 대체됨
    patterns: List[str]

    # leading zero 처리 (예: 069500 -> 69500)
    try_strip_leading_zero: bool = True

    # A 접두사 처리 (예: 069500 -> A069500)
    try_a_prefix: bool = True


# 기본 설정
DEFAULT_LOCATOR_CONFIG = DataLocatorConfig(
    data_root=Path("data/price"),
    patterns=[
        "{ticker}.parquet",
        "A{ticker}.parquet",
        "{ticker}_daily.parquet",
        "{ticker}/{ticker}.parquet",
    ],
    try_strip_leading_zero=True,
    try_a_prefix=True,
)


class DataLocator:
    """
    실데이터 파일 위치 해결 어댑터

    여러 파일명 규약을 지원하며, resolve()가 못 찾으면 None 반환.
    """

    def __init__(self, config: Optional[DataLocatorConfig] = None):
        self.config = config or DEFAULT_LOCATOR_CONFIG
        self._cache: dict = {}  # 캐시: ticker -> path

    def resolve(self, ticker: str) -> Optional[Path]:
        """
        티커에 해당하는 parquet 파일 경로 반환

        Args:
            ticker: 티커 코드 (예: "069500")

        Returns:
            파일 경로 또는 None (못 찾으면)
        """
        # 캐시 확인
        if ticker in self._cache:
            return self._cache[ticker]

        # 티커 변형 목록 생성
        ticker_variants = self._generate_ticker_variants(ticker)

        # 각 패턴과 티커 변형 조합으로 파일 찾기
        for variant in ticker_variants:
            for pattern in self.config.patterns:
                path = self.config.data_root / pattern.format(ticker=variant)
                if path.exists():
                    self._cache[ticker] = path
                    logger.debug(f"DataLocator: {ticker} -> {path}")
                    return path

        # 못 찾음
        self._cache[ticker] = None
        return None

    def resolve_all(self, tickers: List[str]) -> dict:
        """
        여러 티커에 대해 resolve 실행

        Args:
            tickers: 티커 코드 리스트

        Returns:
            {ticker: path or None} 딕셔너리
        """
        return {ticker: self.resolve(ticker) for ticker in tickers}

    def _generate_ticker_variants(self, ticker: str) -> List[str]:
        """티커 변형 목록 생성 (원본, leading zero 제거, A 접두사 등)"""
        variants = [ticker]

        # leading zero 제거
        if self.config.try_strip_leading_zero and ticker.startswith("0"):
            stripped = ticker.lstrip("0")
            if stripped and stripped not in variants:
                variants.append(stripped)

        # A 접두사 추가
        if self.config.try_a_prefix:
            a_prefix = f"A{ticker}"
            if a_prefix not in variants:
                variants.append(a_prefix)

        return variants

    def get_debug_info(self, ticker: str) -> dict:
        """디버그 정보 반환"""
        variants = self._generate_ticker_variants(ticker)
        tried_paths = []

        for variant in variants:
            for pattern in self.config.patterns:
                path = self.config.data_root / pattern.format(ticker=variant)
                tried_paths.append(
                    {
                        "variant": variant,
                        "pattern": pattern,
                        "path": str(path),
                        "exists": path.exists(),
                    }
                )

        return {
            "ticker": ticker,
            "data_root": str(self.config.data_root.absolute()),
            "variants": variants,
            "tried_paths": tried_paths,
            "resolved": str(self.resolve(ticker)) if self.resolve(ticker) else None,
        }

    def clear_cache(self):
        """캐시 초기화"""
        self._cache.clear()


# 전역 인스턴스
_global_locator: Optional[DataLocator] = None


def get_data_locator(config: Optional[DataLocatorConfig] = None) -> DataLocator:
    """전역 DataLocator 인스턴스 반환"""
    global _global_locator
    if _global_locator is None or config is not None:
        _global_locator = DataLocator(config)
    return _global_locator


def resolve_ticker_path(
    ticker: str, data_root: Optional[Path] = None
) -> Optional[Path]:
    """
    티커에 해당하는 parquet 파일 경로 반환 (편의 함수)

    Args:
        ticker: 티커 코드
        data_root: 데이터 루트 디렉토리 (기본: data/price)

    Returns:
        파일 경로 또는 None
    """
    if data_root:
        config = DataLocatorConfig(
            data_root=data_root,
            patterns=DEFAULT_LOCATOR_CONFIG.patterns,
            try_strip_leading_zero=DEFAULT_LOCATOR_CONFIG.try_strip_leading_zero,
            try_a_prefix=DEFAULT_LOCATOR_CONFIG.try_a_prefix,
        )
        locator = DataLocator(config)
        return locator.resolve(ticker)
    else:
        return get_data_locator().resolve(ticker)
