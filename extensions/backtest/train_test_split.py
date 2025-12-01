# -*- coding: utf-8 -*-
"""
extensions/backtest/train_test_split.py
Phase 0: 검증 프레임워크 - Train/Test 분리

목적:
- 모든 변경사항을 Train/Test 양쪽에서 검증
- 과적합 여부 확인
- 실전 성과 예측

사용법:
    from extensions.backtest.train_test_split import (
        simple_train_test_split,
        run_backtest_with_split,
        compare_train_test_results
    )
    
    # 기간 분리
    (train_start, train_end), (test_start, test_end) = simple_train_test_split(
        start_date=date(2022, 1, 1),
        end_date=date(2025, 11, 30),
        train_ratio=0.7
    )
    
    # 분리 백테스트 실행
    results = run_backtest_with_split(
        adapter=adapter,
        price_data=price_data,
        strategy=strategy,
        start_date=date(2022, 1, 1),
        end_date=date(2025, 11, 30),
        train_ratio=0.7
    )
    
    # 결과 비교
    compare_train_test_results(results)
"""
from typing import Dict, Tuple, Optional, Any
from datetime import date, timedelta
from dataclasses import dataclass
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class SplitPeriod:
    """분할 기간 정보"""
    name: str
    start_date: date
    end_date: date
    
    @property
    def days(self) -> int:
        """기간 일수"""
        return (self.end_date - self.start_date).days
    
    def __str__(self) -> str:
        return f"{self.name}: {self.start_date} ~ {self.end_date} ({self.days}일)"


@dataclass
class SplitResult:
    """분할 결과"""
    train: SplitPeriod
    test: SplitPeriod
    
    def __str__(self) -> str:
        return f"Train: {self.train}\nTest: {self.test}"


def simple_train_test_split(
    start_date: date,
    end_date: date,
    train_ratio: float = 0.7,
    min_train_days: int = 504,  # 최소 2년 (252 * 2)
    min_test_days: int = 126    # 최소 6개월
) -> Tuple[Tuple[date, date], Tuple[date, date]]:
    """
    간단한 Train/Test 분리 (시간순)
    
    Args:
        start_date: 전체 시작일
        end_date: 전체 종료일
        train_ratio: Train 비율 (기본 70%)
        min_train_days: 최소 Train 기간 (일)
        min_test_days: 최소 Test 기간 (일)
        
    Returns:
        ((train_start, train_end), (test_start, test_end))
        
    Raises:
        ValueError: 데이터 기간이 부족한 경우
    """
    total_days = (end_date - start_date).days
    
    # 최소 기간 검증
    min_total_days = min_train_days + min_test_days
    if total_days < min_total_days:
        logger.warning(
            f"데이터 기간 부족: {total_days}일 < {min_total_days}일 (최소)\n"
            f"권장: Train {min_train_days}일 + Test {min_test_days}일"
        )
        # 경고만 하고 진행 (비율대로 분할)
    
    # Train/Test 분할
    train_days = int(total_days * train_ratio)
    
    # 최소 기간 보장
    if train_days < min_train_days and total_days >= min_total_days:
        train_days = min_train_days
        logger.info(f"Train 기간을 최소값으로 조정: {train_days}일")
    
    test_days = total_days - train_days
    if test_days < min_test_days and total_days >= min_total_days:
        test_days = min_test_days
        train_days = total_days - test_days
        logger.info(f"Test 기간을 최소값으로 조정: {test_days}일")
    
    # 날짜 계산
    train_end = start_date + timedelta(days=train_days)
    test_start = train_end + timedelta(days=1)
    
    logger.info(f"Train/Test 분리 완료:")
    logger.info(f"  Train: {start_date} ~ {train_end} ({train_days}일, {train_ratio*100:.0f}%)")
    logger.info(f"  Test:  {test_start} ~ {end_date} ({test_days}일, {(1-train_ratio)*100:.0f}%)")
    
    return (start_date, train_end), (test_start, end_date)


