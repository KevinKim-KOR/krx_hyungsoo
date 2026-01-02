# -*- coding: utf-8 -*-
"""
tools/run_phase20_real_gate2.py
Phase 2.0 Real 데이터 엔진 루프 증거 확보 (Gate2 + Real replay)

실행:
    python -m tools.run_phase20_real_gate2 --runs 2 --trials 30 --seed 42 --top-n 5 --real --analysis-mode --force-gate2 --stop-at-gate2

목적:
- Real 데이터에서 Gate2(WF)까지 최소 1~2회 실제로 돌린 로그/manifest를 남긴다
- Real replay(같은 데이터 스냅샷/캐시 기준)에서 결과가 재현되는지 확인한다

PASS 조건 (Phase 2.0):
- (A) real 모드에서 Gate2가 최소 1회라도 실제 실행됨 (완화모드든 정상모드든 상관없음, Gate3 금지)
- (B) real manifest 2개 이상 저장 성공
- (C) 위 manifest들을 replay_manifest --mode real로 재현성 PASS

보안/봉인:
- --force-gate2 / --analysis-mode는 tools/CLI에서만 접근 가능
- UI/서비스 레이어에서는 절대 노출하지 않음
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.run_phase15_realdata import run_phase15_loop


def main():
    parser = argparse.ArgumentParser(
        description="Phase 2.0 Real 데이터 엔진 루프 증거 확보"
    )
    parser.add_argument("--runs", type=int, default=2, help="반복 횟수 (기본: 2)")
    parser.add_argument("--trials", type=int, default=30, help="시행 횟수 (기본: 30)")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드 (기본: 42)")
    parser.add_argument("--top-n", type=int, default=5, help="Top-N (기본: 5)")
    parser.add_argument(
        "--real", action="store_true", help="실제 데이터 사용 (기본: Mock)"
    )
    parser.add_argument(
        "--analysis-mode",
        action="store_true",
        help="분석 모드: 가드레일 실패해도 manifest 저장",
    )
    parser.add_argument(
        "--stop-at-gate2",
        action="store_true",
        help="Gate2까지만 실행 (Gate3 금지)",
    )
    parser.add_argument(
        "--force-gate2",
        action="store_true",
        help="Gate1 후보 0일 때 가드레일 무시하고 Gate2 실행 (--analysis-mode 필수)",
    )

    args = parser.parse_args()

    # Phase 2.0 기본 설정: real + analysis-mode + stop-at-gate2 + force-gate2
    use_mock = not args.real
    analysis_mode = args.analysis_mode
    stop_at_gate2 = args.stop_at_gate2
    force_gate2 = args.force_gate2

    # Phase 2.0 권장 설정 안내
    print("\n" + "=" * 60)
    print("Phase 2.0 Real 데이터 엔진 루프 증거 확보")
    print("=" * 60)
    print("\n권장 실행 커맨드:")
    print("  python -m tools.run_phase20_real_gate2 --runs 2 --trials 30 --seed 42 \\")
    print("         --top-n 5 --real --analysis-mode --force-gate2 --stop-at-gate2")
    print("\nPASS 조건:")
    print("  (A) real 모드에서 Gate2가 최소 1회 실행됨")
    print("  (B) real manifest 2개 이상 저장 성공")
    print("  (C) replay_manifest --mode real로 재현성 PASS")
    print("=" * 60)

    # 실행
    success = run_phase15_loop(
        n_runs=args.runs,
        n_trials=args.trials,
        seed=args.seed,
        top_n=args.top_n,
        use_mock=use_mock,
        analysis_mode=analysis_mode,
        stop_at_gate2=stop_at_gate2,
        force_gate2=force_gate2,
    )

    # Phase 2.0 결과 요약
    print("\n" + "=" * 60)
    print("Phase 2.0 결과 요약")
    print("=" * 60)

    if success:
        print("\n🎉 Phase 2.0 PASS!")
        print("\n다음 단계:")
        print("  1. 생성된 manifest 확인:")
        print("     dir data\\tuning_test\\analysis_real_*.json")
        print("\n  2. Real replay 재현성 테스트:")
        print("     python -m tools.replay_manifest data\\tuning_test\\<manifest>.json --mode real --tolerance 1e-4")
        print("\n  3. 모든 manifest에 대해 replay PASS 확인 후 엔진 Freeze 선언")
    else:
        print("\n⚠️ Phase 2.0 조건 미충족")
        print("\n확인 사항:")
        print("  - Real 데이터 로딩 성공 여부 (preflight)")
        print("  - Gate1 후보 생성 여부 (--force-gate2로 완화 가능)")
        print("  - Gate2 실행 여부")

    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
