# -*- coding: utf-8 -*-
"""
tests/tuning/test_gate2_loop.py
Gate2 WF outsample 안정성 검증 루프

실행: python -m tests.tuning.test_gate2_loop --trials 30 --seed 42 --runs 3

목적:
- Gate1 → Gate2까지 반복 실행 (Gate3는 하지 않음)
- WF outsample이 안정적으로 통과되는지 확인
- TEST_MODE OFF 상태로 실행 (skip 플래그 사용 불가)
- 룩백별 cache_key 구분 확인

주의:
- 실제 데이터 연결 시 use_mock=False로 변경
"""
import logging
import sys
from datetime import date
from pathlib import Path

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
    Period,
    SplitConfig,
    CostConfig,
    DataConfig,
    DEFAULT_COSTS,
    TuningObjective,
    MiniWalkForward,
    check_gate1,
    check_gate2,
    deduplicate_top_n_candidates,
    run_backtest_for_tuning,
    clear_global_cache,
    create_manifest,
    save_manifest,
    compute_universe_hash,
)
from extensions.tuning.gates import is_test_mode

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def get_trading_calendar(start: date, end: date) -> list:
    """거래일 캘린더 생성 (주말 제외)"""
    from datetime import timedelta

    calendar = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            calendar.append(current)
        current += timedelta(days=1)
    return calendar


def get_universe() -> list:
    """ETF 유니버스"""
    return [
        "069500",  # KODEX 200
        "102110",  # TIGER 200
        "229200",  # KODEX 코스닥150
        "114800",  # KODEX 인버스
        "122630",  # KODEX 레버리지
        "233740",  # KODEX 코스닥150레버리지
        "252670",  # KODEX 200선물인버스2X
        "261240",  # KODEX 미국S&P500선물(H)
        "305720",  # KODEX 2차전지산업
        "091160",  # KODEX 반도체
    ]