def get_split_periods(
    start_date: date,
    end_date: date,
    train_ratio: float = 0.7
) -> SplitResult:
    """
    분할 기간 정보 반환
    
    Args:
        start_date: 전체 시작일
        end_date: 전체 종료일
        train_ratio: Train 비율
        
    Returns:
        SplitResult 객체
    """
    (train_start, train_end), (test_start, test_end) = simple_train_test_split(
        start_date, end_date, train_ratio
    )
    
    return SplitResult(
        train=SplitPeriod("Train", train_start, train_end),
        test=SplitPeriod("Test", test_start, test_end)
    )


def run_backtest_with_split(
    adapter: Any,
    price_data: pd.DataFrame,
    strategy: Any,
    start_date: date,
    end_date: date,
    train_ratio: float = 0.7,
    **kwargs
) -> Dict[str, Dict]:
    """
    Train/Test 분리 백테스트 실행
    
    Args:
        adapter: 백테스트 어댑터 (KRXMAPSAdapter 등)
        price_data: 가격 데이터
        strategy: 전략 객체
        start_date: 전체 시작일
        end_date: 전체 종료일
        train_ratio: Train 비율
        **kwargs: 어댑터에 전달할 추가 인자
        
    Returns:
        {
            'train': {...},  # Train 결과
            'test': {...},   # Test 결과
            'periods': SplitResult,  # 기간 정보
            'comparison': {...}  # 비교 결과
        }
    """
    # 기간 분리
    (train_start, train_end), (test_start, test_end) = simple_train_test_split(
        start_date, end_date, train_ratio
    )
    
    periods = SplitResult(
        train=SplitPeriod("Train", train_start, train_end),
        test=SplitPeriod("Test", test_start, test_end)
    )
    
    logger.info("=" * 60)
    logger.info("Train/Test 분리 백테스트 시작")
    logger.info("=" * 60)
    
    # Train 백테스트
    logger.info(f"\n[Train] {train_start} ~ {train_end}")
    logger.info("-" * 40)
    
    # 어댑터 리셋 (새 인스턴스 생성이 필요할 수 있음)
    train_results = adapter.run(
        price_data=price_data,
        strategy=strategy,
        start_date=train_start,
        end_date=train_end,
        **kwargs
    )
    
    logger.info(f"[Train] 완료: CAGR {train_results.get('cagr', 0):.2f}%, "
                f"Sharpe {train_results.get('sharpe_ratio', 0):.2f}, "
                f"MDD {train_results.get('max_drawdown', 0):.2f}%")
    
    # 어댑터 리셋 (중요!)
    adapter.reset()
    
    # Test 백테스트
    logger.info(f"\n[Test] {test_start} ~ {test_end}")
    logger.info("-" * 40)
    
    test_results = adapter.run(
        price_data=price_data,
        strategy=strategy,
        start_date=test_start,
        end_date=test_end,
        **kwargs
    )
    
    logger.info(f"[Test] 완료: CAGR {test_results.get('cagr', 0):.2f}%, "
                f"Sharpe {test_results.get('sharpe_ratio', 0):.2f}, "
                f"MDD {test_results.get('max_drawdown', 0):.2f}%")
    
    # 비교 결과 생성
    comparison = _compare_results(train_results, test_results)
    
    return {
        'train': train_results,
        'test': test_results,
        'periods': periods,
        'comparison': comparison
    }


