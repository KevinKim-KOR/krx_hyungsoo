# -*- coding: utf-8 -*-
"""
extensions/tuning/split.py
튜닝/검증 체계 v2.1 - Split 및 거래일 스냅 함수

문서 참조: docs/tuning/00_overview.md 2.2~2.5절
"""
import logging
from datetime import date, timedelta
from typing import List, Optional, Tuple
import warnings

from extensions.tuning.types import Period, SplitConfig, LOOKBACK_TRADING_DAYS

logger = logging.getLogger(__name__)


def snap_start(dt: date, trading_calendar: List[date]) -> date:
    """
    시작일: 휴장일이면 다음 영업일로 스냅
    
    문서 참조: docs/tuning/00_overview.md 2.5절
    
    Args:
        dt: 스냅할 날짜
        trading_calendar: 거래일 리스트 (정렬됨)
        
    Returns:
        스냅된 거래일
    """
    if not trading_calendar:
        raise ValueError("trading_calendar가 비어있습니다")
    
    calendar_set = set(trading_calendar)
    max_date = max(trading_calendar)
    
    while dt not in calendar_set:
        dt = dt + timedelta(days=1)
        if dt > max_date:
            raise ValueError(f"시작일({dt})이 거래일 범위를 초과합니다")
    
    return dt


def snap_end(dt: date, trading_calendar: List[date]) -> date:
    """
    종료일: 휴장일이면 이전 영업일로 스냅
    
    문서 참조: docs/tuning/00_overview.md 2.5절
    
    Args:
        dt: 스냅할 날짜
        trading_calendar: 거래일 리스트 (정렬됨)
        
    Returns:
        스냅된 거래일
    """
    if not trading_calendar:
        raise ValueError("trading_calendar가 비어있습니다")
    
    calendar_set = set(trading_calendar)
    min_date = min(trading_calendar)
    
    while dt not in calendar_set:
        dt = dt - timedelta(days=1)
        if dt < min_date:
            raise ValueError(f"종료일({dt})이 거래일 범위를 벗어납니다")
    
    return dt


def calculate_split(
    total_months: int,
    min_val: int = 6,
    min_test: int = 6,
    min_train: int = 8
) -> Tuple[int, int, int, List[str]]:
    """
    최소개월 우선 Split 계산
    
    문서 참조: docs/tuning/00_overview.md 2.3절
    
    Args:
        total_months: 전체 기간 (개월)
        min_val: 최소 Val 기간 (기본 6개월)
        min_test: 최소 Test 기간 (기본 6개월)
        min_train: 최소 Train 기간 (기본 8개월)
        
    Returns:
        (train_months, val_months, test_months, warnings)
        
    Raises:
        ValueError: 전체 기간이 16개월 미만인 경우
    """
    split_warnings = []
    required = min_val + min_test + min_train  # 20개월
    
    if total_months < 16:
        raise ValueError(f"전체 기간이 16개월 미만입니다: {total_months}개월 (최소 16개월 필요)")
    
    if total_months < required:
        # 예외 모드: 4/4/나머지 최소값
        val_months = 4
        test_months = 4
        train_months = total_months - val_months - test_months
        split_warnings.append(f"⚠️ Val/Test가 최소값(4개월)으로 설정되었습니다. (전체: {total_months}개월)")
    else:
        # 정상 모드: 6/6/나머지
        val_months = min_val
        test_months = min_test
        train_months = total_months - val_months - test_months
    
    logger.info(f"Split 계산: Train={train_months}M, Val={val_months}M, Test={test_months}M")
    
    return train_months, val_months, test_months, split_warnings


