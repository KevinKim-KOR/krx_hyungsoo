"""POC6-11 — H1 주간 ETF 상대성과 선별 검증 CLI(PC 수동 · CPU · 저장소 루트에서 실행).

    python scripts/run_weekly_selection.py prepare   # 봉인 · 자격 · 날짜 · 표본 · 모델 배정 잠금(성과 계산 0)
    python scripts/run_weekly_selection.py run       # 잠금과 같을 때만 공식 1회(검증 → 선택 → 시험 → 보고)
    python scripts/run_weekly_selection.py verify    # 새 학습 없이 저장 산출물에서 다시 계산 · 대조

코드 결함 정정(성과 때문 아님): `prepare --correction-reason "…"` = 정정 잠금(이전 잠금 · 실행 보존) → `run`.

외부 조회 · OCI · 라이브 DB 쓰기 0. 산출물 = `state/ml/research/poc6_11/` 에 추가만. 마지막 줄 = `RESULT {json}`.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Optional, Sequence

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.feature_gain import protocol as P8  # noqa: E402
from app.weekly_selection import flow as FL  # noqa: E402
from app.weekly_selection import protocol as PR  # noqa: E402
from app.weekly_selection import verify as VR  # noqa: E402

RC = {
    "OK": 0,
    "CHECK_REQUIRED": 2,
    "DATA_SHORT": 2,
    "BUDGET_STOP": 2,
    "MISMATCH": 2,
    "FAILED": 2,
    "REFUSED": 3,
    "BUSY": 3,
    "ERROR": 1,
}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="POC6-11 weekly ETF relative return selection"
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
    root = REPO / PR.ROOT
    out: dict = {"command": args.command}
    try:
        if args.command == "prepare":
            doc = FL.prepare(
                root, PR.DB, REPO, correction_reason=args.correction_reason
            )
            fx = doc["facts"]
            out.update(
                status="OK",
                lock_id=doc["lock_id"],
                eligible_rows=fx["eligible_rows"],
                val_weeks=fx["val"]["weeks"],
                test_weeks=fx["test"]["weeks"],
                fits=fx["fits"],
                env=doc["env"],
                corrects=doc.get("corrects"),
            )
        elif args.command == "run":
            res = FL.run(root, PR.DB, REPO)
            j = res["report"]["judgment"]
            out.update(
                status=res["meta"]["status"],
                run_id=res["meta"]["run_id"],
                selection=res["report"].get("selection"),
                h1=j["h1"],
                candidate=j["candidate"],
                uncertainty=j.get("uncertainty"),
                stop=res["report"].get("stop"),
            )
        else:
            out.update(VR.verify(root, PR.DB, run_id=args.run_id, repo=REPO))
    except (PR.CheckRequired, P8.CheckRequired) as e:
        out.update(status="CHECK_REQUIRED", reason=str(e)[:500])
    except PR.Refused as e:
        out.update(status="REFUSED", reason=str(e))
    except P8.Busy as e:
        out.update(status="BUSY", reason=str(e))
    except Exception as e:  # noqa: BLE001 — 실패 기록(부분 산출물은 그대로 보존)
        traceback.print_exc()
        out.update(status="ERROR", reason=f"{type(e).__name__}: {e}"[:300])
    print("RESULT " + json.dumps(out, ensure_ascii=False, default=str))
    codes = [RC.get(out.get("status", "ERROR"), 1)]
    if out.get("run_status") is not None:
        codes.append(RC.get(out["run_status"], 1))
    return max(codes)


if __name__ == "__main__":
    sys.exit(main())
