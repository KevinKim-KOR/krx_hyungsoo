"""POC6-09 — 기존 모델의 검토 우선순위 효용 검증 CLI(PC 수동 · 저장소 루트에서 실행 · 새 학습 없음).

    python scripts/run_review_priority.py run       # 08 입력 사전 대조 → protocol → 계산 → 저장(공식 1회)
    python scripts/run_review_priority.py verify    # 고정 입력에서 다시 계산해 저장 결과 · protocol · 실행 상태 대조

코드 결함 정정 · 중단 뒤 재실행만 `run --correction-reason "…"`(이전 실행 보존 · 바뀐 코드 기록 · 성과 때문의 재실행 금지).
외부 조회 · OCI · 라이브 DB 0. 산출물 = `state/ml/research/poc6_09/` 에 추가만. 마지막 줄 = `RESULT {json}`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.review_priority import flow as F  # noqa: E402

RC = {
    "OK": 0,
    "CHECK_REQUIRED": 2,
    "MISMATCH": 2,
    "RUN_FAILED": 2,
    "REFUSED": 3,
    "BUSY": 3,
    "ERROR": 1,
}


def _clock() -> datetime:
    return datetime.now(timezone.utc)


def _head() -> Optional[str]:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="POC6-09 review priority study")
    ap.add_argument("command", choices=("run", "verify"))
    ap.add_argument(
        "--correction-reason",
        default=None,
        help="코드 결함 정정 · 중단 뒤 재실행 사유(성과 때문의 재실행 금지)",
    )
    ap.add_argument("--run-id", default=None, help="verify 할 실행(없으면 마지막)")
    args = ap.parse_args(argv)
    root = REPO / F.ROOT
    out: dict = {"command": args.command}
    try:
        if args.command == "run":
            res = F.run(
                root,
                REPO,
                _clock,
                correction_reason=args.correction_reason,
                base_commit=_head(),
            )
            sc = res["report"]["scopes"]
            out.update(
                status=res["meta"]["status"],
                run_id=res["meta"]["run_id"],
                judge={
                    s: {m: v["status"] for m, v in sc[s]["judge"].items()} for s in sc
                },
                sample_enough={s: sc[s]["sample"]["enough"] for s in sc},
            )
        else:
            out.update(F.verify(root, REPO, run_id=args.run_id))
    except F.CheckRequired as e:
        out.update(status="CHECK_REQUIRED", reason=str(e))
    except F.Refused as e:
        out.update(status="REFUSED", reason=str(e))
    except F.Busy as e:
        out.update(status="BUSY", reason=str(e))
    except Exception as e:  # noqa: BLE001 — 실패 기록(부분 산출물은 그대로 보존)
        traceback.print_exc()
        out.update(status="ERROR", reason=f"{type(e).__name__}: {e}"[:300])
    print("RESULT " + json.dumps(out, ensure_ascii=False, default=str))
    return RC.get(out.get("status", "ERROR"), 1)


if __name__ == "__main__":
    sys.exit(main())
