# -*- coding: utf-8 -*-
"""
tests/tuning/test_gate_e2e.py
Gate 파이프라인 E2E 테스트

실행: python -m tests.tuning.test_gate_e2e
"""
import logging
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
except ImportError:
    print("❌ optuna 패키지가 필요합니다: pip install optuna")
    sys.exit(1)

from extensions.tuning import (
    BacktestMetrics,
    BacktestRunResult,
    GuardrailChecks,
    LogicChecks,
    Period,
    SplitConfig,
    CostConfig,
    DataConfig,
    DEFAULT_COSTS,
    TuningObjective,
    LivePromotionGate,
    MiniWalkForward,
    check_gate1,
    check_gate2,
    check_gate3,
    run_backtest_for_tuning,
    run_backtest_for_final,
    clear_global_cache,
    create_manifest,
    save_manifest,
)
from extensions.tuning.gates import set_test_mode

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def generate_mock_trading_calendar(start: date, end: date) -> list:
    """테스트용 거래일 캘린더 생성 (주말 제외)"""
    calendar = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            calendar.append(current)
        current += timedelta(days=1)
    return calendar


class MockBacktestService:
    """테스트용 백테스트 서비스 Mock"""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.call_count = 0

    def run(self, params: dict, start_date: date, end_date: date) -> BacktestMetrics:
        """결정론적 백테스트 결과 생성"""
        self.call_count += 1

        param_hash = hash(frozenset(params.items()))
        date_hash = hash((start_date.isoformat(), end_date.isoformat()))
        combined_seed = self.seed + param_hash + date_hash

        rng = random.Random(combined_seed)

        ma_period = params.get("ma_period", 60)
        rsi_period = params.get("rsi_period", 14)

        base_sharpe = 0.8
        if 40 <= ma_period <= 80:
            base_sharpe += 0.5
        if 10 <= rsi_period <= 20:
            base_sharpe += 0.3

        sharpe = base_sharpe + rng.uniform(-0.5, 0.5)
        cagr = 0.10 + sharpe * 0.05 + rng.uniform(-0.05, 0.05)
        mdd = -0.08 - rng.uniform(0, 0.15)

        if rng.random() < 0.15:
            num_trades = rng.randint(10, 25)
            exposure_ratio = rng.uniform(0.1, 0.25)
        else:
            num_trades = rng.randint(35, 80)
            exposure_ratio = rng.uniform(0.4, 0.8)

        annual_turnover = rng.uniform(5, 20)

        return BacktestMetrics(
            sharpe=sharpe,
            cagr=cagr,
            mdd=mdd,
            total_return=cagr * 1.5,
            volatility=abs(cagr / sharpe) if sharpe != 0 else 0.1,
            num_trades=num_trades,
            win_rate=rng.uniform(0.4, 0.6),
            exposure_ratio=exposure_ratio,
            annual_turnover=annual_turnover,
        )


_mock_service = None


def get_mock_service(seed: int = 42) -> MockBacktestService:
    global _mock_service
    if _mock_service is None or _mock_service.seed != seed:
        _mock_service = MockBacktestService(seed)
    return _mock_service


def mock_run_single_backtest(
    params: dict,
    start_date: date,
    end_date: date,
    costs: CostConfig,
    trading_calendar: list,
) -> BacktestMetrics:
    """Mock 백테스트 실행"""
    service = get_mock_service()
    return service.run(params, start_date, end_date)