def get_lookback_start(
    end_date: date,
    lookback_months: int,
    trading_calendar: List[date]
) -> date:
    """
    거래일 기준 룩백 시작일 계산
    
    문서 참조: docs/tuning/01_metrics_guardrails.md 5.4절
    
    Args:
        end_date: 종료일
        lookback_months: 룩백 기간 (3, 6, 12)
        trading_calendar: 거래일 리스트
        
    Returns:
        룩백 시작일
        
    Raises:
        ValueError: 데이터 부족 시
    """
    # end_date 스냅
    end_date = snap_end(end_date, trading_calendar)
    
    # 거래일 수 확인
    trading_days = LOOKBACK_TRADING_DAYS.get(lookback_months)
    if trading_days is None:
        raise ValueError(f"지원하지 않는 룩백 기간: {lookback_months}개월")
    
    # end_date 이전 거래일 필터링
    calendar_before_end = [d for d in trading_calendar if d <= end_date]
    
    if len(calendar_before_end) < trading_days:
        raise ValueError(
            f"데이터 부족: {trading_days}거래일 필요, {len(calendar_before_end)}일 존재"
        )
    
    # end_date 포함해서 trading_days개 확보 → 시작일
    return calendar_before_end[-trading_days]


def create_period(
    start_date: date,
    end_date: date,
    trading_calendar: List[date],
    split_config: Optional[SplitConfig] = None,
    include_test: bool = False
) -> Period:
    """
    Period 구조 생성
    
    문서 참조: docs/tuning/04_implementation.md period 구조 표준화
    
    Args:
        start_date: 전체 시작일
        end_date: 전체 종료일
        trading_calendar: 거래일 리스트
        split_config: Split 설정 (None이면 기본값 사용)
        include_test: Test 기간 포함 여부 (튜닝 중에는 False)
        
    Returns:
        Period 객체
    """
    if split_config is None:
        split_config = SplitConfig()
    
    # 시작/종료일 스냅
    snapped_start = snap_start(start_date, trading_calendar)
    snapped_end = snap_end(end_date, trading_calendar)
    
    # 전체 기간 계산 (개월)
    total_days = (snapped_end - snapped_start).days
    total_months = total_days // 30
    
    # Split 계산
    train_months, val_months, test_months, split_warnings = calculate_split(
        total_months,
        min_val=split_config.min_val_months,
        min_test=split_config.min_test_months,
        min_train=split_config.min_train_months
    )
    
    # 실제 적용값 저장
    split_config.applied_train_months = train_months
    split_config.applied_val_months = val_months
    split_config.applied_test_months = test_months
    
    # 기간 경계 계산
    train_end_approx = snapped_start + timedelta(days=train_months * 30)
    val_end_approx = train_end_approx + timedelta(days=val_months * 30)
    
    # 거래일로 스냅
    train_start = snapped_start
    train_end = snap_end(train_end_approx, trading_calendar)
    
    val_start = snap_start(train_end + timedelta(days=1), trading_calendar)
    val_end = snap_end(val_end_approx, trading_calendar)
    
    period = Period(
        start_date=snapped_start,
        end_date=snapped_end,
        train={'start': train_start, 'end': train_end},
        val={'start': val_start, 'end': val_end},
        test=None
    )
    
    # Test 기간 (Gate 3 이후에만)
    if include_test:
        test_start = snap_start(val_end + timedelta(days=1), trading_calendar)
        test_end = snapped_end
        period.test = {'start': test_start, 'end': test_end}
    
    # 경고 로깅
    for w in split_warnings:
        logger.warning(w)
    
    return period


def create_period_for_lookback(
    end_date: date,
    lookback_months: int,
    trading_calendar: List[date],
    split_config: Optional[SplitConfig] = None,
    include_test: bool = False
) -> Period:
    """
    룩백 기반 Period 생성
    
    Args:
        end_date: 종료일
        lookback_months: 룩백 기간 (3, 6, 12)
        trading_calendar: 거래일 리스트
        split_config: Split 설정
        include_test: Test 기간 포함 여부
        
    Returns:
        Period 객체
    """
    start_date = get_lookback_start(end_date, lookback_months, trading_calendar)
    
    return create_period(
        start_date=start_date,
        end_date=end_date,
        trading_calendar=trading_calendar,
        split_config=split_config,
        include_test=include_test
    )
