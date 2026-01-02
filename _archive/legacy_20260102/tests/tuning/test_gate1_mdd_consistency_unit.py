# -*- coding: utf-8 -*-
"""
tests/tuning/test_gate1_mdd_consistency_unit.py
Gate 1 MDD 일관성 유닛 테스트

실행: python -m pytest tests/tuning/test_gate1_mdd_consistency_unit.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from extensions.tuning.types import BacktestMetrics, BacktestRunResult, GuardrailChecks
from extensions.tuning.guardrails import check_mdd_consistency


def make_result(train_mdd: float, val_mdd: float) -> BacktestRunResult:
    """테스트용 BacktestRunResult 생성"""
    return BacktestRunResult(
        metrics={
            'train': BacktestMetrics(sharpe=1.5, cagr=0.2, mdd=train_mdd),
            'val': BacktestMetrics(sharpe=1.2, cagr=0.15, mdd=val_mdd),
            'test': None
        },
        guardrail_checks=GuardrailChecks(num_trades=50, exposure_ratio=0.5, annual_turnover=10)
    )


def test_mdd_consistency_pass():
    """
    MDD 일관성 통과 케이스
    
    Val MDD <= max(Train MDD * 1.2, 10%) 이면 통과
    """
    # Train MDD = -10%, threshold = max(10% * 1.2, 10%) = 12%
    # Val MDD = -11% <= 12% → 통과
    result = make_result(train_mdd=-0.10, val_mdd=-0.11)
    assert check_mdd_consistency(result) is True, "Val MDD(11%) <= threshold(12%)"


def test_mdd_consistency_fail():
    """
    MDD 일관성 실패 케이스
    
    Val MDD > max(Train MDD * 1.2, 10%) 면 실패
    """
    # Train MDD = -10%, threshold = max(10% * 1.2, 10%) = 12%
    # Val MDD = -20% > 12% → 실패
    result = make_result(train_mdd=-0.10, val_mdd=-0.20)
    assert check_mdd_consistency(result) is False, "Val MDD(20%) > threshold(12%)"


def test_mdd_consistency_edge_case():
    """
    MDD 일관성 경계 케이스
    
    Val MDD가 정확히 threshold면 통과
    """
    # Train MDD = -10%, threshold = max(10% * 1.2, 10%) = 12%
    # Val MDD = -12% == 12% → 통과
    result = make_result(train_mdd=-0.10, val_mdd=-0.12)
    assert check_mdd_consistency(result) is True, "Val MDD(12%) == threshold(12%)"


def test_mdd_consistency_min_tolerance():
    """
    최소 허용치 케이스
    
    Train MDD가 작아도 최소 10%까지는 허용
    """
    # Train MDD = -5%, threshold = max(5% * 1.2, 10%) = 10%
    # Val MDD = -8% <= 10% → 통과
    result = make_result(train_mdd=-0.05, val_mdd=-0.08)
    assert check_mdd_consistency(result) is True, "Val MDD(8%) <= min_tolerance(10%)"


def test_mdd_consistency_both_zero():
    """
    Train/Val MDD 모두 0인 케이스
    """
    result = make_result(train_mdd=0.0, val_mdd=0.0)
    assert check_mdd_consistency(result) is True, "둘 다 0이면 통과"


if __name__ == "__main__":
    print("MDD 일관성 유닛 테스트")
    print("=" * 40)
    
    tests = [
        ("PASS 케이스", test_mdd_consistency_pass),
        ("FAIL 케이스", test_mdd_consistency_fail),
        ("경계 케이스", test_mdd_consistency_edge_case),
        ("최소 허용치 케이스", test_mdd_consistency_min_tolerance),
        ("둘 다 0 케이스", test_mdd_consistency_both_zero),
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
