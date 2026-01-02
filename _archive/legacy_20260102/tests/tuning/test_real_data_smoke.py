# -*- coding: utf-8 -*-
"""
tests/tuning/test_real_data_smoke.py
실데이터 스모크 테스트 (작은 유니버스)

실행: python -m tests.tuning.test_real_data_smoke --trials 20 --seed 42

목적:
- Mock이 아닌 실제 데이터로 튜닝 파이프라인 검증
- 작은 유니버스 (5~20개 ETF)
- 3~6년 기간
- trials 20~50

주의:
- 실제 데이터 연결 필요
- 실행 시간이 Mock 대비 길어질 수 있음
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
    check_gate1,
    check_gate2,
    check_gate3,
    deduplicate_top_n_candidates,
    run_backtest_for_tuning,
    run_backtest_for_final,
    clear_global_cache,
    create_manifest,
    save_manifest,
    compute_universe_hash,
)
from extensions.tuning.gates import set_test_mode

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def get_real_trading_calendar(start: date, end: date) -> list:
    """
    실제 거래일 캘린더 조회

    TODO: 실제 데이터 소스에서 조회하도록 구현
    현재는 주말 제외한 간이 캘린더 반환
    """
    from datetime import timedelta

    # 실제 구현 시 아래 주석 해제
    # from app.services.market_service import get_trading_calendar
    # return get_trading_calendar(start, end)

    # 간이 캘린더 (주말 제외)
    calendar = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            calendar.append(current)
        current += timedelta(days=1)
    return calendar


def get_real_universe() -> list:
    """
    실제 유니버스 조회

    TODO: 실제 데이터 소스에서 조회하도록 구현
    현재는 샘플 ETF 리스트 반환
    """
    # 실제 구현 시 아래 주석 해제
    # from app.services.universe_service import get_etf_universe
    # return get_etf_universe()

    # 샘플 ETF 리스트 (작은 유니버스)
    return [
        "069500",  # KODEX 200
        "102110",  # TIGER 200
        "229200",  # KODEX 코스닥150
        "251340",  # KODEX 코스닥150선물인버스
        "114800",  # KODEX 인버스
        "122630",  # KODEX 레버리지
        "233740",  # KODEX 코스닥150레버리지
        "252670",  # KODEX 200선물인버스2X
        "261240",  # KODEX 미국S&P500선물(H)
        "305720",  # KODEX 2차전지산업
    ]


def run_real_data_smoke_test(
    n_trials: int = 20,
    seed: int = 42,
    top_n: int = 3,
    use_mock: bool = True,  # 실제 데이터 연결 전까지 True
):
    """
    실데이터 스모크 테스트 실행

    Args:
        n_trials: 시행 횟수
        seed: 랜덤 시드
        top_n: Gate1 Top-N
        use_mock: Mock 사용 여부 (실제 데이터 연결 전까지 True)
    """
    print("\n" + "#" * 60)
    print(f"# 실데이터 스모크 테스트")
    print(f"# n_trials={n_trials}, seed={seed}, top_n={top_n}")
    print(f"# use_mock={use_mock}")
    print("#" * 60)

    # 유니버스 조회
    universe = get_real_universe()
    universe_hash = compute_universe_hash(universe)

    print(f"\n[유니버스]")
    print(f"  종목 수: {len(universe)}")
    print(f"  universe_hash: {universe_hash[:16]}...")
    print(f"  종목: {universe[:5]}... (처음 5개)")

    # 기간 설정 (3~6년)
    end_date = date(2024, 6, 30)
    start_date = date(2020, 1, 1)  # 약 4.5년

    trading_calendar = get_real_trading_calendar(start_date, end_date)

    print(f"\n[기간]")
    print(f"  시작: {start_date}")
    print(f"  종료: {end_date}")
    print(f"  거래일 수: {len(trading_calendar)}")

    # Mock 사용 시 패치
    if use_mock:
        print(f"\n⚠️ Mock 모드로 실행 (실제 데이터 연결 전)")
        import extensions.tuning.runner as runner_module
        from tests.tuning.test_mini_tuning import (
            mock_run_single_backtest,
            MockBacktestService,
        )

        original_func = runner_module._run_single_backtest
        runner_module._run_single_backtest = mock_run_single_backtest

        import tests.tuning.test_mini_tuning as mini_tuning_module

        mini_tuning_module._mock_service = MockBacktestService(seed)

    # TEST_MODE 활성화 (skip 플래그 사용 허용)
    set_test_mode(True)
    clear_global_cache()

    try:
        # 파라미터 범위
        lookbacks = [3, 6, 12]

        param_ranges = {
            "ma_period": {"min": 20, "max": 100, "step": 10, "type": "int"},
            "rsi_period": {"min": 5, "max": 25, "step": 5, "type": "int"},
        }

        split_config = SplitConfig()
        data_config = DataConfig(
            data_version="real_v1" if not use_mock else "mock_v1",
            universe_version="etf_small_v1",
            universe_hash=universe_hash,
            universe_count=len(universe),
        )

        # TuningObjective 생성
        objective = TuningObjective(
            start_date=start_date,
            end_date=end_date,
            trading_calendar=trading_calendar,
            lookbacks=lookbacks,
            param_ranges=param_ranges,
            split_config=split_config,
            data_config=data_config,
        )

        # Optuna Study 생성
        sampler = optuna.samplers.TPESampler(seed=seed)
        study = optuna.create_study(direction="maximize", sampler=sampler)

        print(f"\n[설정]")
        print(f"  룩백: {lookbacks}")
        print(f"  파라미터: {list(param_ranges.keys())}")
        print(f"  시행 횟수: {n_trials}")

        # ============================================================
        # Phase 1: 튜닝 실행
        # ============================================================
        print("\n" + "=" * 60)
        print("Phase 1: 튜닝 실행")
        print("=" * 60)

        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

        # 결과 분석
        stats = objective.get_stats()

        print(f"\n[튜닝 결과]")
        print(f"  전체 시행: {stats['trial_count']}")
        print(
            f"  가드레일 실패: {stats['guardrail_failures']} ({stats['guardrail_failure_rate']:.1%})"
        )
        print(f"  고유 파라미터: {stats.get('unique_params_count', 0)}")
        print(f"  중복 파라미터: {stats.get('duplicate_params_count', 0)}")

        # 실패 사유 Top3
        fail_reasons = stats.get("guardrail_fail_reasons", {})
        if fail_reasons:
            print(f"\n  실패 사유 Top3:")
            for i, (reason, count) in enumerate(list(fail_reasons.items())[:3]):
                pct = stats.get("guardrail_fail_reason_pct", {}).get(reason, 0)
                print(f"    {i+1}. {reason}: {count}건 ({pct:.0%})")

        # ============================================================
        # Phase 2: Gate 1 - Top-N 선정
        # ============================================================
        print("\n" + "=" * 60)
        print("Phase 2: Gate 1 - Top-N 선정")
        print("=" * 60)

        completed_trials = [
            t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE
        ]

        # 후보 리스트 생성
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

        # 중복 제거
        deduped_candidates = deduplicate_top_n_candidates(candidates, top_n=top_n)

        print(f"\n  후보 수: {len(candidates)} → {len(deduped_candidates)} (중복 제거)")

        gate1_passed = []
        for c in deduped_candidates:
            # 결과 재계산
            result = run_backtest_for_tuning(
                params=c["params"],
                start_date=start_date,
                end_date=end_date,
                lookback_months=12,
                trading_calendar=trading_calendar,
                use_cache=True,
            )

            gate1_result = check_gate1(
                result,
                top_n=top_n,
                skip_logic_check=True,  # Mock 데이터
                skip_mdd_check=True,  # Mock 데이터
            )

            status = (
                "✅ PASS"
                if gate1_result.passed
                else f"❌ FAIL: {gate1_result.failures}"
            )
            print(
                f"  Trial #{c['trial_number']}: Val Sharpe={c['val_sharpe']:.3f} - {status}"
            )
            print(f"    params: {c['params']}")

            if gate1_result.passed:
                gate1_passed.append(
                    {**c, "result": result, "gate1_result": gate1_result}
                )

        print(f"\n  Gate 1 통과: {len(gate1_passed)}/{len(deduped_candidates)}")

        if not gate1_passed:
            print("\n⚠️ Gate 1 통과 후보 없음")
            return False

        # ============================================================
        # Phase 3: Manifest 저장
        # ============================================================
        print("\n" + "=" * 60)
        print("Phase 3: Manifest 저장")
        print("=" * 60)

        best_candidate = gate1_passed[0]

        manifest = create_manifest(
            stage="tuning",
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
            random_seed=seed,
        )

        # Manifest 검증
        manifest_dict = manifest.to_dict()
        data_section = manifest_dict.get("data", {})

        print(f"\n  Manifest 검증:")
        print(f"    - run_id: {manifest.run_id}")
        print(f"    - stage: {manifest.stage}")
        print(f"    - universe_hash: {data_section.get('universe_hash', '')[:16]}...")
        print(f"    - universe_count: {data_section.get('universe_count', 0)}")

        # 파일 저장
        output_dir = Path(__file__).parent.parent.parent / "data" / "tuning_test"
        filepath = save_manifest(manifest, output_dir)
        print(f"    - 저장 경로: {filepath}")

        # ============================================================
        # 결과 요약
        # ============================================================
        print("\n" + "=" * 60)
        print("실데이터 스모크 테스트 결과 요약")
        print("=" * 60)

        print(f"\n  유니버스: {len(universe)}개 ETF")
        print(f"  기간: {start_date} ~ {end_date}")
        print(f"  튜닝 Trial: {n_trials}")
        print(f"  Gate 1 통과: {len(gate1_passed)}")
        print(f"  최적 후보: Trial #{best_candidate['trial_number']}")
        print(f"    - params: {best_candidate['params']}")
        print(f"    - Val Sharpe: {best_candidate['val_sharpe']:.4f}")

        print(f"\n  🎉 실데이터 스모크 테스트 성공!")
        return True

    finally:
        if use_mock:
            runner_module._run_single_backtest = original_func
        set_test_mode(False)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="실데이터 스모크 테스트")
    parser.add_argument("--trials", type=int, default=20, help="시행 횟수 (기본: 20)")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드 (기본: 42)")
    parser.add_argument("--top-n", type=int, default=3, help="Top-N (기본: 3)")
    parser.add_argument(
        "--real", action="store_true", help="실제 데이터 사용 (기본: Mock)"
    )

    args = parser.parse_args()

    success = run_real_data_smoke_test(
        n_trials=args.trials, seed=args.seed, top_n=args.top_n, use_mock=not args.real
    )
    sys.exit(0 if success else 1)