def run_gate2_loop(
    n_trials: int = 30,
    seed: int = 42,
    top_n: int = 5,
    n_runs: int = 3,
    use_mock: bool = True,
):
    """
    Gate2 WF outsample 안정성 검증 루프

    Args:
        n_trials: 시행 횟수
        seed: 랜덤 시드
        top_n: Gate1 Top-N
        n_runs: 반복 실행 횟수
        use_mock: Mock 사용 여부
    """
    print("\n" + "#" * 60)
    print("# Gate2 WF Outsample 안정성 검증 루프")
    print(f"# n_trials={n_trials}, seed={seed}, top_n={top_n}, n_runs={n_runs}")
    print(f"# TEST_MODE={is_test_mode()}, use_mock={use_mock}")
    print("#" * 60)

    # TEST_MODE 확인 (OFF여야 함)
    if is_test_mode():
        print("\n⚠️ 경고: TEST_MODE가 ON입니다. 실전 검증을 위해 OFF 상태로 실행하세요.")

    # 유니버스
    universe = get_universe()
    universe_hash = compute_universe_hash(universe)

    print(f"\n[유니버스]")
    print(f"  종목 수: {len(universe)}")
    print(f"  universe_hash: {universe_hash[:16]}...")

    # Mock 패치
    if use_mock:
        print(f"\n⚠️ Mock 모드로 실행")
        import extensions.tuning.runner as runner_module
        from tests.tuning.test_mini_tuning import (
            mock_run_single_backtest,
            MockBacktestService,
        )

        original_func = runner_module._run_single_backtest
        runner_module._run_single_backtest = mock_run_single_backtest

        import tests.tuning.test_mini_tuning as mini_tuning_module

    # 결과 저장
    all_run_results = []

    try:
        for run_idx in range(n_runs):
            run_seed = seed + run_idx * 100
            print("\n" + "=" * 60)
            print(f"Run {run_idx + 1}/{n_runs} (seed={run_seed})")
            print("=" * 60)

            # Mock 서비스 초기화 (run마다 다른 seed)
            if use_mock:
                mini_tuning_module._mock_service = MockBacktestService(run_seed)

            clear_global_cache()

            # 기간 설정 (run마다 약간 다르게)
            end_date = date(2024, 6, 30)
            start_date = date(2020 - run_idx, 1, 1)  # 2020, 2019, 2018...

            trading_calendar = get_trading_calendar(start_date, end_date)

            print(f"\n  기간: {start_date} ~ {end_date} ({len(trading_calendar)}일)")

            # 설정
            lookbacks = [3, 6, 12]
            param_ranges = {
                "ma_period": {"min": 20, "max": 100, "step": 10, "type": "int"},
                "rsi_period": {"min": 5, "max": 25, "step": 5, "type": "int"},
            }

            split_config = SplitConfig()
            data_config = DataConfig(
                data_version="mock_v1" if use_mock else "real_v1",
                universe_version="etf_small_v1",
                universe_hash=universe_hash,
                universe_count=len(universe),
            )

            # ============================================================
            # Phase 1: 튜닝 실행
            # ============================================================
            print(f"\n  [Phase 1] 튜닝 실행 (n_trials={n_trials})")

            objective = TuningObjective(
                start_date=start_date,
                end_date=end_date,
                trading_calendar=trading_calendar,
                lookbacks=lookbacks,
                param_ranges=param_ranges,
                split_config=split_config,
                data_config=data_config,
            )

            sampler = optuna.samplers.TPESampler(seed=run_seed)
            study = optuna.create_study(direction="maximize", sampler=sampler)
            study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

            stats = objective.get_stats()
            print(f"    완료: {stats['trial_count']}건, 가드레일 실패: {stats['guardrail_failures']}건")

            # ============================================================
            # Phase 2: Gate 1 - Top-N 선정
            # ============================================================
            print(f"\n  [Phase 2] Gate 1 - Top-N 선정")

            completed_trials = [
                t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE
            ]

            candidates = []
            for trial in completed_trials:
                if "val_sharpe" in trial.user_attrs:
                    candidates.append(
                        {
                            "trial_number": trial.number,
                            "params": trial.params,
                            "val_sharpe": trial.user_attrs["val_sharpe"],
                            "params_hash": trial.user_attrs.get("params_hash", ""),
                        }
                    )

            deduped_candidates = deduplicate_top_n_candidates(candidates, top_n=top_n)
            print(f"    후보: {len(candidates)} → {len(deduped_candidates)} (중복 제거)")

            gate1_passed = []
            for c in deduped_candidates:
                result = run_backtest_for_tuning(
                    params=c["params"],
                    start_date=start_date,
                    end_date=end_date,
                    lookback_months=12,
                    trading_calendar=trading_calendar,
                    use_cache=True,
                )

                # Gate1: skip 플래그 없이 실행 (TEST_MODE OFF)
                # Mock 데이터에서는 logic_check/mdd_check가 실패할 수 있음
                # 실제 데이터에서는 통과해야 함
                try:
                    gate1_result = check_gate1(
                        result,
                        top_n=top_n,
                        skip_logic_check=False,
                        skip_mdd_check=False,
                    )
                except RuntimeError as e:
                    # TEST_MODE OFF에서 skip 플래그 사용 시 에러
                    print(f"    ❌ RuntimeError: {e}")
                    continue

                if gate1_result.passed:
                    gate1_passed.append(
                        {**c, "result": result, "gate1_result": gate1_result}
                    )
                    print(f"    ✅ Trial #{c['trial_number']}: Val Sharpe={c['val_sharpe']:.3f}")
                else:
                    print(f"    ❌ Trial #{c['trial_number']}: {gate1_result.failures[:2]}")

            print(f"    Gate 1 통과: {len(gate1_passed)}/{len(deduped_candidates)}")

            if not gate1_passed:
                print(f"    ⚠️ Gate 1 통과 후보 없음 - 다음 run으로")
                all_run_results.append(
                    {
                        "run": run_idx + 1,
                        "seed": run_seed,
                        "gate1_passed": 0,
                        "gate2_passed": 0,
                        "best_stability": None,
                    }
                )
                continue

            # ============================================================
            # Phase 3: Gate 2 - WF Outsample 안정성
            # ============================================================
            print(f"\n  [Phase 3] Gate 2 - WF Outsample 안정성")

            gate2_passed = []
            for c in gate1_passed:
                # Mini Walk-Forward 실행
                wf = MiniWalkForward(
                    start_date=start_date,
                    end_date=end_date,
                    trading_calendar=trading_calendar,
                    train_months=12,
                    val_months=3,
                    outsample_months=3,
                    stride_months=6,
                )

                wf_results_list = wf.run(c["params"])

                # WF 결과를 Gate2 형식으로 변환
                wf_results = [
                    {"sharpe": r.outsample_metrics.sharpe if r.outsample_metrics else 0}
                    for r in wf_results_list
                ]

                gate2_result = check_gate2(
                    c["result"],
                    wf_results,
                    min_stability_score=1.0,
                    min_win_rate=0.60,
                )

                stability = gate2_result.metadata.get("stability_score", 0)
                win_rate = gate2_result.metadata.get("win_rate", 0)

                if gate2_result.passed:
                    gate2_passed.append(
                        {
                            **c,
                            "gate2_result": gate2_result,
                            "wf_results": wf_results_list,
                            "stability_score": stability,
                            "win_rate": win_rate,
                        }
                    )
                    print(
                        f"    ✅ Trial #{c['trial_number']}: "
                        f"stability={stability:.2f}, win_rate={win_rate:.0%}"
                    )
                else:
                    print(
                        f"    ❌ Trial #{c['trial_number']}: "
                        f"stability={stability:.2f}, win_rate={win_rate:.0%} - {gate2_result.failures}"
                    )

            print(f"    Gate 2 통과: {len(gate2_passed)}/{len(gate1_passed)}")

            # 결과 저장
            best_stability = max([c["stability_score"] for c in gate2_passed], default=None)
            all_run_results.append(
                {
                    "run": run_idx + 1,
                    "seed": run_seed,
                    "period": f"{start_date}~{end_date}",
                    "gate1_passed": len(gate1_passed),
                    "gate2_passed": len(gate2_passed),
                    "best_stability": best_stability,
                }
            )

            # Manifest 저장 (stage=gate2)
            if gate2_passed:
                best_candidate = max(gate2_passed, key=lambda x: x["stability_score"])
                manifest = create_manifest(
                    stage="gate2",
                    start_date=start_date,
                    end_date=end_date,
                    lookbacks=lookbacks,
                    trials=n_trials,
                    split_config=split_config,
                    costs=DEFAULT_COSTS,
                    data_config=data_config,
                    param_ranges=param_ranges,
                    best_result=best_candidate["result"],
                    all_trials_count=len(study.trials),
                    random_seed=run_seed,
                )

                output_dir = Path(__file__).parent.parent.parent / "data" / "tuning_test"
                filepath = save_manifest(manifest, output_dir)
                print(f"    Manifest: {filepath.name}")

        # ============================================================
        # 전체 결과 요약
        # ============================================================
        print("\n" + "=" * 60)
        print("Gate2 루프 결과 요약")
        print("=" * 60)

        print(f"\n  {'Run':<5} {'Seed':<8} {'Period':<25} {'G1':<5} {'G2':<5} {'Best Stab':<10}")
        print("  " + "-" * 60)
        for r in all_run_results:
            period = r.get("period", "N/A")
            stab = f"{r['best_stability']:.2f}" if r["best_stability"] else "N/A"
            print(
                f"  {r['run']:<5} {r['seed']:<8} {period:<25} "
                f"{r['gate1_passed']:<5} {r['gate2_passed']:<5} {stab:<10}"
            )

        # 성공 여부 판단
        gate2_success_count = sum(1 for r in all_run_results if r["gate2_passed"] > 0)
        success_rate = gate2_success_count / n_runs if n_runs > 0 else 0

        print(f"\n  Gate2 통과 run: {gate2_success_count}/{n_runs} ({success_rate:.0%})")

        if success_rate >= 0.5:
            print(f"\n  🎉 Gate2 WF outsample 안정성 검증 성공!")
            return True
        else:
            print(f"\n  ⚠️ Gate2 통과율 낮음 - 파라미터/유니버스 조정 필요")
            return False

    finally:
        if use_mock:
            runner_module._run_single_backtest = original_func


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gate2 WF Outsample 안정성 검증 루프")
    parser.add_argument("--trials", type=int, default=30, help="시행 횟수 (기본: 30)")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드 (기본: 42)")
    parser.add_argument("--top-n", type=int, default=5, help="Top-N (기본: 5)")
    parser.add_argument("--runs", type=int, default=3, help="반복 실행 횟수 (기본: 3)")
    parser.add_argument("--real", action="store_true", help="실제 데이터 사용 (기본: Mock)")

    args = parser.parse_args()

    success = run_gate2_loop(
        n_trials=args.trials,
        seed=args.seed,
        top_n=args.top_n,
        n_runs=args.runs,
        use_mock=not args.real,
    )
    sys.exit(0 if success else 1)
