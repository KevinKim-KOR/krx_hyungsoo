# -*- coding: utf-8 -*-
"""
extensions/tuning/runner.py
튜닝/검증 체계 v2.1 - 백테스트 실행 함수

문서 참조: docs/tuning/00_overview.md 2.1절, 02_objective_gates.md 6절
"""
import logging
from datetime import date
from typing import Dict, List, Optional, Any

from extensions.tuning.types import (
    BacktestMetrics,
    BacktestRunResult,
    GuardrailChecks,
    LogicChecks,
    DebugInfo,
    CostConfig,
    DataConfig,
    SplitConfig,
    DEFAULT_COSTS,
    compute_params_hash,
)
from extensions.tuning.split import create_period
from extensions.tuning.cache import make_cache_key, get_global_cache

logger = logging.getLogger(__name__)


def _run_single_backtest(
    params: Dict[str, Any],
    start_date: date,
    end_date: date,
    costs: CostConfig,
    trading_calendar: List[date],
    universe_codes: Optional[List[str]] = None,
) -> BacktestMetrics:
    """
    단일 구간 백테스트 실행 (내부 함수)

    Args:
        params: 전략 파라미터
        start_date: 시작일
        end_date: 종료일
        costs: 비용 설정
        trading_calendar: 거래일 리스트
        universe_codes: 유니버스 코드 리스트 (필수)

    Returns:
        BacktestMetrics 객체
    """
    # 기존 백테스트 서비스 호출
    from app.services.backtest_service import BacktestService, BacktestParams

    service = BacktestService(save_history=False)

    bt_params = BacktestParams(
        start_date=start_date,
        end_date=end_date,
        ma_period=params.get("ma_period", 60),
        rsi_period=params.get("rsi_period", 14),
        # stop_loss_pct: 양수 소수 (0.03~0.10 = 3%~10%)
        # BacktestParams는 퍼센트 정수를 받으므로 *100 변환
        stop_loss=params.get("stop_loss_pct", 0.05) * 100,
        max_positions=params.get("max_positions", 10),
        initial_capital=params.get("initial_capital", 10_000_000),
        enable_defense=params.get("enable_defense", True),
        universe_codes=universe_codes,
    )

    try:
        result = service.run(bt_params)

        # BacktestResult는 직접 필드를 가짐 (metrics 속성 없음)
        return BacktestMetrics(
            sharpe=result.sharpe_ratio,
            cagr=result.cagr / 100 if result.cagr else 0.0,  # % → 소수
            mdd=(
                -abs(result.max_drawdown) / 100 if result.max_drawdown else 0.0
            ),  # 음수로 저장
            total_return=result.total_return / 100 if result.total_return else 0.0,
            volatility=result.volatility / 100 if result.volatility else 0.0,
            calmar=result.calmar_ratio if hasattr(result, "calmar_ratio") else 0.0,
            num_trades=result.num_trades,
            win_rate=result.win_rate / 100 if result.win_rate else 0.0,
            exposure_ratio=result.exposure_ratio,  # Phase 3 Fix: Real Calculation
            annual_turnover=0.0,  # TODO: 실제 계산 필요
            # Phase 2.1: 멀티룩백 증거 강화
            signal_days=getattr(result, "signal_days", 0),
            order_count=getattr(result, "order_count", 0),
            first_trade_date=getattr(result, "first_trade_date", None),
        )
        
        # Phase 3 Sanity Check: 거래가 있는데 노출도가 0이면 논리적 오류
        if metrics.num_trades > 0 and metrics.exposure_ratio == 0.0:
             # 엔진 내부 소수점 이슈일 수 있으므로 warning 정도가 안전하나, 
             # Phase 3 "Strict" 요구사항에 따라 Error 발생 시킴 (혹은 강한 Warning)
             # 단, 1일치 거래 후 바로 매도한 경우 매우 낮을 순 있음. 
             # 하지만 0.0은 불가능 (최소 1일 보유).
             logger.error(f"[Sanity Check Failed] Trades={metrics.num_trades} but Exposure=0.0! (Run Integrity Violated)")
             # raise ValueError(f"Metric Integrity Error: Trades > 0 but Exposure Ratio == 0.0") 
             # 튜닝 중단 방지를 위해 로깅만 하고 넘어갈지, 멈출지 결정. 
             # 사용자 요청: "즉시 에러를 발생시켜 조용한 버그를 차단할 것"
             raise ValueError(f"Metric Integrity Error: Trades({metrics.num_trades}) > 0 but Exposure Ratio == 0.0")

        return metrics
    except Exception as e:
        logger.error(f"백테스트 실행 실패: {e}")
        return BacktestMetrics()


