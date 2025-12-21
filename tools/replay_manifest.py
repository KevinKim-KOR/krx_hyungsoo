# -*- coding: utf-8 -*-
"""
tools/replay_manifest.py
Manifest 재실행 도구 - Phase 1.7 재현성 증명

manifest json을 읽어 동일한 params/period/universe로 백테스트를 재실행하고
원본 metrics와 비교하여 PASS/FAIL을 출력한다.

사용법:
    python -m tools.replay_manifest <manifest_path>
    python -m tools.replay_manifest data/tuning_test/gate2_20251220_xxx.json

허용오차:
    - mock 모드: abs diff <= 1e-6
    - real 모드: abs diff <= 1e-3
"""
import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from extensions.tuning import (
    run_backtest_for_tuning,
    clear_global_cache,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class ReplayResult:
    """재실행 결과"""

    manifest_path: str
    original_metrics: Dict[str, float]
    replayed_metrics: Dict[str, float]
    diffs: Dict[str, float]
    passed: bool
    tolerance: float
    failures: List[str]


def get_trading_calendar(start_date: str, end_date: str) -> List[date]:
    """거래일 캘린더 생성 (주말 제외)"""
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    calendar = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            calendar.append(current)
        current += timedelta(days=1)
    return calendar


def load_manifest(manifest_path: str) -> Dict[str, Any]:
    """Manifest JSON 로드"""
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_replay_config(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """
    Manifest에서 재실행에 필요한 설정 추출

    v4.1: 멀티 룩백 증거 (by_lookback) 지원
    - by_lookback이 있으면 전체 룩백을 재실행하여 검증
    - 없으면 min_lookback_months 단일 값으로 검증 (하위 호환)

    v4.2: Gate2 WF 결과 (walkforward) 지원
    - walkforward가 있으면 stability_score, win_rate, outsample_sharpes 검증
    """
    config = manifest.get("config", {})
    data = manifest.get("data", {})
    results = manifest.get("results", {})
    best_trial = results.get("best_trial", {})
    environment = manifest.get("environment", {})

    # period 추출 (config.period.start_date 또는 config.period_start)
    period = config.get("period", {})
    period_start = period.get("start_date") or config.get("period_start")
    period_end = period.get("end_date") or config.get("period_end")

    # lookbacks 추출 (config.lookbacks)
    lookbacks = config.get("lookbacks", [3, 6, 12])

    # min_lookback_months 추출 (best_trial.debug.min_lookback_months)
    debug = best_trial.get("debug", {})
    min_lookback_months = debug.get("min_lookback_months") or debug.get(
        "lookback_months", 12
    )

    # by_lookback 추출 (v4.1 멀티 룩백 증거)
    by_lookback = best_trial.get("by_lookback", {})

    # combined_score 추출
    combined_score = best_trial.get("combined_score")

    # walkforward 추출 (v4.2 Gate2 WF 결과)
    walkforward = best_trial.get("walkforward", {})

    # seed 추출
    random_seed = environment.get("random_seed", 42)

    # universe_hash 추출 (결정론적 seed 계산용)
    universe_hash = data.get("universe_hash", "")

    # data_snapshot_hash 추출 (real 모드 재현성 검증용)
    data_snapshot_hash = data.get("data_snapshot_hash", "")

    return {
        "params": best_trial.get("params", {}),
        "period_start": period_start,
        "period_end": period_end,
        "lookbacks": lookbacks,
        "min_lookback_months": min_lookback_months,
        "by_lookback": by_lookback,
        "combined_score": combined_score,
        "walkforward": walkforward,
        "data_version": data.get("data_version", "unknown"),
        "universe_codes": data.get("sample_codes", []),
        "universe_hash": universe_hash,
        "data_snapshot_hash": data_snapshot_hash,
        "random_seed": random_seed,
    }


def replay_backtest(
    params: Dict[str, Any],
    period_start: str,
    period_end: str,
    lookback_months: int,
    universe_codes: List[str],
    use_mock: bool = True,
    random_seed: int = 42,
) -> Dict[str, float]:
    """
    백테스트 재실행 - manifest의 best_trial과 동일한 조건

    manifest의 best_trial.debug.lookback_months가 실제 사용된 lookback
    run_phase15_realdata.py에서 Gate1 검증 시 해당 lookback만 사용하므로
    replay도 동일하게 해당 lookback만 사용
    """
    clear_global_cache()

    # Mock 패치 (필요시)
    original_func = None
    runner_module = None
    if use_mock:
        import extensions.tuning.runner as _runner_module
        from tests.tuning.test_mini_tuning import (
            mock_run_single_backtest,
            MockBacktestService,
        )
        import tests.tuning.test_mini_tuning as mini_tuning_module

        runner_module = _runner_module
        original_func = runner_module._run_single_backtest
        runner_module._run_single_backtest = mock_run_single_backtest
        # 전역 Mock 서비스를 새로 생성하여 seed 적용
        mini_tuning_module._mock_service = MockBacktestService(random_seed)

    try:
        trading_calendar = get_trading_calendar(period_start, period_end)

        # manifest의 lookback_months와 동일한 조건으로 실행
        result = run_backtest_for_tuning(
            params=params,
            start_date=date.fromisoformat(period_start),
            end_date=date.fromisoformat(period_end),
            lookback_months=lookback_months,
            trading_calendar=trading_calendar,
            use_cache=False,
            universe_codes=universe_codes if universe_codes else None,
        )

        # Phase 2.1: debug 필드 추가
        debug_fields = {}
        if result and result.debug:
            debug_fields = {
                "lookback_start_date": (
                    result.debug.lookback_start_date.isoformat()
                    if result.debug.lookback_start_date
                    else None
                ),
                "effective_eval_start": (
                    result.debug.effective_eval_start.isoformat()
                    if result.debug.effective_eval_start
                    else None
                ),
                "bars_used": result.debug.bars_used,
                "signal_days": result.debug.signal_days,
                "order_count": result.debug.order_count,
            }

        return {
            "sharpe": result.val.sharpe if result and result.val else 0,
            "cagr": result.val.cagr if result and result.val else 0,
            "mdd": result.val.mdd if result and result.val else 0,
            "debug": debug_fields,
        }
    finally:
        if use_mock and original_func is not None and runner_module is not None:
            runner_module._run_single_backtest = original_func


def compare_metrics(
    original: Dict[str, float],
    replayed: Dict[str, float],
    tolerance: float,
) -> tuple:
    """메트릭 비교"""
    diffs = {}
    failures = []

    for key in ["sharpe", "cagr", "mdd"]:
        orig_val = original.get(key, 0)
        replay_val = replayed.get(key, 0)
        diff = abs(orig_val - replay_val)
        diffs[key] = diff

        if diff > tolerance:
            failures.append(
                f"{key}: orig={orig_val:.6f}, replay={replay_val:.6f}, diff={diff:.6f} > tol={tolerance}"
            )

    return diffs, failures


def replay_gate2_wf(
    params: Dict[str, Any],
    period_start: str,
    period_end: str,
    lookback_months: int,
    universe_codes: List[str],
    use_mock: bool = True,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """
    Gate2 Walk-Forward 재실행

    Returns:
        {
            'windows': int,
            'outsample_sharpes': List[float],
            'stability_score': float,
            'win_rate': float,
        }
    """
    from extensions.tuning import MiniWalkForward, calculate_stability_score, calculate_win_rate

    clear_global_cache()

    # Mock 패치 (필요시)
    original_func = None
    runner_module = None
    if use_mock:
        import extensions.tuning.runner as _runner_module
        from tests.tuning.test_mini_tuning import (
            mock_run_single_backtest,
            MockBacktestService,
        )
        import tests.tuning.test_mini_tuning as mini_tuning_module

        runner_module = _runner_module
        original_func = runner_module._run_single_backtest
        runner_module._run_single_backtest = mock_run_single_backtest
        mini_tuning_module._mock_service = MockBacktestService(random_seed)

    try:
        trading_calendar = get_trading_calendar(period_start, period_end)

        # MiniWalkForward 실행
        wf = MiniWalkForward(
            start_date=date.fromisoformat(period_start),
            end_date=date.fromisoformat(period_end),
            trading_calendar=trading_calendar,
            train_months=12,
            val_months=3,
            outsample_months=3,
            stride_months=6,
            universe_codes=universe_codes if universe_codes else None,
        )
        wf_results_list = wf.run(params)

        outsample_sharpes = [
            r.outsample_metrics.sharpe if r.outsample_metrics else 0
            for r in wf_results_list
        ]
        stability_score = calculate_stability_score(outsample_sharpes)
        win_rate = calculate_win_rate(outsample_sharpes)

        return {
            "windows": len(wf_results_list),
            "outsample_sharpes": outsample_sharpes,
            "stability_score": stability_score,
            "win_rate": win_rate,
        }
    finally:
        if use_mock and original_func is not None and runner_module is not None:
            runner_module._run_single_backtest = original_func


def verify_gate2_wf(
    original_wf: Dict[str, Any],
    replayed_wf: Dict[str, Any],
    tolerance: float,
) -> tuple:
    """
    Gate2 WF 결과 비교

    Returns:
        (diffs, failures)
    """
    diffs = {}
    failures = []

    # stability_score 비교
    orig_stability = original_wf.get("stability_score", 0)
    replay_stability = replayed_wf.get("stability_score", 0)
    diff = abs(orig_stability - replay_stability)
    diffs["stability_score"] = diff
    if diff > tolerance:
        failures.append(
            f"stability_score: orig={orig_stability:.6f}, replay={replay_stability:.6f}, diff={diff:.9f}"
        )

    # win_rate 비교
    orig_win_rate = original_wf.get("win_rate", 0)
    replay_win_rate = replayed_wf.get("win_rate", 0)
    diff = abs(orig_win_rate - replay_win_rate)
    diffs["win_rate"] = diff
    if diff > tolerance:
        failures.append(
            f"win_rate: orig={orig_win_rate:.6f}, replay={replay_win_rate:.6f}, diff={diff:.9f}"
        )

    # outsample_sharpes 비교 (평균)
    orig_sharpes = original_wf.get("outsample_sharpes", [])
    replay_sharpes = replayed_wf.get("outsample_sharpes", [])
    if orig_sharpes and replay_sharpes:
        import numpy as np
        orig_mean = float(np.mean(orig_sharpes))
        replay_mean = float(np.mean(replay_sharpes))
        diff = abs(orig_mean - replay_mean)
        diffs["mean_outsample_sharpe"] = diff
        if diff > tolerance:
            failures.append(
                f"mean_outsample_sharpe: orig={orig_mean:.6f}, replay={replay_mean:.6f}, diff={diff:.9f}"
            )

    return diffs, failures


def replay_manifest(
    manifest_path: str,
    tolerance: Optional[float] = None,
    use_mock: Optional[bool] = None,
) -> ReplayResult:
    """
    Manifest 재실행 및 비교

    v4.1: 멀티 룩백 증거 (by_lookback) 지원
    - by_lookback이 있으면 전체 룩백을 재실행하여 검증
    - 3개 룩백 모두 tol=1e-6로 PASS해야 함

    Args:
        manifest_path: manifest json 경로
        tolerance: 허용오차 (None이면 자동 결정)
        use_mock: Mock 모드 사용 여부 (None이면 data_version으로 자동 결정)

    Returns:
        ReplayResult
    """
    print(f"\n{'=' * 60}")
    print(f"Manifest Replay: {manifest_path}")
    print("=" * 60)

    # Manifest 로드
    manifest = load_manifest(manifest_path)
    config = extract_replay_config(manifest)

    # Mock/Real 자동 결정
    if use_mock is None:
        use_mock = config["data_version"].startswith("mock")

    # 허용오차 자동 결정
    # 완전 결정론적 Mock: tolerance 1e-6
    # Real 모드: 부동소수/데이터 정렬 이슈 가능 (1e-4 기본, 1e-6 시도 가능)
    if tolerance is None:
        tolerance = 1e-6 if use_mock else 1e-4

    print("\n설정:")
    print(f"  - data_version: {config['data_version']}")
    print(f"  - mode: {'mock' if use_mock else 'real'}")
    print(f"  - tolerance: {tolerance}")
    print(f"  - period: {config['period_start']} ~ {config['period_end']}")
    print(f"  - lookbacks: {config['lookbacks']}")
    print(f"  - min_lookback_months: {config['min_lookback_months']}")
    print(f"  - params: {json.dumps(config['params'], sort_keys=True)}")

    by_lookback = config.get("by_lookback", {})
    all_failures = []
    all_diffs = {}
    replayed_by_lookback = {}

    # v4.1: by_lookback이 있으면 전체 룩백 재실행
    if by_lookback:
        print(f"\n멀티 룩백 증거 검증 (by_lookback: {list(by_lookback.keys())})")

        for lb_str, orig_data in by_lookback.items():
            lb = int(lb_str)
            print(f"\n  [Lookback {lb}M]")
            print(
                f"    원본: sharpe={orig_data['val_sharpe']:.6f}, score={orig_data['score']:.6f}"
            )

            # Phase 2.1: 멀티룩백 증거 강화 - debug 필드 출력
            orig_debug = orig_data.get("debug", {})
            if orig_debug:
                print(f"    debug: lookback_start={orig_debug.get('lookback_start_date')}, "
                      f"eval_start={orig_debug.get('effective_eval_start')}, "
                      f"bars={orig_debug.get('bars_used')}, "
                      f"signals={orig_debug.get('signal_days')}, "
                      f"orders={orig_debug.get('order_count')}")

            # 재실행
            replayed = replay_backtest(
                params=config["params"],
                period_start=config["period_start"],
                period_end=config["period_end"],
                lookback_months=lb,
                universe_codes=config["universe_codes"],
                use_mock=use_mock,
                random_seed=config.get("random_seed", 42),
            )

            replayed_by_lookback[lb] = replayed
            print(f"    재실행: sharpe={replayed['sharpe']:.6f}")

            # Phase 2.1: 재실행된 debug 필드 출력
            replayed_debug = replayed.get("debug", {})
            if replayed_debug:
                print(f"    replay: lookback_start={replayed_debug.get('lookback_start_date')}, "
                      f"eval_start={replayed_debug.get('effective_eval_start')}, "
                      f"bars={replayed_debug.get('bars_used')}, "
                      f"signals={replayed_debug.get('signal_days')}, "
                      f"orders={replayed_debug.get('order_count')}")

            # 비교 (val_sharpe 기준)
            orig_sharpe = orig_data["val_sharpe"]
            replay_sharpe = replayed["sharpe"]
            diff = abs(orig_sharpe - replay_sharpe)
            all_diffs[f"lb{lb}_sharpe"] = diff

            if diff <= tolerance:
                print(f"    ✅ diff={diff:.9f} <= tol={tolerance}")
            else:
                all_failures.append(
                    f"lb{lb}_sharpe: orig={orig_sharpe:.6f}, replay={replay_sharpe:.6f}, diff={diff:.9f}"
                )
                print(f"    ❌ diff={diff:.9f} > tol={tolerance}")

        # combined_score 검증
        if config.get("combined_score") is not None:
            orig_combined = config["combined_score"]
            # 재실행된 scores로 combined_score 계산
            replayed_scores = {}
            for lb_str, orig_data in by_lookback.items():
                lb = int(lb_str)
                replayed = replayed_by_lookback[lb]
                replayed_scores[lb] = replayed["sharpe"] - 0.5 * abs(replayed["mdd"])

            replay_combined = (
                min(replayed_scores.values()) if replayed_scores else -999.0
            )
            diff = abs(orig_combined - replay_combined)
            all_diffs["combined_score"] = diff

            print(f"\n  [Combined Score (min)]")
            print(f"    원본: {orig_combined:.6f}")
            print(f"    재실행: {replay_combined:.6f}")
            if diff <= tolerance:
                print(f"    ✅ diff={diff:.9f} <= tol={tolerance}")
            else:
                all_failures.append(
                    f"combined_score: orig={orig_combined:.6f}, replay={replay_combined:.6f}, diff={diff:.9f}"
                )
                print(f"    ❌ diff={diff:.9f} > tol={tolerance}")

        # Gate2 WF 결과 검증 (v4.2)
        walkforward = config.get("walkforward", {})
        if walkforward and walkforward.get("windows"):
            print(f"\n  [Gate2 Walk-Forward 검증]")
            print(f"    원본: windows={walkforward['windows']}, "
                  f"stability={walkforward.get('stability_score', 0):.4f}, "
                  f"win_rate={walkforward.get('win_rate', 0):.2%}")

            # WF 재실행
            replayed_wf = replay_gate2_wf(
                params=config["params"],
                period_start=config["period_start"],
                period_end=config["period_end"],
                lookback_months=config["min_lookback_months"],
                universe_codes=config["universe_codes"],
                use_mock=use_mock,
                random_seed=config.get("random_seed", 42),
            )
            print(f"    재실행: windows={replayed_wf['windows']}, "
                  f"stability={replayed_wf['stability_score']:.4f}, "
                  f"win_rate={replayed_wf['win_rate']:.2%}")

            # 비교
            wf_diffs, wf_failures = verify_gate2_wf(walkforward, replayed_wf, tolerance)
            all_diffs.update(wf_diffs)

            if wf_failures:
                all_failures.extend(wf_failures)
                for f in wf_failures:
                    print(f"    ❌ {f}")
            else:
                print(f"    ✅ Gate2 WF 재현성 PASS (tol={tolerance})")

        # 결과 집계
        passed = len(all_failures) == 0
        original_metrics = {
            f"lb{lb}": by_lookback[str(lb)]
            for lb in config["lookbacks"]
            if str(lb) in by_lookback
        }
        replayed_metrics = replayed_by_lookback

    else:
        # 하위 호환: by_lookback이 없으면 min_lookback_months 단일 검증
        lb = config["min_lookback_months"]
        print(f"\n단일 룩백 검증 (min_lookback_months={lb})")

        replayed = replay_backtest(
            params=config["params"],
            period_start=config["period_start"],
            period_end=config["period_end"],
            lookback_months=lb,
            universe_codes=config["universe_codes"],
            use_mock=use_mock,
            random_seed=config.get("random_seed", 42),
        )

        # 원본 metrics는 manifest에서 직접 추출
        metrics = manifest.get("results", {}).get("best_trial", {}).get("metrics", {})
        val_metrics = metrics.get("val", {})
        original_metrics = {
            "sharpe": val_metrics.get("sharpe", 0),
            "cagr": val_metrics.get("cagr", 0),
            "mdd": val_metrics.get("mdd", 0),
        }

        print(f"\n원본 메트릭 (lookback={lb}M):")
        print(f"  - sharpe: {original_metrics['sharpe']:.6f}")

        print(f"\n재실행 메트릭:")
        print(f"  - sharpe: {replayed['sharpe']:.6f}")

        all_diffs, all_failures = compare_metrics(original_metrics, replayed, tolerance)
        replayed_metrics = replayed
        passed = len(all_failures) == 0

    # 결과 출력
    print("\n" + "=" * 60)
    if passed:
        print("✅ REPLAY PASS - 재현성 검증 통과")
        if by_lookback:
            print(f"   ({len(by_lookback)}개 룩백 모두 tol={tolerance} 이내)")
    else:
        print("❌ REPLAY FAIL - 재현성 검증 실패")
        for f in all_failures:
            print(f"  - {f}")
    print("=" * 60)

    return ReplayResult(
        manifest_path=manifest_path,
        original_metrics=original_metrics,
        replayed_metrics=replayed_metrics,
        diffs=all_diffs,
        passed=passed,
        tolerance=tolerance,
        failures=all_failures,
    )


def replay_multiple(
    manifest_paths: List[str], tolerance: Optional[float] = None
) -> bool:
    """여러 manifest 재실행"""
    results = []
    for path in manifest_paths:
        try:
            result = replay_manifest(path, tolerance)
            results.append(result)
        except Exception as e:
            print(f"\n❌ {path} 재실행 실패: {e}")  # noqa: F541
            results.append(None)

    # 요약
    print(f"\n{'=' * 60}")
    print("Replay 요약")
    print("=" * 60)

    passed_count = sum(1 for r in results if r and r.passed)
    total_count = len(results)

    print(f"\n  {'Manifest':<50} {'Result':<10}")
    print("  " + "-" * 60)
    for i, result in enumerate(results):
        path = manifest_paths[i]
        name = Path(path).name if len(path) > 40 else path
        if result:
            status = "✅ PASS" if result.passed else "❌ FAIL"
        else:
            status = "❌ ERROR"
        print(f"  {name:<50} {status:<10}")

    print(f"\n  총 {passed_count}/{total_count}개 PASS")

    return passed_count == total_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manifest 재실행 도구 - 재현성 증명")
    parser.add_argument(
        "manifest_paths",
        nargs="+",
        help="manifest json 경로 (여러 개 가능)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=None,
        help="허용오차 (기본: mock=1e-6, real=1e-4)",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "mock", "real"],
        default="auto",
        help="실행 모드 (auto: data_version으로 자동 결정, mock: 강제 mock, real: 강제 real)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="강제 mock 모드 (--mode mock과 동일)",
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="강제 real 모드 (--mode real과 동일)",
    )

    args = parser.parse_args()

    # use_mock 결정 (--mode 우선, 그 다음 --mock/--real)
    use_mock = None
    if args.mode == "mock" or args.mock:
        use_mock = True
    elif args.mode == "real" or args.real:
        use_mock = False

    if len(args.manifest_paths) == 1:
        result = replay_manifest(
            args.manifest_paths[0],
            tolerance=args.tolerance,
            use_mock=use_mock,
        )
        sys.exit(0 if result.passed else 1)
    else:
        success = replay_multiple(args.manifest_paths, tolerance=args.tolerance)
        sys.exit(0 if success else 1)