def _compare_results(train: Dict, test: Dict) -> Dict:
    """
    Train/Test 결과 비교
    
    Args:
        train: Train 결과
        test: Test 결과
        
    Returns:
        비교 결과 딕셔너리
    """
    # 주요 지표 비교
    metrics = ['cagr', 'sharpe_ratio', 'max_drawdown', 'total_return_pct']
    
    comparison = {
        'metrics': {},
        'warnings': [],
        'is_overfit': False
    }
    
    for metric in metrics:
        train_val = train.get(metric, 0)
        test_val = test.get(metric, 0)
        
        # 차이 계산
        if train_val != 0:
            diff_pct = (test_val - train_val) / abs(train_val) * 100
        else:
            diff_pct = 0
        
        comparison['metrics'][metric] = {
            'train': train_val,
            'test': test_val,
            'diff': test_val - train_val,
            'diff_pct': diff_pct
        }
    
    # 과적합 경고 체크
    cagr_diff = comparison['metrics']['cagr']['diff_pct']
    sharpe_diff = comparison['metrics']['sharpe_ratio']['diff_pct']
    
    # CAGR이 50% 이상 하락하면 과적합 의심
    if cagr_diff < -50:
        comparison['warnings'].append(
            f"⚠️ CAGR 급락: Train {train.get('cagr', 0):.2f}% → Test {test.get('cagr', 0):.2f}% ({cagr_diff:.1f}%)"
        )
        comparison['is_overfit'] = True
    
    # Sharpe가 50% 이상 하락하면 과적합 의심
    if sharpe_diff < -50:
        comparison['warnings'].append(
            f"⚠️ Sharpe 급락: Train {train.get('sharpe_ratio', 0):.2f} → Test {test.get('sharpe_ratio', 0):.2f} ({sharpe_diff:.1f}%)"
        )
        comparison['is_overfit'] = True
    
    # Test MDD가 Train보다 50% 이상 악화
    mdd_train = abs(train.get('max_drawdown', 0))
    mdd_test = abs(test.get('max_drawdown', 0))
    if mdd_train > 0 and (mdd_test - mdd_train) / mdd_train > 0.5:
        comparison['warnings'].append(
            f"⚠️ MDD 악화: Train {train.get('max_drawdown', 0):.2f}% → Test {test.get('max_drawdown', 0):.2f}%"
        )
    
    # 정상 패턴 확인 (Train > Test는 일반적)
    if cagr_diff > -30 and sharpe_diff > -30:
        comparison['status'] = '✅ 정상 (Train/Test 차이 허용 범위)'
    elif comparison['is_overfit']:
        comparison['status'] = '❌ 과적합 의심'
    else:
        comparison['status'] = '⚠️ 주의 필요'
    
    return comparison


def compare_train_test_results(results: Dict, verbose: bool = True) -> Dict:
    """
    Train/Test 결과 비교 출력
    
    Args:
        results: run_backtest_with_split() 결과
        verbose: 상세 출력 여부
        
    Returns:
        비교 결과
    """
    comparison = results.get('comparison', {})
    periods = results.get('periods')
    
    if verbose:
        print("\n" + "=" * 70)
        print("📊 Train/Test 비교 결과")
        print("=" * 70)
        
        if periods:
            print(f"\n📅 기간:")
            print(f"  {periods.train}")
            print(f"  {periods.test}")
        
        print(f"\n📈 성과 비교:")
        print("-" * 70)
        print(f"{'지표':<20} {'Train':>15} {'Test':>15} {'차이':>15}")
        print("-" * 70)
        
        for metric, values in comparison.get('metrics', {}).items():
            train_val = values['train']
            test_val = values['test']
            diff = values['diff']
            
            # 포맷팅
            if metric in ['cagr', 'max_drawdown', 'total_return_pct']:
                fmt = f"{train_val:>14.2f}% {test_val:>14.2f}% {diff:>+14.2f}%"
            else:
                fmt = f"{train_val:>15.2f} {test_val:>15.2f} {diff:>+15.2f}"
            
            print(f"{metric:<20} {fmt}")
        
        print("-" * 70)
        
        # 경고 출력
        if comparison.get('warnings'):
            print(f"\n⚠️ 경고:")
            for warning in comparison['warnings']:
                print(f"  {warning}")
        
        # 상태 출력
        print(f"\n📋 판정: {comparison.get('status', '알 수 없음')}")
        print("=" * 70)
    
    return comparison