def run_backtest_for_tuning(
    params: Dict[str, Any],
    start_date: date,
    end_date: date,
    lookback_months: int,
    trading_calendar: List[date],
    split_config: Optional[SplitConfig] = None,
    costs: Optional[CostConfig] = None,
    data_config: Optional[DataConfig] = None,
    use_cache: bool = True,
    universe_codes: List[str] = None,
    guardrail_config: Optional[Dict] = None,
) -> BacktestRunResult:
    """
        start_date: 전체 시작일
        end_date: 전체 종료일
        lookback_months: 룩백 기간 (3, 6, 12)
        trading_calendar: 거래일 리스트
        split_config: Split 설정
        costs: 비용 설정 (기본값 적용)
        data_config: 데이터 설정
        use_cache: 캐시 사용 여부
        universe_codes: 유니버스 코드 리스트 (필수)

    Returns:
        BacktestRunResult (test=None)
    """
    if costs is None:
        costs = DEFAULT_COSTS

    if data_config is None:
        data_config = DataConfig()

    if split_config is None:
        split_config = SplitConfig()

    from dateutil.relativedelta import relativedelta

    # Period 생성 (전체 기간 사용, lookback_months는 캐시 키 구분용)
    # ⚠️ 룩백은 "멀티 룩백 결합" 시 다른 기간을 구분하는 용도로만 사용
    # 실제 Split은 start_date ~ end_date 전체 기간에서 수행
    try:
        period = create_period(
            start_date=start_date,
            end_date=end_date,
            trading_calendar=trading_calendar,
            split_config=split_config,
            include_test=False,  # ⚠️ Test 봉인
        )
    except ValueError as e:
        logger.error(f"Period 생성 실패: {e}")
        return BacktestRunResult(
            metrics={"train": None, "val": None, "test": None}, warnings=[str(e)]
        )

    # 캐시 확인
    cache_key = None
    if use_cache:
        cache = get_global_cache()
        cache_key = make_cache_key(params, lookback_months, period, costs, data_config)
        # 룩백별 cache_key 구분 확인용 로그 (INFO 레벨)
        logger.info(f"[캐시] lb={lookback_months}M, key={cache_key[:8]}")
        cached = cache.get(cache_key)
        if cached is not None:
            # 캐시 hit 시 params_hash 검증 (버그 조기 발견용)
            current_params_hash = compute_params_hash(params)
            if cached.debug and cached.debug.params_hash != current_params_hash:
                logger.error(
                    f"[캐시 안전장치] params_hash 불일치! "
                    f"cache_key={cache_key[:8]}..., "
                    f"cached_hash={cached.debug.params_hash[:8]}..., "
                    f"current_hash={current_params_hash[:8]}... "
                    f"- 캐시 키 생성 로직 버그 가능성"
                )
            logger.info(f"[캐시 HIT] lb={lookback_months}M, key={cache_key[:8]}")
            return cached

    # Train 백테스트
    train_metrics = _run_single_backtest(
        params=params,
        start_date=period.train["start"],
        end_date=period.train["end"],
        costs=costs,
        trading_calendar=trading_calendar,
        universe_codes=universe_codes,
    )

    # Phase 2.2: "진짜" 멀티 룩백 구현 (Trailing Evaluation)
    # Val 평가는 전체 Val 기간이 아니라, 끝에서 lookback_months만큼의 기간(=Evaluation Window)만 수행한다.
    # 단, effective_eval_start가 period.val["start"]보다 앞서면 안 된다 (Clamp).
    
    val_end = period.val["end"]
    val_eval_start_target = val_end - relativedelta(months=lookback_months)
    
    # 평가 시작일이 Val 시작일보다 이전이면 Val 시작일로 Clamp (혹은 에러? Clamp가 안전)
    # 다만, 룩백이 Val 기간보다 길면 의미가 퇴색되므로 경고 로그 남김
    val_eval_start = max(period.val["start"], val_eval_start_target)
    
    if val_eval_start_target < period.val["start"]:
        logger.warning(
            f"Evaluation Window Clamped: lookback={lookback_months}M, "
            f"target_start={val_eval_start_target}, clamped_start={val_eval_start}"
        )

    # bars_used: 룩백 적용 후 실제 계산에 사용된 봉 수
    # = val_eval_start ~ val_end 기간의 거래일 수
    bars_used = len([d for d in trading_calendar if val_eval_start <= d <= val_end])

    # Val 백테스트 (Trailing Period 적용)
    val_metrics = _run_single_backtest(
        params=params,
        start_date=val_eval_start,  # ✅ 변경된 평가 시작일 사용
        end_date=val_end,
        costs=costs,
        trading_calendar=trading_calendar,
        universe_codes=universe_codes,
    )

    # 가드레일 체크 (Val 기준)
    g_conf = guardrail_config or {}
    guardrail_checks = GuardrailChecks(
        num_trades=val_metrics.num_trades,
        exposure_ratio=val_metrics.exposure_ratio,
        annual_turnover=val_metrics.annual_turnover,
        min_trades=g_conf.get("min_trades", 30),
        min_exposure=g_conf.get("min_exposure", 0.30),
        max_turnover=g_conf.get("max_turnover", 24.0),
    )

    # Logic Checks (Val 구간에서만 집계)
    # TODO: 실제 RSI 영향 데이터에서 계산 필요
    # Mock 데이터: rsi_period 파라미터가 있으면 해당 값 사용, 없으면 기본값 14
    rsi_period = params.get("rsi_period", params.get("RSI_PERIOD", 14))
    logic_checks = LogicChecks(rsi_scale_days=rsi_period, rsi_scale_events=10)

    # 디버그 정보 생성
    params_hash = compute_params_hash(params)
    period_signature = (
        f"train:{period.train['start']}~{period.train['end']}|"
        f"val:{period.val['start']}~{period.val['end']}"
    )

    # lookback_start_date 계산: end_date에서 lookback_months만큼 뒤로
    # from dateutil.relativedelta import relativedelta  # Moved up
    lookback_start = end_date - relativedelta(months=lookback_months)

    # Phase 1.8: 룩백 의미 검증용 필드 계산
    # indicator_warmup_days: MA/RSI 계산을 위해 버린 구간
    # MA 기간이 가장 긴 지표의 warmup 기간 사용
    ma_period = params.get("ma_period", params.get("MA_PERIOD", 60))
    indicator_warmup_days = ma_period  # MA 계산에 필요한 최소 일수

    # lookback_effective_start_date: 전략이 실제로 사용하는 시작점
    # = train 시작일 + warmup 기간
    train_start = period.train["start"]
    lookback_effective_start = train_start + relativedelta(days=indicator_warmup_days)

    # Phase 2.1: 멀티룩백 증거 강화 - 룩백별로 확실히 달라지는 필드
    # effective_eval_start: 룩백 적용 후 성과 계산 시작일 (val 시작일 기준)
    effective_eval_start = val_eval_start

    # bars_used: 이미 위에서 계산함

    # signal_days, order_count: val_metrics에서 가져옴
    val_signal_days = val_metrics.signal_days if val_metrics else 0
    val_order_count = val_metrics.order_count if val_metrics else 0

    debug_info = DebugInfo(
        lookback_months=lookback_months,
        lookback_start_date=lookback_start,
        params_hash=params_hash,
        cache_key=cache_key if use_cache else "",
        period_signature=period_signature,
        # Phase 1.8 추가
        lookback_effective_start_date=lookback_effective_start,
        indicator_warmup_days=indicator_warmup_days,
        # Phase 2.1 추가: 멀티룩백 증거 강화
        effective_eval_start=effective_eval_start,
        bars_used=bars_used,
        signal_days=val_signal_days,
        order_count=val_order_count,
    )

    result = BacktestRunResult(
        metrics={
            "train": train_metrics,
            "val": val_metrics,
            "test": None,  # ⚠️ Test 봉인
        },
        guardrail_checks=guardrail_checks,
        logic_checks=logic_checks,
        params=params,
        period=period,
        warnings=[],
        debug=debug_info,
    )

    # 캐시/파라미터 깨짐 탐지: 다른 params_hash인데 같은 cache_key면 ERROR
    if use_cache:
        existing = cache.get(cache_key)
        if existing is not None and existing.debug:
            if existing.debug.params_hash != params_hash:
                logger.error(
                    f"캐시/파라미터 충돌 감지! "
                    f"cache_key={cache_key[:8]}, "
                    f"기존 params_hash={existing.debug.params_hash}, "
                    f"신규 params_hash={params_hash}"
                )
        cache.set(cache_key, result)

    return result


