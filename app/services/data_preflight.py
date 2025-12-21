# -*- coding: utf-8 -*-
"""
app/services/data_preflight.py
실데이터 사전검증(Preflight) - Phase 1.6

튜닝 루프 시작 전에 데이터 품질 문제를 사전에 걸러낸다.
- parquet 파일 읽기 가능 여부
- 날짜 범위 커버리지
- 필수 컬럼 존재 여부
"""
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# 필수 컬럼 목록
REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


@dataclass
class TickerPreflightResult:
    """개별 티커 검증 결과"""

    ticker: str
    ok: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    data_start: Optional[date] = None
    data_end: Optional[date] = None
    row_count: int = 0
    missing_columns: List[str] = field(default_factory=list)
    coverage_ratio: float = 0.0  # 요청 기간 대비 실제 데이터 비율


@dataclass
class PreflightReport:
    """Preflight 검증 결과 보고서"""

    ok: bool
    fail_count: int
    total_count: int
    failures: List[str]  # 실패 코드 리스트 (예: "PARQUET_READ_FAIL:069500")
    ticker_results: Dict[str, TickerPreflightResult] = field(default_factory=dict)
    sample_stats: Dict[str, Any] = field(default_factory=dict)

    # Phase 2.1 추가: data_digest (데이터 건전성 해시)
    data_digest: str = ""  # 데이터 상태 해시 (재현성 추적용)
    common_period_start: Optional[date] = None  # 종목별 공통 기간 시작
    common_period_end: Optional[date] = None  # 종목별 공통 기간 종료

    @property
    def pass_count(self) -> int:
        return self.total_count - self.fail_count

    @property
    def pass_ratio(self) -> float:
        return self.pass_count / self.total_count if self.total_count > 0 else 0.0