def validate_split_quality(
    price_data: pd.DataFrame,
    train_period: SplitPeriod,
    test_period: SplitPeriod,
    market_index: str = '069500'  # KODEX 200
) -> Dict:
    """
    분할 품질 검증 (레짐 균형 등)
    
    Args:
        price_data: 가격 데이터
        train_period: Train 기간
        test_period: Test 기간
        market_index: 시장 지수 종목 코드
        
    Returns:
        검증 결과
    """
    validation = {
        'train': {},
        'test': {},
        'warnings': []
    }
    
    try:
        # 시장 지수 데이터 추출
        if market_index in price_data.index.get_level_values('code'):
            market_data = price_data.xs(market_index, level='code')
            
            # Train 기간 분석
            train_data = market_data[
                (market_data.index >= pd.Timestamp(train_period.start_date)) &
                (market_data.index <= pd.Timestamp(train_period.end_date))
            ]
            
            if len(train_data) > 0:
                train_return = (train_data['close'].iloc[-1] / train_data['close'].iloc[0] - 1) * 100
                train_volatility = train_data['close'].pct_change().std() * np.sqrt(252) * 100
                validation['train'] = {
                    'return': train_return,
                    'volatility': train_volatility,
                    'days': len(train_data)
                }
            
            # Test 기간 분석
            test_data = market_data[
                (market_data.index >= pd.Timestamp(test_period.start_date)) &
                (market_data.index <= pd.Timestamp(test_period.end_date))
            ]
            
            if len(test_data) > 0:
                test_return = (test_data['close'].iloc[-1] / test_data['close'].iloc[0] - 1) * 100
                test_volatility = test_data['close'].pct_change().std() * np.sqrt(252) * 100
                validation['test'] = {
                    'return': test_return,
                    'volatility': test_volatility,
                    'days': len(test_data)
                }
            
            # 경고 체크
            train_ret = validation['train'].get('return', 0)
            test_ret = validation['test'].get('return', 0)
            
            # 극단적인 시장 상황 경고
            if train_ret > 50:
                validation['warnings'].append(
                    f"⚠️ Train 기간 강세장: 시장 수익률 {train_ret:.1f}%"
                )
            elif train_ret < -30:
                validation['warnings'].append(
                    f"⚠️ Train 기간 약세장: 시장 수익률 {train_ret:.1f}%"
                )
            
            if test_ret > 50:
                validation['warnings'].append(
                    f"⚠️ Test 기간 강세장: 시장 수익률 {test_ret:.1f}%"
                )
            elif test_ret < -30:
                validation['warnings'].append(
                    f"⚠️ Test 기간 약세장: 시장 수익률 {test_ret:.1f}%"
                )
            
            logger.info(f"분할 품질 검증:")
            logger.info(f"  Train 시장 수익률: {train_ret:.2f}%")
            logger.info(f"  Test 시장 수익률: {test_ret:.2f}%")
            
    except Exception as e:
        logger.warning(f"분할 품질 검증 실패: {e}")
        validation['error'] = str(e)
    
    return validation


# 편의 함수
def quick_split_backtest(
    adapter: Any,
    price_data: pd.DataFrame,
    strategy: Any,
    start_date: date,
    end_date: date,
    train_ratio: float = 0.7,
    verbose: bool = True,
    **kwargs
) -> Dict:
    """
    빠른 Train/Test 분리 백테스트 (원스톱)
    
    Args:
        adapter: 백테스트 어댑터
        price_data: 가격 데이터
        strategy: 전략 객체
        start_date: 시작일
        end_date: 종료일
        train_ratio: Train 비율
        verbose: 상세 출력
        **kwargs: 추가 인자
        
    Returns:
        전체 결과
    """
    # 백테스트 실행
    results = run_backtest_with_split(
        adapter=adapter,
        price_data=price_data,
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
        train_ratio=train_ratio,
        **kwargs
    )
    
    # 결과 비교 출력
    if verbose:
        compare_train_test_results(results, verbose=True)
    
    return results


# =============================================================================
# Phase 3: Train/Val/Test 3-way 분할
# =============================================================================

@dataclass
class ThreeWaySplitResult:
    """3-way 분할 결과"""
    train: SplitPeriod
    val: SplitPeriod
    test: SplitPeriod
    
    def __str__(self) -> str:
        return f"Train: {self.train}\nVal: {self.val}\nTest: {self.test}"


