"""POC6-02 — ETF D20 공동 학습 비교 연구 CLI(PC 수동 · 읽기 전용 · 외부 호출 0).

    python scripts/run_d20_pooled_research.py run            # 맥북 공식 CPU 실행 + RTX PC 실행 묶음
    python scripts/run_d20_pooled_research.py run --smoke    # 1구간 · 지표 없음(시간 · 형식 · 누수 · 표본 수만)
    python scripts/run_d20_pooled_research.py merge --run-dir <폴더> --gpu-result <gpu_result.json>

입력 = 현재 보유 파일(ticker 만) · PC 시장 DB(`mode=ro`) 또는 `--snapshot` 파일.
출력 = `state/ml/research/poc6_02/<생성시각>_<id>/` 새 폴더. DB · 보유 · 원장 쓰기 · OCI · PUSH 0.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.d20_pooled import report as R  # noqa: E402
from app.d20_pooled import runner  # noqa: E402
from app.d20_pooled import study as S  # noqa: E402
from app.d20_pooled.snapshot import SnapshotError  # noqa: E402


def _summary(body: dict) -> None:
    print(
        f"상태: {body['status']} · 완료 범위: {body.get('completion')}"
        + (f" · 사유: {body['reason']}" if body.get("reason") else "")
    )
    print(
        f"기준일 T {body['T']} · 적격 {len(body['eligibility']['eligible'])}종"
        f" · 제외 {len(body['eligibility']['excluded'])}종"
    )
    for c, v in (body.get("candidates") or {}).items():
        print(
            f"  {c}: {v['verdict']}" + (f" ({v['reason']})" if v.get("reason") else "")
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="POC6-02 ETF D20 공동 학습 비교(읽기 전용)"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="맥북 공식 CPU 실행 + RTX PC 실행 묶음")
    p_run.add_argument(
        "--snapshot", type=Path, help="기존 input_snapshot.json 으로 실행"
    )
    p_run.add_argument("--smoke", action="store_true", help="1구간 · 지표 없음")
    p_merge = sub.add_parser("merge", help="RTX PC 결과 취합")
    p_merge.add_argument("--run-dir", type=Path, required=True)
    p_merge.add_argument("--gpu-result", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "run":
            folder = runner.run(snapshot_path=args.snapshot, smoke=args.smoke)
            body = json.loads((folder / "report.json").read_text(encoding="utf-8"))
            print(f"산출 폴더: {folder}")
            _summary(body)
            if (folder / "gpu_bundle.zip").exists():
                print(f"RTX PC 실행 묶음: {folder / 'gpu_bundle.zip'}")
            return 0
        out = runner.merge(args.run_dir, args.gpu_result)
        print(f"취합 보고서: {out}")
        _summary(json.loads(out.read_text(encoding="utf-8")))
        return 0
    except (SnapshotError, S.StudyError) as e:
        print(f"{S.CHECK_REQUIRED}: {e}", file=sys.stderr)
        return 2
    except runner.MergeError as e:
        print(f"취합 거절: {e}", file=sys.stderr)
        return 2
    except R.ArtifactSaveError as e:
        print(f"{S.RUN_FAILED}: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 — 계산 오류를 기각으로 숨기지 않음
        print(f"{S.RUN_FAILED}: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
