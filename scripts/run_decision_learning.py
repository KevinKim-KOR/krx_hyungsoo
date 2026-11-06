"""POC6-23 — 비용을 반영한 주간 의사결정 학습 CLI(PC 수동 · CPU · 저장소 루트에서 실행).

    python scripts/run_decision_learning.py prepare   # 환경 · 봉인 · 공통 신호 · 분기 창 상한 잠금(성과 계산 0)
    python scripts/run_decision_learning.py run       # 잠금과 같을 때만 공식 1회(새 프로세스 · 참조 → 정답 → fit → 장부)
    python scripts/run_decision_learning.py verify    # 재학습 없이 저장 산출물에서 다시 계산 · 대조

코드 결함 정정(성과 때문 아님): `prepare --correction-reason "…"` = 정정 잠금(이전 잠금 · 실행 보존) → `run`.

BLAS · OpenMP 스레드 환경 변수는 import 전에 1로 고정한다(잠금 · 실행에 기록 · 판정 A-6). 학습 solver 는 첫 호출부터
threads=1 이다. 외부 조회 · OCI · 라이브 DB 쓰기 0. 산출물 = `state/ml/research/poc6_23/` 에 추가만.
마지막 줄 = `RESULT {json}`.
"""

from __future__ import annotations

import os

for _k in ("VECLIB_MAXIMUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_k] = "1"

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import traceback  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Optional, Sequence  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.decision_learning import flow as FW  # noqa: E402
from app.decision_learning import protocol as P23  # noqa: E402
from app.decision_learning import verify as VR  # noqa: E402
from app.feature_gain import protocol as P8  # noqa: E402
from app.weekly_selection import protocol as PR  # noqa: E402

RC = {
    "OK": 0,
    "CHECK_REQUIRED": 2,
    "DATA_SHORT": 2,
    "INSUFFICIENT_DATA": 2,
    "BUDGET_STOP": 2,
    "MISMATCH": 2,
    "FAILED": 2,
    "REFUSED": 3,
    "BUSY": 3,
    "ERROR": 1,
}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="POC6-23 cost-aware weekly decision learning"
    )
    ap.add_argument("command", choices=("prepare", "run", "verify"))
    ap.add_argument(
        "--run-id", default=None, help="verify 할 실행(없으면 지금 잠금의 마지막 실행)"
    )
    ap.add_argument(
        "--correction-reason",
        default=None,
        help="prepare = 코드 결함 정정 잠금 사유(이전 잠금 · 실행 보존 · 입력 · 사실 · recipe 같아야 함)",
    )
    args = ap.parse_args(argv)
    root = REPO / P23.ROOT
    out: dict = {"command": args.command}
    try:
        if args.command == "prepare":
            doc = FW.prepare(
                root, PR.DB, REPO, correction_reason=args.correction_reason
            )
            fx = doc["facts"]
            out.update(
                status="OK",
                lock_id=doc["lock_id"],
                common=fx["common"]["count"],
                val_weeks=fx["val"]["weeks"],
                test_weeks=fx["test"]["weeks"],
                fits=fx["fits"],
                train_upper_min=min(fx["train_upper"].values()),
                env=doc["env"],
                corrects=doc.get("corrects"),
            )
        elif args.command == "run":
            res = FW.run(root, PR.DB, REPO)
            j = res["report"]["judgment"]
            out.update(
                status=res["meta"]["status"],
                run_id=res["meta"]["run_id"],
                decision_gain=j["decision_gain"],
                purpose=j["purpose"],
                risk_burden=j["risk_burden"],
                cost_stress=j["cost_stress"],
                uncertainty=j.get("uncertainty"),
                candidate=j["candidate"],
                stop=res["report"].get("stop"),
            )
        else:
            out.update(VR.verify(root, PR.DB, REPO, run_id=args.run_id))
    except (PR.CheckRequired, P8.CheckRequired) as e:
        out.update(status="CHECK_REQUIRED", reason=str(e)[:500])
    except PR.Refused as e:
        out.update(status="REFUSED", reason=str(e))
    except P8.Busy as e:
        out.update(status="BUSY", reason=str(e))
    except Exception as e:  # noqa: BLE001 — 실패 기록(부분 산출물은 그대로 보존)
        traceback.print_exc()
        out.update(status="ERROR", reason=f"{type(e).__name__}: {e}"[:300])
        if args.command == "run":
            try:
                _ldir, _lk, rdir = PR.latest_run(root)
                meta = PR.load_json(rdir / "run.json")
                out.update(run_id=rdir.name, run_status=meta.get("status"))
            except (
                Exception
            ):  # noqa: BLE001 — 실행 폴더가 없거나 run.json 을 못 쓴 경우
                pass
    print("RESULT " + json.dumps(out, ensure_ascii=False, default=str))
    codes = [RC.get(out.get("status", "ERROR"), 1)]
    if out.get("run_status") is not None:
        codes.append(RC.get(out["run_status"], 1))
    return max(codes)


if __name__ == "__main__":
    sys.exit(main())