def train_val_test_split(
    start_date: date,
    end_date: date,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    min_train_days: int = 504,  # 최소 2년
    min_val_days: int = 126,    # 최소 6개월
    min_test_days: int = 126    # 최소 6개월
) -> Tuple[Tuple[date, date], Tuple[date, date], Tuple[date, date]]:
    """
    Train/Val/Test 3-way 분리 (시간순)
    
    Args:
        start_date: 전체 시작일
        end_date: 전체 종료일
        train_ratio: Train 비율 (기본 70%)
        val_ratio: Validation 비율 (기본 15%)
        test_ratio: Test 비율 (기본 15%)
        min_train_days: 최소 Train 기간 (일)
        min_val_days: 최소 Val 기간 (일)
        min_test_days: 최소 Test 기간 (일)
        
    Returns:
        ((train_start, train_end), (val_start, val_end), (test_start, test_end))
    """
    # 비율 검증
    total_ratio = train_ratio + val_ratio + test_ratio
    if abs(total_ratio - 1.0) > 0.01:
        logger.warning(f"비율 합이 1.0이 아님: {total_ratio:.2f}, 정규화 적용")
        train_ratio /= total_ratio
        val_ratio /= total_ratio
        test_ratio /= total_ratio
    
    total_days = (end_date - start_date).days
    
    # 최소 기간 검증
    min_total_days = min_train_days + min_val_days + min_test_days
    if total_days < min_total_days:
        logger.warning(
            f"데이터 기간 부족: {total_days}일 < {min_total_days}일 (최소)\n"
            f"권장: Train {min_train_days}일 + Val {min_val_days}일 + Test {min_test_days}일"
        )
    
    # 기간 계산
    train_days = int(total_days * train_ratio)
    val_days = int(total_days * val_ratio)
    test_days = total_days - train_days - val_days
    
    # 날짜 계산
    train_end = start_date + timedelta(days=train_days)
    val_start = train_end + timedelta(days=1)
    val_end = val_start + timedelta(days=val_days - 1)
    test_start = val_end + timedelta(days=1)
    
    logger.info(f"Train/Val/Test 분리 완료:")
    logger.info(f"  Train: {start_date} ~ {train_end} ({train_days}일, {train_ratio*100:.0f}%)")
    logger.info(f"  Val:   {val_start} ~ {val_end} ({val_days}일, {val_ratio*100:.0f}%)")
    logger.info(f"  Test:  {test_start} ~ {end_date} ({test_days}일, {test_ratio*100:.0f}%)")
    
    return (start_date, train_end), (val_start, val_end), (test_start, end_date)


def get_three_way_split_periods(
    start_date: date,
    end_date: date,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15
) -> ThreeWaySplitResult:
    """
    3-way 분할 기간 정보 반환
    """
    (train_start, train_end), (val_start, val_end), (test_start, test_end) = train_val_test_split(
        start_date, end_date, train_ratio, val_ratio, test_ratio
    )
    
    return ThreeWaySplitResult(
        train=SplitPeriod("Train", train_start, train_end),
        val=SplitPeriod("Val", val_start, val_end),
        test=SplitPeriod("Test", test_start, test_end)
    )


