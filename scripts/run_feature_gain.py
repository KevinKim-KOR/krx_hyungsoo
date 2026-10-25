"""POC6-08 — 거래량 · 동일 기간 상대강도 ML 추가 효용 검증 CLI(PC 수동 · CPU · 저장소 루트에서 실행).

    python scripts/run_feature_gain.py lock     # 입력 · 축 · 구간 · 행 · 적격 · 가용 · recipe 잠금(성과 계산 0)
    python scripts/run_feature_gain.py run      # 잠금과 같을 때만 공식 1회(학습 · 예측 · 저장 · 복원 · 보고)
    python scripts/run_feature_gain.py verify   # 새 fit 없이 저장 산출물에서 다시 계산 · 대조

코드 결함 정정(성과 때문 아님): `lock --correction-reason "…"` = 정정 잠금(이전 잠금 · 실행 보존 · 입력 · recipe 같아야 함)
→ `run`. 같은 코드 재실행(중단 등) = `run --correction-reason "…"`.

외부 조회 · OCI · 라이브 DB 쓰기 0. 산출물 = `state/ml/research/poc6_08/` 에 추가만. 마지막 줄 = `RESULT {json}`.
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

from app.feature_gain import protocol as P  # noqa: E402
from app.feature_gain import study as ST  # noqa: E402
from app.feature_gain import verify as VR  # noqa: E402

RC = {
    "OK": 0,
    "CHECK_REQUIRED": 2,
    "MISMATCH": 2,
    "RESTORE_MISMATCH": 2,
    "CONFIG_FAILED": 2,
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
    ap = argparse.ArgumentParser(description="POC6-08 feature gain study")
    ap.add_argument("command", choices=("lock", "run", "verify"))
    ap.add_argument(
        "--correction-reason",
        default=None,
        help="lock = 코드 결함 정정 잠금 사유 · run = 같은 코드 재실행 사유(성과 때문의 재실행 금지)",
    )
    ap.add_argument(
        "--run-id",
        default=None,
        help="verify 할 실행(없으면 지금 잠금의 마지막 실행 · 이전 잠금의 실행도 찾음)",
    )
    args = ap.parse_args(argv)
    root = REPO / P.ROOT
    load = ST.real_loader(REPO, REPO / P.EVIDENCE_ROOT)
    out: dict = {"command": args.command}
    try:
        if args.command == "lock":
            doc = ST.lock(
                root,
                REPO,
                load,
                _clock,
                base_commit=_head(),
                correction_reason=args.correction_reason,
            )
            pl = doc["plan"]
            out.update(
                status="OK",
                lock_id=doc["lock_id"],
                T=pl["T"],
                corrects=doc.get("corrects"),
                eligible=len(pl["eligible"]),
                review=len(pl["review"]),
                train_rows=pl["train_rows"],
                test_rows=pl["test_rows"],
                coverage={
                    c: {s: v["status"] for s, v in sc.items()}
                    for c, sc in pl["coverage"].items()
                },
            )
        elif args.command == "run":
            res = ST.run(
                root, REPO, load, _clock, correction_reason=args.correction_reason
            )
            rep = res["report"]
            out.update(
                status=res["meta"]["status"],
                run_id=res["meta"]["run_id"],
                A={
                    s: {c: v["status"] for c, v in rep["A"][s].items()}
                    for s in P.SCOPES
                },
                B={
                    s: {c: v["status"] for c, v in rep["B"][s].items()}
                    for s in P.SCOPES
                },
                use_candidate={
                    s: [c for c, v in rep["B"][s].items() if v.get("use_candidate")]
                    for s in P.SCOPES
                },
                failed_configs=res["meta"].get("failed_configs"),
            )
        else:
            out.update(VR.verify(root, load, run_id=args.run_id))
    except P.CheckRequired as e:
        out.update(status="CHECK_REQUIRED", reason=str(e))
    except P.Refused as e:
        out.update(status="REFUSED", reason=str(e))
    except P.Busy as e:
        out.update(status="BUSY", reason=str(e))
    except Exception as e:  # noqa: BLE001 — 실패 기록(부분 산출물은 그대로 보존)
        traceback.print_exc()
        out.update(status="ERROR", reason=f"{type(e).__name__}: {e}"[:300])
    print("RESULT " + json.dumps(out, ensure_ascii=False, default=str))
    # verify 는 산출물 대조와 실행 상태 중 나쁜 쪽(복원 불일치 실행이 0 으로 끝나지 않게).
    codes = [RC.get(out.get("status", "ERROR"), 1)]
    if out.get("run_status") is not None:
        codes.append(RC.get(out["run_status"], 1))
    return max(codes)


if __name__ == "__main__":
    sys.exit(main())