def run_gate_e2e_test(n_trials: int = 20, seed: int = 42, top_n: int = 3):
    """
    Gate 파이프라인 E2E 테스트

    Gate1: Val Top-N 뽑기
    Gate2: WF 돌려서 stability_score / win_rate 계산
    Gate3: Gate2 통과한 것만 run_backtest_for_final()로 Test 계산
    """
    print("\n" + "#" * 60)
    print(f"# Gate 파이프라인 E2E 테스트")
    print(f"# n_trials={n_trials}, seed={seed}, top_n={top_n}")
    print("#" * 60)

    # Mock 함수로 패치
    import extensions.tuning.runner as runner_module

    original_func = runner_module._run_single_backtest
    runner_module._run_single_backtest = mock_run_single_backtest

    global _mock_service
    _mock_service = MockBacktestService(seed)

    # TEST_MODE 활성화 (skip_logic_check/skip_mdd_check 사용 허용)
    set_test_mode(True)

    clear_global_cache()

    try:
        # 설정
        end_date = date(2024, 6, 30)
        start_date = date(2020, 1, 1)
        trading_calendar = generate_mock_trading_calendar(start_date, end_date)

        lookbacks = [3, 6, 12]
        lookback_months = 12

        param_ranges = {
            "ma_period": {"min": 20, "max": 100, "step": 10, "type": "int"},
            "rsi_period": {"min": 5, "max": 25, "step": 5, "type": "int"},
            "stop_loss": {"min": 0.03, "max": 0.10, "step": 0.01, "type": "float"},
        }

        split_config = SplitConfig()
        data_config = DataConfig(data_version="mock_v1", universe_version="mock_v1")

        # ============================================================
        # Phase 1: 튜닝 실행
        # ============================================================
        print("\n" + "=" * 60)
        print("Phase 1: 튜닝 실행")
        print("=" * 60)

        objective = TuningObjective(
            start_date=start_date,
            end_date=end_date,
            trading_calendar=trading_calendar,
            lookbacks=lookbacks,
            param_ranges=param_ranges,
        )

        sampler = optuna.samplers.TPESampler(seed=seed)
        study = optuna.create_study(direction="maximize", sampler=sampler)
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

        completed_trials = [
            t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE
        ]
        print(f"\n  완료된 Trial: {len(completed_trials)}/{n_trials}")

        # ============================================================
        # Phase 2: Gate 1 - Val Top-N 선정
        # ============================================================
        print("\n" + "=" * 60)
        print(f"Phase 2: Gate 1 - Val Top-{top_n} 선정")
        print("=" * 60)

        # Val Sharpe 기준 정렬
        trial_results = []
        for trial in completed_trials:
            params = trial.params
            result = run_backtest_for_tuning(
                params=params,
                start_date=start_date,
                end_date=end_date,
                lookback_months=lookback_months,
                trading_calendar=trading_calendar,
                use_cache=True,
            )

            trial_results.append(
                {
                    "trial_number": trial.number,
                    "params": params,
                    "result": result,
                    "val_sharpe": result.val.sharpe if result.val else 0,
                    "score": trial.value,
                }
            )

        # Val Sharpe 기준 정렬
        trial_results.sort(key=lambda x: x["val_sharpe"], reverse=True)

        print(f"\n  Val Sharpe Top-{top_n}:")
        gate1_passed = []

        for i, tr in enumerate(trial_results[:top_n]):
            result = tr["result"]
            params = tr["params"]

            # 파라미터 전체 출력 (JSON 덤프)
            import json

            params_json = json.dumps(params, sort_keys=True)

            # params_hash 출력
            from extensions.tuning.types import compute_params_hash

            params_hash = compute_params_hash(params)

            # Mock 데이터에서는 RSI/MDD 체크 건너뛰기
            gate1_result = check_gate1(
                result,
                top_n=top_n,
                all_results=[t["result"] for t in trial_results],
                skip_logic_check=True,  # Mock 데이터에서는 RSI 영향 없음
                skip_mdd_check=True,  # Mock 데이터에서는 MDD 일관성 불안정
            )

            status = (
                "✅ PASS"
                if gate1_result.passed
                else f"❌ FAIL: {gate1_result.failures}"
            )
            print(
                f"    {i+1}. Trial #{tr['trial_number']}: Val Sharpe={tr['val_sharpe']:.3f} - {status}"
            )
            print(f"       params: {params_json}")
            print(f"       params_hash: {params_hash}")

            if gate1_result.passed:
                gate1_passed.append({**tr, "gate1_result": gate1_result})

        print(f"\n  Gate 1 통과: {len(gate1_passed)}/{top_n}")

        if not gate1_passed:
            print("\n  ⚠️ Gate 1 통과 Trial 없음 - 테스트 종료")
            return False

        # ============================================================
        # Phase 3: Gate 2 - Walk-Forward 안정성
        # ============================================================
        print("\n" + "=" * 60)
        print("Phase 3: Gate 2 - Walk-Forward 안정성")
        print("=" * 60)

        gate2_passed = []

        for tr in gate1_passed:
            params = tr["params"]
            params_json = json.dumps(params, sort_keys=True)

            # stop_loss 필수 검증
            if "stop_loss" not in params:
                raise ValueError(
                    f"Trial #{tr['trial_number']}: stop_loss 파라미터 누락!"
                )

            print(f"\n  Trial #{tr['trial_number']} WF 분석 중...")
            print(f"    params: {params_json}")

            # 미니 Walk-Forward 실행
            wf = MiniWalkForward(
                start_date=start_date,
                end_date=end_date,
                trading_calendar=trading_calendar,
                train_months=12,
                val_months=3,
                outsample_months=3,
                stride_months=6,
            )

            wf_results = wf.run(params)
            summary = wf.get_summary()

            print(f"    - 윈도우 수: {summary['n_windows']}")
            print(f"    - 안정성 점수: {summary['stability_score']:.2f}")
            print(f"    - 승률: {summary['win_rate']:.0%}")
            print(f"    - 평균 Sharpe: {summary['mean_sharpe']:.3f}")

            # Gate 2 체크
            gate2_result = check_gate2(
                result=tr["result"],
                wf_results=wf.to_gate2_format(),
                min_stability_score=0.5,  # 테스트용으로 낮춤
                min_win_rate=0.4,  # 테스트용으로 낮춤
            )

            status = (
                "✅ PASS"
                if gate2_result.passed
                else f"❌ FAIL: {gate2_result.failures}"
            )
            print(f"    Gate 2: {status}")

            if gate2_result.passed:
                gate2_passed.append(
                    {**tr, "gate2_result": gate2_result, "wf_summary": summary}
                )

        print(f"\n  Gate 2 통과: {len(gate2_passed)}/{len(gate1_passed)}")

        if not gate2_passed:
            print("\n  ⚠️ Gate 2 통과 Trial 없음 - 테스트 종료")
            return False

        # ============================================================
        # Phase 4: Gate 3 - Test 공개
        # ============================================================
        print("\n" + "=" * 60)
        print("Phase 4: Gate 3 - Test 공개 (봉인 해제)")
        print("=" * 60)

        final_candidates = []

        for tr in gate2_passed:
            params = tr["params"]
            params_json = json.dumps(params, sort_keys=True)

            print(f"\n  Trial #{tr['trial_number']} Test 계산 중...")
            print(f"    params: {params_json}")

            # ⚠️ Gate 2 통과 후에만 run_backtest_for_final 호출
            final_result = run_backtest_for_final(
                params=params,
                start_date=start_date,
                end_date=end_date,
                lookback_months=lookback_months,
                trading_calendar=trading_calendar,
                split_config=split_config,
                costs=DEFAULT_COSTS,
                data_config=data_config,
            )

            # Test 결과 확인
            test = final_result.test
            val = final_result.val
            train = final_result.train

            print(
                f"    Train: Sharpe={train.sharpe:.3f}, CAGR={train.cagr:.1%}, MDD={train.mdd:.1%}"
            )
            print(
                f"    Val:   Sharpe={val.sharpe:.3f}, CAGR={val.cagr:.1%}, MDD={val.mdd:.1%}"
            )

            if test is not None:
                print(
                    f"    Test:  Sharpe={test.sharpe:.3f}, CAGR={test.cagr:.1%}, MDD={test.mdd:.1%}"
                )
                print(f"    ✅ Test 봉인 해제 성공!")

                final_candidates.append(
                    {
                        **tr,
                        "final_result": final_result,
                        "test_sharpe": test.sharpe,
                        "test_cagr": test.cagr,
                        "test_mdd": test.mdd,
                    }
                )
            else:
                print(f"    ❌ Test가 None - 오류!")

        print(f"\n  최종 후보: {len(final_candidates)}")

        # ============================================================
        # Phase 5: Manifest 저장 (stage=final)
        # ============================================================
        print("\n" + "=" * 60)
        print("Phase 5: Manifest 저장 (stage=final)")
        print("=" * 60)

        if final_candidates:
            # 최적 후보 선택 (Test Sharpe 기준)
            best = max(final_candidates, key=lambda x: x["test_sharpe"])

            print(f"\n  최적 후보: Trial #{best['trial_number']}")
            print(f"    - 파라미터: {best['params']}")
            print(f"    - Val Sharpe: {best['val_sharpe']:.3f}")
            print(f"    - Test Sharpe: {best['test_sharpe']:.3f}")

            # Manifest 생성 (stage=final)
            manifest = create_manifest(
                stage="final",  # ⚠️ Gate 3 통과 후 final
                start_date=start_date,
                end_date=end_date,
                lookbacks=lookbacks,
                trials=n_trials,
                split_config=split_config,
                costs=DEFAULT_COSTS,
                data_config=data_config,
                param_ranges=param_ranges,
                best_result=best["final_result"],
                all_trials_count=len(study.trials),
                random_seed=seed,
            )

            # Test가 채워졌는지 확인
            manifest_dict = manifest.to_dict()
            results = manifest_dict.get("results", {})
            best_trial_data = results.get("best_trial", {})
            metrics = best_trial_data.get("metrics", {})
            test_metrics = metrics.get("test")

            print(f"\n  Manifest 검증:")
            print(f"    - stage: {manifest.stage}")
            print(f"    - test 값: {test_metrics}")

            if test_metrics is not None:
                print(f"    ✅ test가 채워짐 (Gate 3 정상)")
            else:
                print(f"    ❌ test가 None (오류)")

            # 파일 저장
            output_dir = Path(__file__).parent.parent.parent / "data" / "tuning_test"
            filepath = save_manifest(manifest, output_dir)
            print(f"    - 저장 경로: {filepath}")

        # ============================================================
        # 결과 요약
        # ============================================================
        print("\n" + "=" * 60)
        print("E2E 테스트 결과 요약")
        print("=" * 60)

        print(f"\n  튜닝 Trial: {n_trials}")
        print(f"  완료 Trial: {len(completed_trials)}")
        print(f"  Gate 1 통과: {len(gate1_passed)}")
        print(f"  Gate 2 통과: {len(gate2_passed)}")
        print(f"  최종 후보: {len(final_candidates)}")

        if final_candidates:
            print(f"\n  🎉 E2E 테스트 성공!")
            return True
        else:
            print(f"\n  ⚠️ 최종 후보 없음")
            return False

    finally:
        runner_module._run_single_backtest = original_func
        set_test_mode(False)  # TEST_MODE 비활성화


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gate 파이프라인 E2E 테스트")
    parser.add_argument("--trials", type=int, default=20, help="시행 횟수 (기본: 20)")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드 (기본: 42)")
    parser.add_argument("--top-n", type=int, default=3, help="Top-N (기본: 3)")

    args = parser.parse_args()

    success = run_gate_e2e_test(n_trials=args.trials, seed=args.seed, top_n=args.top_n)
    sys.exit(0 if success else 1)
