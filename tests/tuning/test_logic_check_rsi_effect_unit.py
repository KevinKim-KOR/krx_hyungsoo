# -*- coding: utf-8 -*-
"""
tests/tuning/test_logic_check_rsi_effect_unit.py
Logic Check RSI 실효성 유닛 테스트

실행: python -m pytest tests/tuning/test_logic_check_rsi_effect_unit.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from extensions.tuning.types import BacktestMetrics, BacktestRunResult, LogicChecks, GuardrailChecks
from extensions.tuning.guardrails import check_logic_rsi


def make_result(rsi_scale_days: int, rsi_scale_events: int = 10) -> BacktestRunResult:
    """테스트용 BacktestRunResult 생성"""
    return BacktestRunResult(
        metrics={
            'train': BacktestMetrics(sharpe=1.5, cagr=0.2, mdd=-0.1),
            'val': BacktestMetrics(sharpe=1.2, cagr=0.15, mdd=-0.12),
            'test': None
        },
        guardrail_checks=GuardrailChecks(num_trades=50, exposure_ratio=0.5, annual_turnover=10),
        logic_checks=LogicChecks(
            rsi_scale_days=rsi_scale_days,
            rsi_scale_events=rsi_scale_events
        )
    )


def test_rsi_effect_pass():
    """
    RSI 실효성 통과 케이스
    
    rsi_scale_days >= 10이면 통과
    """
    result = make_result(rsi_scale_days=15)
    assert check_logic_rsi(result) is True, "rsi_scale_days(15) >= 10"


def test_rsi_effect_fail():
    """
    RSI 실효성 실패 케이스
    
    rsi_scale_days < 10이면 실패
    """
    result = make_result(rsi_scale_days=5)
    assert check_logic_rsi(result) is False, "rsi_scale_days(5) < 10"


def test_rsi_effect_zero():
    """
    RSI 영향 없음 케이스 (rsi_scale_days = 0)
    
    RSI가 전혀 영향을 주지 않은 경우 → 실패
    """
    result = make_result(rsi_scale_days=0)
    assert check_logic_rsi(result) is False, "rsi_scale_days(0) < 10"


def test_rsi_effect_edge_case():
    """
    RSI 실효성 경계 케이스
    
    rsi_scale_days = 10 (정확히 경계)
    """
    result = make_result(rsi_scale_days=10)
    assert check_logic_rsi(result) is True, "rsi_scale_days(10) >= 10"


def test_rsi_effect_no_logic_checks():
    """
    LogicChecks가 None인 케이스
    
    LogicChecks가 없으면 통과 (선택적 체크)
    """
    result = BacktestRunResult(
        metrics={
            'train': BacktestMetrics(sharpe=1.5, cagr=0.2, mdd=-0.1),
            'val': BacktestMetrics(sharpe=1.2, cagr=0.15, mdd=-0.12),
            'test': None
        },
        guardrail_checks=GuardrailChecks(num_trades=50, exposure_ratio=0.5, annual_turnover=10),
        logic_checks=None  # LogicChecks 없음
    )
    assert check_logic_rsi(result) is True, "LogicChecks가 None이면 통과 (선택적 체크)"


def test_rsi_effect_high_value():
    """
    RSI 영향 높음 케이스
    
    rsi_scale_days가 매우 높은 경우
    """
    result = make_result(rsi_scale_days=100)
    assert check_logic_rsi(result) is True, "rsi_scale_days(100) >= 10"


if __name__ == "__main__":
    print("RSI 실효성 유닛 테스트")
    print("=" * 40)
    
    tests = [
        ("PASS 케이스 (15일)", test_rsi_effect_pass),
        ("FAIL 케이스 (5일)", test_rsi_effect_fail),
        ("영향 없음 (0일)", test_rsi_effect_zero),
        ("경계 케이스 (10일)", test_rsi_effect_edge_case),
        ("LogicChecks=None", test_rsi_effect_no_logic_checks),
        ("높은 값 (100일)", test_rsi_effect_high_value),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            print(f"  ✅ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {name}: {e}")
            failed += 1
    
    print("=" * 40)
    print(f"결과: {passed}/{passed + failed} 통과")
