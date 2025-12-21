# -*- coding: utf-8 -*-
"""
extensions/tuning/walkforward.py
튜닝/검증 체계 v2.1 - 미니 Walk-Forward 분석

문서 참조: docs/tuning/03_walkforward_manifest.md 8절
"""
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Any, Tuple

from dateutil.relativedelta import relativedelta

from extensions.tuning.types import (
    BacktestMetrics,
    CostConfig,
    DataConfig,
    DEFAULT_COSTS,
)
from extensions.tuning.split import snap_start, snap_end

logger = logging.getLogger(__name__)


@dataclass
class WFWindow:
    """Walk-Forward 윈도우"""
    window_number: int
    train: Tuple[date, date]      # (start, end)
    val: Tuple[date, date]
    outsample: Tuple[date, date]  # ✅ v2.1: WF에서는 outsample 용어 사용


@dataclass
class WFResult:
    """Walk-Forward 결과"""
    window: WFWindow
    train_metrics: Optional[BacktestMetrics] = None
    val_metrics: Optional[BacktestMetrics] = None
    outsample_metrics: Optional[BacktestMetrics] = None
    best_params: Dict[str, Any] = field(default_factory=dict)


def generate_windows(
    start_date: date,
    end_date: date,
    train_months: int,
    val_months: int,
    outsample_months: int,
    stride_months: int,
    trading_calendar: List[date]
) -> List[WFWindow]:
    """
    Walk-Forward 윈도우 생성
    
    문서 참조: docs/tuning/03_walkforward_manifest.md 8.1절
    
    ⚠️ 절대 규칙:
    - 모든 윈도우는 전체 기간(start_date ~ end_date) 내에서만 생성
    - end_date를 초과하는 윈도우는 생성하지 않음
    - start 경계: 휴장일이면 다음 영업일로 스냅(snap_start)
    - end 경계: 휴장일이면 이전 영업일로 스냅(snap_end)
    
    Args:
        start_date: 전체 시작일
        end_date: 전체 종료일
        train_months: 학습 기간 (개월)
        val_months: 검증 기간 (개월)
        outsample_months: Out-of-Sample 기간 (개월)
        stride_months: 윈도우 이동 간격 (개월)
        trading_calendar: 거래일 리스트
        
    Returns:
        WFWindow 리스트
    """
    windows = []
    window_number = 1
    
    current_start = start_date
    
    while True:
        # 기간 계산
        train_end = current_start + relativedelta(months=train_months)
        val_start = train_end
        val_end = val_start + relativedelta(months=val_months)
        outsample_start = val_end
        outsample_end = outsample_start + relativedelta(months=outsample_months)
        
        # end_date 초과 시 중단
        if outsample_end > end_date:
            break
        
        # v2.1: 시작일은 snap_start, 종료일은 snap_end
        try:
            window = WFWindow(
                window_number=window_number,
                train=(
                    snap_start(current_start, trading_calendar),
                    snap_end(train_end - timedelta(days=1), trading_calendar)
                ),
                val=(
                    snap_start(val_start, trading_calendar),
                    snap_end(val_end - timedelta(days=1), trading_calendar)
                ),
                outsample=(
                    snap_start(outsample_start, trading_calendar),
                    snap_end(outsample_end - timedelta(days=1), trading_calendar)
                ),
            )
            windows.append(window)
            window_number += 1
        except ValueError as e:
            logger.warning(f"윈도우 {window_number} 생성 실패: {e}")
        
        # 다음 윈도우로 이동
        current_start += relativedelta(months=stride_months)
    
    logger.info(f"Walk-Forward 윈도우 {len(windows)}개 생성")
    return windows


def calculate_stability_score(sharpe_list: List[float]) -> float:
    """
    안정성 점수 계산
    
    문서 참조: docs/tuning/03_walkforward_manifest.md 8.3절
    
    공식: mean / (std + epsilon)
    높을수록 안정적
    
    Args:
        sharpe_list: Sharpe 리스트
        
    Returns:
        안정성 점수
    """
    import numpy as np
    
    if not sharpe_list:
        return 0.0
    
    mean = np.mean(sharpe_list)
    std = np.std(sharpe_list)
    epsilon = 0.1
    
    return mean / (std + epsilon)


def calculate_win_rate(sharpe_list: List[float]) -> float:
    """
    승률 계산
    
    문서 참조: docs/tuning/03_walkforward_manifest.md 8.3절
    
    공식: Sharpe > 0인 윈도우 비율
    
    Args:
        sharpe_list: Sharpe 리스트
        
    Returns:
        승률 (0~1)
    """
    if not sharpe_list:
        return 0.0
    
    wins = sum(1 for s in sharpe_list if s > 0)
    return wins / len(sharpe_list)