def run_backtest_with_three_way_split(
    adapter: Any,
    price_data: pd.DataFrame,
    strategy: Any,
    start_date: date,
    end_date: date,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    **kwargs
) -> Dict[str, Dict]:
    """
    Train/Val/Test 3-way 분리 백테스트 실행
    
    Args:
        adapter: 백테스트 어댑터 (KRXMAPSAdapter 등)
        price_data: 가격 데이터
        strategy: 전략 객체
        start_date: 전체 시작일
        end_date: 전체 종료일
        train_ratio: Train 비율
        val_ratio: Val 비율
        test_ratio: Test 비율
        **kwargs: 어댑터에 전달할 추가 인자
        
    Returns:
        {
            'train': {...},
            'val': {...},
            'test': {...},
            'periods': ThreeWaySplitResult,
            'comparison': {...}
        }
    """
    # 기간 분리
    (train_start, train_end), (val_start, val_end), (test_start, test_end) = train_val_test_split(
        start_date, end_date, train_ratio, val_ratio, test_ratio
    )
    
    periods = ThreeWaySplitResult(
        train=SplitPeriod("Train", train_start, train_end),
        val=SplitPeriod("Val", val_start, val_end),
        test=SplitPeriod("Test", test_start, test_end)
    )
    
    logger.info("=" * 60)
    logger.info("Train/Val/Test 3-way 분리 백테스트 시작")
    logger.info("=" * 60)
    
    # Train 백테스트
    logger.info(f"\n[Train] {train_start} ~ {train_end}")
    logger.info("-" * 40)
    
    train_results = adapter.run(
        price_data=price_data,
        strategy=strategy,
        start_date=train_start,
        end_date=train_end,
        **kwargs
    )
    
    logger.info(f"[Train] 완료: CAGR {train_results.get('cagr', 0):.2f}%, "
                f"Sharpe {train_results.get('sharpe_ratio', 0):.2f}, "
                f"MDD {train_results.get('max_drawdown', 0):.2f}%")
    
    # 어댑터 리셋
    adapter.reset()
    
    # Validation 백테스트
    logger.info(f"\n[Val] {val_start} ~ {val_end}")
    logger.info("-" * 40)
    
    val_results = adapter.run(
        price_data=price_data,
        strategy=strategy,
        start_date=val_start,
        end_date=val_end,
        **kwargs
    )
    
    logger.info(f"[Val] 완료: CAGR {val_results.get('cagr', 0):.2f}%, "
                f"Sharpe {val_results.get('sharpe_ratio', 0):.2f}, "
                f"MDD {val_results.get('max_drawdown', 0):.2f}%")
    
    # 어댑터 리셋
    adapter.reset()
    
    # Test 백테스트
    logger.info(f"\n[Test] {test_start} ~ {test_end}")
    logger.info("-" * 40)
    
    test_results = adapter.run(
        price_data=price_data,
        strategy=strategy,
        start_date=test_start,
        end_date=test_end,
        **kwargs
    )
    
    logger.info(f"[Test] 완료: CAGR {test_results.get('cagr', 0):.2f}%, "
                f"Sharpe {test_results.get('sharpe_ratio', 0):.2f}, "
                f"MDD {test_results.get('max_drawdown', 0):.2f}%")
    
    # 비교 결과 생성
    comparison = _compare_three_way_results(train_results, val_results, test_results)
    
    return {
        'train': train_results,
        'val': val_results,
        'test': test_results,
        'periods': periods,
        'comparison': comparison
    }