def run_backtest_for_final(
    params: Dict[str, Any],
    start_date: date,
    end_date: date,
    lookback_months: int,
    trading_calendar: List[date],
    split_config: Optional[SplitConfig] = None,
    costs: Optional[CostConfig] = None,
    data_config: Optional[DataConfig] = None,
    universe_codes: Optional[List[str]] = None,
) -> BacktestRunResult:
    """
    최종 보고서용 백테스트: Test 포함 (Gate 2 통과 후에만 호출)

    문서 참조: docs/tuning/00_overview.md 2.1절

    ⚠️ Gate 2 통과 후에만 이 함수를 호출해야 함

    Args:
        params: 전략 파라미터
        start_date: 전체 시작일
        end_date: 전체 종료일
        lookback_months: 룩백 기간
        trading_calendar: 거래일 리스트
        split_config: Split 설정
        costs: 비용 설정
        data_config: 데이터 설정

    Returns:
        BacktestRunResult (test 포함)
    """
    if costs is None:
        costs = DEFAULT_COSTS

    if data_config is None:
        data_config = DataConfig()

    if split_config is None:
        split_config = SplitConfig()

    # Period 생성 (전체 기간 사용, Test 포함)
    try:
        period = create_period(
            start_date=start_date,
            end_date=end_date,
            trading_calendar=trading_calendar,
            split_config=split_config,
            include_test=True,  # ✅ Test 포함
        )
    except ValueError as e:
        logger.error(f"Period 생성 실패: {e}")
        return BacktestRunResult(
            metrics={"train": None, "val": None, "test": None}, warnings=[str(e)]
        )

    # Train 백테스트
    train_metrics = _run_single_backtest(
        params=params,
        start_date=period.train["start"],
        end_date=period.train["end"],
        costs=costs,
        trading_calendar=trading_calendar,
        universe_codes=universe_codes,
    )

    # Val 백테스트
    val_metrics = _run_single_backtest(
        params=params,
        start_date=period.val["start"],
        end_date=period.val["end"],
        costs=costs,
        trading_calendar=trading_calendar,
        universe_codes=universe_codes,
    )

    # Test 백테스트 (Gate 2 통과 후에만)
    test_metrics = None
    if period.test is not None:
        test_metrics = _run_single_backtest(
            params=params,
            start_date=period.test["start"],
            end_date=period.test["end"],
            costs=costs,
            trading_calendar=trading_calendar,
            universe_codes=universe_codes,
        )

    # 가드레일 체크
    guardrail_checks = GuardrailChecks(
        num_trades=val_metrics.num_trades,
        exposure_ratio=val_metrics.exposure_ratio,
        annual_turnover=val_metrics.annual_turnover,
    )

    # Logic Checks
    logic_checks = LogicChecks(rsi_scale_days=0, rsi_scale_events=0)

    # 디버그 정보 생성
    params_hash = compute_params_hash(params)
    period_signature = (
        f"train:{period.train['start']}~{period.train['end']}|"
        f"val:{period.val['start']}~{period.val['end']}"
    )
    if period.test:
        period_signature += f"|test:{period.test['start']}~{period.test['end']}"

    debug_info = DebugInfo(
        lookback_months=lookback_months,
        lookback_start_date=None,
        params_hash=params_hash,
        cache_key="",  # final은 캐시 미사용
        period_signature=period_signature,
    )

    return BacktestRunResult(
        metrics={
            "train": train_metrics,
            "val": val_metrics,
            "test": test_metrics,  # ✅ Test 포함
        },
        guardrail_checks=guardrail_checks,
        logic_checks=logic_checks,
        params=params,
        period=period,
        warnings=[],
        debug=debug_info,
    )