class MiniWalkForward:
    """
    미니 Walk-Forward 분석기
    
    문서 참조: docs/tuning/03_walkforward_manifest.md 8절
    
    Gate 2 안정성 평가용 (3~5개 윈도우)
    """
    
    def __init__(
        self,
        start_date: date,
        end_date: date,
        trading_calendar: List[date],
        train_months: int = 12,
        val_months: int = 3,
        outsample_months: int = 3,
        stride_months: int = 3,
        costs: Optional[CostConfig] = None,
        data_config: Optional[DataConfig] = None,
        universe_codes: Optional[List[str]] = None,
    ):
        """
        Args:
            start_date: 전체 시작일
            end_date: 전체 종료일
            trading_calendar: 거래일 리스트
            train_months: 학습 기간 (기본 12개월)
            val_months: 검증 기간 (기본 3개월)
            outsample_months: Out-of-Sample 기간 (기본 3개월)
            stride_months: 윈도우 이동 간격 (기본 3개월)
            costs: 비용 설정
            data_config: 데이터 설정
            universe_codes: 유니버스 종목 코드 리스트
        """
        self.start_date = start_date
        self.end_date = end_date
        self.trading_calendar = trading_calendar
        self.train_months = train_months
        self.val_months = val_months
        self.outsample_months = outsample_months
        self.stride_months = stride_months
        self.costs = costs or DEFAULT_COSTS
        self.data_config = data_config
        self.universe_codes = universe_codes
        
        # 윈도우 생성
        self.windows = generate_windows(
            start_date=start_date,
            end_date=end_date,
            train_months=train_months,
            val_months=val_months,
            outsample_months=outsample_months,
            stride_months=stride_months,
            trading_calendar=trading_calendar
        )
        
        self.results: List[WFResult] = []
    
    def run(self, params: Dict[str, Any]) -> List[WFResult]:
        """
        Walk-Forward 분석 실행
        
        Args:
            params: 고정 파라미터 (튜닝된 파라미터)
            
        Returns:
            WFResult 리스트
        """
        from extensions.tuning.runner import _run_single_backtest
        
        self.results = []
        
        for window in self.windows:
            logger.info(f"[윈도우 {window.window_number}] 실행 중...")
            logger.debug(f"  Train: {window.train[0]} ~ {window.train[1]}")
            logger.debug(f"  Val: {window.val[0]} ~ {window.val[1]}")
            logger.debug(f"  Outsample: {window.outsample[0]} ~ {window.outsample[1]}")
            
            # Train 백테스트
            train_metrics = _run_single_backtest(
                params=params,
                start_date=window.train[0],
                end_date=window.train[1],
                costs=self.costs,
                trading_calendar=self.trading_calendar,
                universe_codes=self.universe_codes,
            )
            
            # Val 백테스트
            val_metrics = _run_single_backtest(
                params=params,
                start_date=window.val[0],
                end_date=window.val[1],
                costs=self.costs,
                trading_calendar=self.trading_calendar,
                universe_codes=self.universe_codes,
            )
            
            # Outsample 백테스트
            outsample_metrics = _run_single_backtest(
                params=params,
                start_date=window.outsample[0],
                end_date=window.outsample[1],
                costs=self.costs,
                trading_calendar=self.trading_calendar,
                universe_codes=self.universe_codes,
            )
            
            result = WFResult(
                window=window,
                train_metrics=train_metrics,
                val_metrics=val_metrics,
                outsample_metrics=outsample_metrics,
                best_params=params
            )
            
            self.results.append(result)
            
            logger.info(
                f"  결과: Train Sharpe={train_metrics.sharpe:.2f}, "
                f"Val Sharpe={val_metrics.sharpe:.2f}, "
                f"Outsample Sharpe={outsample_metrics.sharpe:.2f}"
            )
        
        return self.results
    
    def get_outsample_sharpes(self) -> List[float]:
        """Outsample Sharpe 리스트 반환"""
        return [r.outsample_metrics.sharpe for r in self.results if r.outsample_metrics]
    
    def get_stability_score(self) -> float:
        """안정성 점수 반환"""
        return calculate_stability_score(self.get_outsample_sharpes())
    
    def get_win_rate(self) -> float:
        """승률 반환"""
        return calculate_win_rate(self.get_outsample_sharpes())
    
    def get_summary(self) -> Dict[str, Any]:
        """요약 통계 반환"""
        import numpy as np
        
        sharpes = self.get_outsample_sharpes()
        
        return {
            'n_windows': len(self.windows),
            'n_results': len(self.results),
            'stability_score': self.get_stability_score(),
            'win_rate': self.get_win_rate(),
            'mean_sharpe': float(np.mean(sharpes)) if sharpes else 0.0,
            'std_sharpe': float(np.std(sharpes)) if sharpes else 0.0,
            'min_sharpe': float(np.min(sharpes)) if sharpes else 0.0,
            'max_sharpe': float(np.max(sharpes)) if sharpes else 0.0,
        }
    
    def to_gate2_format(self) -> List[Dict[str, float]]:
        """Gate 2 입력 형식으로 변환"""
        return [
            {'sharpe': r.outsample_metrics.sharpe}
            for r in self.results
            if r.outsample_metrics
        ]