def _compare_three_way_results(train: Dict, val: Dict, test: Dict) -> Dict:
    """
    Train/Val/Test 결과 비교
    """
    metrics = ['cagr', 'sharpe_ratio', 'max_drawdown', 'total_return_pct']
    
    comparison = {
        'metrics': {},
        'warnings': [],
        'is_overfit': False,
        'degradation_pattern': None  # Train > Val > Test 패턴 확인
    }
    
    for metric in metrics:
        train_val = train.get(metric, 0)
        val_val = val.get(metric, 0)
        test_val = test.get(metric, 0)
        
        comparison['metrics'][metric] = {
            'train': train_val,
            'val': val_val,
            'test': test_val,
            'train_to_val': val_val - train_val,
            'val_to_test': test_val - val_val,
            'train_to_test': test_val - train_val
        }
    
    # 과적합 패턴 분석
    cagr_train = train.get('cagr', 0)
    cagr_val = val.get('cagr', 0)
    cagr_test = test.get('cagr', 0)
    
    sharpe_train = train.get('sharpe_ratio', 0)
    sharpe_val = val.get('sharpe_ratio', 0)
    sharpe_test = test.get('sharpe_ratio', 0)
    
    # 정상 패턴: Train >= Val >= Test (약간의 성능 저하는 정상)
    if cagr_train >= cagr_val >= cagr_test:
        comparison['degradation_pattern'] = 'normal'
        comparison['status'] = '[O] 정상 (Train >= Val >= Test)'
    # 과적합 패턴: Train >> Val 또는 Val >> Test
    elif cagr_train > 0 and cagr_val / cagr_train < 0.5:
        comparison['degradation_pattern'] = 'overfit_train'
        comparison['is_overfit'] = True
        comparison['warnings'].append(
            f"[!] Train->Val 급락: CAGR {cagr_train:.2f}% -> {cagr_val:.2f}%"
        )
        comparison['status'] = '[X] 과적합 (Train에서 과최적화)'
    elif cagr_val > 0 and cagr_test / cagr_val < 0.5:
        comparison['degradation_pattern'] = 'overfit_val'
        comparison['is_overfit'] = True
        comparison['warnings'].append(
            f"[!] Val->Test 급락: CAGR {cagr_val:.2f}% -> {cagr_test:.2f}%"
        )
        comparison['status'] = '[X] 과적합 (Val에서 과최적화)'
    # 역전 패턴: Test > Val 또는 Val > Train (시장 환경 변화)
    elif cagr_test > cagr_val > cagr_train:
        comparison['degradation_pattern'] = 'improving'
        comparison['status'] = '[+] 개선 (시장 환경 호전)'
    else:
        comparison['degradation_pattern'] = 'mixed'
        comparison['status'] = '[?] 혼합 패턴 (추가 분석 필요)'
    
    # Val과 Test 차이가 작으면 신뢰도 높음
    if cagr_val != 0:
        val_test_diff_pct = abs(cagr_test - cagr_val) / abs(cagr_val) * 100
        if val_test_diff_pct < 20:
            comparison['validation_reliability'] = 'high'
        elif val_test_diff_pct < 50:
            comparison['validation_reliability'] = 'medium'
        else:
            comparison['validation_reliability'] = 'low'
            comparison['warnings'].append(
                f"[!] Val/Test 차이 큼: {val_test_diff_pct:.1f}%"
            )
    else:
        comparison['validation_reliability'] = 'unknown'
    
    return comparison


def compare_three_way_results(results: Dict, verbose: bool = True) -> Dict:
    """
    Train/Val/Test 결과 비교 출력
    """
    comparison = results.get('comparison', {})
    periods = results.get('periods')
    
    if verbose:
        print("\n" + "=" * 70)
        print("[결과] Train/Val/Test 비교 결과")
        print("=" * 70)
        
        if periods:
            print(f"\n[기간]")
            print(f"  {periods.train}")
            print(f"  {periods.val}")
            print(f"  {periods.test}")
        
        print(f"\n[성과 비교]")
        print("-" * 70)
        print(f"{'지표':<20} {'Train':>12} {'Val':>12} {'Test':>12} {'T->V':>10} {'V->T':>10}")
        print("-" * 70)
        
        metrics_display = {
            'cagr': ('CAGR', '%'),
            'sharpe_ratio': ('Sharpe', ''),
            'max_drawdown': ('MDD', '%'),
            'total_return_pct': ('Total Return', '%')
        }
        
        for metric, (name, unit) in metrics_display.items():
            if metric in comparison.get('metrics', {}):
                m = comparison['metrics'][metric]
                train_val = m['train']
                val_val = m['val']
                test_val = m['test']
                t_to_v = m['train_to_val']
                v_to_t = m['val_to_test']
                
                if unit == '%':
                    print(f"{name:<20} {train_val:>10.2f}% {val_val:>10.2f}% {test_val:>10.2f}% {t_to_v:>+9.2f}% {v_to_t:>+9.2f}%")
                else:
                    print(f"{name:<20} {train_val:>12.2f} {val_val:>12.2f} {test_val:>12.2f} {t_to_v:>+10.2f} {v_to_t:>+10.2f}")
        
        print("-" * 70)
        
        print(f"\n[판정] {comparison.get('status', '알 수 없음')}")
        print(f"   검증 신뢰도: {comparison.get('validation_reliability', 'unknown')}")
        
        if comparison.get('warnings'):
            print("\n[경고]")
            for warning in comparison['warnings']:
                print(f"   {warning}")
        
        print("=" * 70)
    
    return comparison