class DataPreflightService:
    """
    데이터 사전검증 서비스

    튜닝 시작 전에 데이터 품질을 검증한다.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        min_coverage_ratio: float = 0.8,
        min_pass_ratio: float = 0.5,
    ):
        """
        Args:
            data_dir: 데이터 디렉토리 (기본: data/price)
            min_coverage_ratio: 최소 날짜 커버리지 비율 (기본: 80%)
            min_pass_ratio: 전체 티커 중 최소 통과 비율 (기본: 50%)
        """
        self.data_dir = data_dir or Path("data/price")
        self.min_coverage_ratio = min_coverage_ratio
        self.min_pass_ratio = min_pass_ratio

    def run(
        self,
        universe_codes: List[str],
        start_date: date,
        end_date: date,
        data_version: str = "real_v1",
    ) -> PreflightReport:
        """
        Preflight 검증 실행

        Args:
            universe_codes: 검증할 티커 코드 리스트
            start_date: 시작일
            end_date: 종료일
            data_version: 데이터 버전

        Returns:
            PreflightReport
        """
        failures: List[str] = []
        ticker_results: Dict[str, TickerPreflightResult] = {}

        for ticker in universe_codes:
            result = self._check_ticker(ticker, start_date, end_date)
            ticker_results[ticker] = result

            if not result.ok:
                failures.append(f"{result.error_code}:{ticker}")

        fail_count = len(failures)
        total_count = len(universe_codes)
        pass_ratio = (
            (total_count - fail_count) / total_count if total_count > 0 else 0.0
        )

        # 전체 통과 여부 결정
        ok = fail_count == 0 or pass_ratio >= self.min_pass_ratio

        # 샘플 통계
        sample_stats = self._compute_sample_stats(ticker_results, start_date, end_date)

        # Phase 2.1: data_digest 해시 및 공통 기간 계산
        data_digest = self._compute_data_digest(ticker_results, start_date, end_date)
        common_start, common_end = self._compute_common_period(ticker_results)

        report = PreflightReport(
            ok=ok,
            fail_count=fail_count,
            total_count=total_count,
            failures=failures,
            ticker_results=ticker_results,
            sample_stats=sample_stats,
            data_digest=data_digest,
            common_period_start=common_start,
            common_period_end=common_end,
        )

        # 로그 출력
        self._log_report(report)

        return report

    def _check_ticker(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> TickerPreflightResult:
        """개별 티커 검증"""
        import pandas as pd

        from app.services.data_locator import resolve_ticker_path

        # parquet 파일 경로 (DataLocator로 해결)
        parquet_path = resolve_ticker_path(ticker, self.data_dir)

        # 1. 파일 존재 여부
        if parquet_path is None:
            return TickerPreflightResult(
                ticker=ticker,
                ok=False,
                error_code="FILE_NOT_FOUND",
                error_message=f"파일 없음: {self.data_dir}/{ticker}.parquet (및 변형)",
            )

        # 2. parquet 읽기 시도
        try:
            df = pd.read_parquet(parquet_path)
        except Exception as e:
            return TickerPreflightResult(
                ticker=ticker,
                ok=False,
                error_code="PARQUET_READ_FAIL",
                error_message=str(e),
            )

        # 3. 필수 컬럼 확인
        missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        if missing_columns:
            return TickerPreflightResult(
                ticker=ticker,
                ok=False,
                error_code="MISSING_COLUMNS",
                error_message=f"필수 컬럼 누락: {missing_columns}",
                missing_columns=missing_columns,
            )

        # 4. 날짜 범위 확인
        if df.index.name != "Date" and "Date" in df.columns:
            df = df.set_index("Date")

        try:
            df.index = pd.to_datetime(df.index)
        except Exception:
            pass

        if len(df) == 0:
            return TickerPreflightResult(
                ticker=ticker,
                ok=False,
                error_code="EMPTY_DATA",
                error_message="데이터가 비어있음",
            )

        data_start = df.index.min().date()
        data_end = df.index.max().date()

        # 5. 커버리지 계산
        # 요청 기간 내 실제 데이터 일수 / 요청 기간 거래일 수 (대략 계산)
        mask = (df.index.date >= start_date) & (df.index.date <= end_date)
        filtered_df = df[mask]

        # 요청 기간의 대략적인 거래일 수 (연 250일 기준)
        total_days = (end_date - start_date).days
        expected_trading_days = int(total_days * 250 / 365)
        actual_trading_days = len(filtered_df)

        coverage_ratio = (
            actual_trading_days / expected_trading_days
            if expected_trading_days > 0
            else 0.0
        )

        # 커버리지 부족 체크
        if coverage_ratio < self.min_coverage_ratio:
            return TickerPreflightResult(
                ticker=ticker,
                ok=False,
                error_code="LOW_COVERAGE",
                error_message=f"커버리지 부족: {coverage_ratio:.1%} < {self.min_coverage_ratio:.1%}",
                data_start=data_start,
                data_end=data_end,
                row_count=len(filtered_df),
                coverage_ratio=coverage_ratio,
            )

        # 모든 검증 통과
        return TickerPreflightResult(
            ticker=ticker,
            ok=True,
            data_start=data_start,
            data_end=data_end,
            row_count=len(filtered_df),
            coverage_ratio=coverage_ratio,
        )

    def _compute_sample_stats(
        self,
        ticker_results: Dict[str, TickerPreflightResult],
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """샘플 통계 계산"""
        ok_results = [r for r in ticker_results.values() if r.ok]
        fail_results = [r for r in ticker_results.values() if not r.ok]

        # 에러 코드별 분포
        error_distribution: Dict[str, int] = {}
        for r in fail_results:
            code = r.error_code or "UNKNOWN"
            error_distribution[code] = error_distribution.get(code, 0) + 1

        # 커버리지 통계
        coverages = [r.coverage_ratio for r in ok_results if r.coverage_ratio > 0]
        avg_coverage = sum(coverages) / len(coverages) if coverages else 0.0
        min_coverage = min(coverages) if coverages else 0.0

        return {
            "requested_period": f"{start_date} ~ {end_date}",
            "total_tickers": len(ticker_results),
            "ok_count": len(ok_results),
            "fail_count": len(fail_results),
            "error_distribution": error_distribution,
            "avg_coverage": avg_coverage,
            "min_coverage": min_coverage,
            "ok_tickers_sample": [r.ticker for r in ok_results[:5]],
            "fail_tickers_sample": [r.ticker for r in fail_results[:5]],
        }

    def _compute_data_digest(
        self,
        ticker_results: Dict[str, TickerPreflightResult],
        start_date: date,
        end_date: date,
    ) -> str:
        """
        Phase 2.1: 데이터 건전성 해시 계산

        해시 구성 요소:
        - 티커 목록 (정렬)
        - 각 티커의 row_count, data_start, data_end
        - 요청 기간

        이 해시가 같으면 "같은 데이터 상태"로 간주
        """
        import hashlib

        ok_results = sorted(
            [r for r in ticker_results.values() if r.ok],
            key=lambda x: x.ticker
        )

        digest_parts = [
            f"period:{start_date}~{end_date}",
            f"tickers:{len(ok_results)}",
        ]

        for r in ok_results:
            digest_parts.append(
                f"{r.ticker}:{r.row_count}:{r.data_start}:{r.data_end}"
            )

        digest_str = "|".join(digest_parts)
        return hashlib.sha256(digest_str.encode()).hexdigest()[:16]

    def _compute_common_period(
        self,
        ticker_results: Dict[str, TickerPreflightResult],
    ) -> tuple:
        """
        Phase 2.1: 종목별 공통 기간(intersection) 계산

        Returns:
            (common_start, common_end) 또는 (None, None)
        """
        ok_results = [r for r in ticker_results.values() if r.ok and r.data_start and r.data_end]

        if not ok_results:
            return (None, None)

        # 공통 기간 = max(모든 시작일), min(모든 종료일)
        common_start = max(r.data_start for r in ok_results)
        common_end = min(r.data_end for r in ok_results)

        if common_start > common_end:
            # 공통 기간 없음
            return (None, None)

        return (common_start, common_end)

    def _log_report(self, report: PreflightReport):
        """보고서 로그 출력"""
        if report.ok:
            logger.info(
                f"PREFLIGHT OK: {report.pass_count}/{report.total_count} 티커 통과 "
                f"(pass_ratio={report.pass_ratio:.1%})"
            )
        else:
            logger.warning(
                f"PREFLIGHT FAIL: {report.fail_count}/{report.total_count} 티커 실패 "
                f"(pass_ratio={report.pass_ratio:.1%})"
            )
            for failure in report.failures[:10]:
                logger.warning(f"  - {failure}")
            if len(report.failures) > 10:
                logger.warning(f"  ... 외 {len(report.failures) - 10}건")

            # 디버그 정보 출력 (FILE_NOT_FOUND 시 원인 파악용)
            self._log_debug_info(report)

    def _log_debug_info(self, report: PreflightReport):
        """FILE_NOT_FOUND 디버그 정보 출력 (원인 3초 컷)"""
        import glob

        # FILE_NOT_FOUND 에러가 있는지 확인
        file_not_found_count = sum(
            1 for f in report.failures if f.startswith("FILE_NOT_FOUND:")
        )
        if file_not_found_count == 0:
            return

        logger.warning("=" * 60)
        logger.warning("[PREFLIGHT DEBUG] FILE_NOT_FOUND 원인 분석")
        logger.warning("=" * 60)

        # 1. data_root, expected_pattern
        data_root = str(self.data_dir.absolute())
        expected_pattern = f"{data_root}/{{ticker}}.parquet"
        logger.warning(f"  data_root: {data_root}")
        logger.warning(f"  expected_pattern: {expected_pattern}")

        # 2. 첫 번째 실패 티커의 expected_full_path
        first_fail_ticker = None
        for ticker, result in report.ticker_results.items():
            if result.error_code == "FILE_NOT_FOUND":
                first_fail_ticker = ticker
                break

        if first_fail_ticker:
            expected_full_path = self.data_dir / f"{first_fail_ticker}.parquet"
            logger.warning(f"  expected_full_path (첫 번째 실패): {expected_full_path}")

        # 3. root 하위 실제 파일 20개 샘플 (glob 결과)
        logger.warning(f"  [glob 샘플] {data_root}/*.parquet (최대 20개):")
        parquet_files = list(self.data_dir.glob("*.parquet"))[:20]
        if parquet_files:
            for f in parquet_files:
                logger.warning(f"    - {f.name}")
        else:
            logger.warning(f"    (parquet 파일 없음)")

            # parquet 없으면 다른 파일 확인
            all_files = list(self.data_dir.glob("*"))[:20]
            if all_files:
                logger.warning(f"  [glob 샘플] {data_root}/* (최대 20개):")
                for f in all_files:
                    logger.warning(f"    - {f.name}")
            else:
                logger.warning(f"    (디렉토리가 비어있거나 존재하지 않음)")

        # 4. 티커가 파일명에 매칭되는지 (leading zero 포함 여부) 체크
        if first_fail_ticker and parquet_files:
            logger.warning(f"  [leading zero 체크] ticker={first_fail_ticker}")

            # 파일명에서 티커 추출 패턴들
            file_names = [f.stem for f in parquet_files]  # 확장자 제외
            logger.warning(f"    파일명 샘플: {file_names[:5]}")

            # 매칭 시도
            exact_match = first_fail_ticker in file_names
            logger.warning(f"    exact_match ({first_fail_ticker}): {exact_match}")

            # leading zero 없는 버전
            ticker_no_leading = first_fail_ticker.lstrip("0")
            no_leading_match = ticker_no_leading in file_names
            logger.warning(
                f"    no_leading_zero ({ticker_no_leading}): {no_leading_match}"
            )

            # A 접두사 버전
            ticker_with_a = f"A{first_fail_ticker}"
            a_prefix_match = ticker_with_a in file_names
            logger.warning(f"    A_prefix ({ticker_with_a}): {a_prefix_match}")

            # 부분 매칭 (ticker가 파일명에 포함되는지)
            partial_matches = [fn for fn in file_names if first_fail_ticker in fn]
            if partial_matches:
                logger.warning(f"    partial_matches: {partial_matches[:5]}")

        logger.warning("=" * 60)


def run_preflight(
    universe_codes: List[str],
    start_date: date,
    end_date: date,
    data_version: str = "real_v1",
    data_dir: Optional[Path] = None,
    min_coverage_ratio: float = 0.8,
    min_pass_ratio: float = 0.5,
) -> PreflightReport:
    """
    Preflight 검증 실행 (편의 함수)

    Args:
        universe_codes: 검증할 티커 코드 리스트
        start_date: 시작일
        end_date: 종료일
        data_version: 데이터 버전
        data_dir: 데이터 디렉토리
        min_coverage_ratio: 최소 날짜 커버리지 비율
        min_pass_ratio: 전체 티커 중 최소 통과 비율

    Returns:
        PreflightReport
    """
    service = DataPreflightService(
        data_dir=data_dir,
        min_coverage_ratio=min_coverage_ratio,
        min_pass_ratio=min_pass_ratio,
    )
    return service.run(universe_codes, start_date, end_date, data_version)
