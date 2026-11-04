"""POC6-20 — 시장 정보 추가 효용 비교 CLI(PC 수동 · CPU · 저장소 루트에서 실행).

    python scripts/run_market_context_value.py prepare   # 봉인 · H1 분모 · 시장 4열 · 공통 분모 잠금(성과 계산 0)
    python scripts/run_market_context_value.py run       # 잠금과 같을 때만 공식 1회(선행 재생 → 주 평가 → 보고)
    python scripts/run_market_context_value.py verify    # 새 학습 없이 저장 산출물에서 다시 계산 · 대조

코드 결함 정정(성과 때문 아님): `prepare --correction-reason "…"` = 정정 잠금(이전 잠금 · 실행 보존) → `run`.

외부 조회 · OCI · 라이브 DB 쓰기 0. 산출물 = `state/ml/research/poc6_20/` 에 추가만. 마지막 줄 = `RESULT {json}`.
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
from app.market_context_value import flow as FW  # noqa: E402
from app.market_context_value import protocol as P20  # noqa: E402
from app.market_context_value import verify as VR  # noqa: E402
from app.weekly_selection import protocol as PR  # noqa: E402

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
    ap = argparse.ArgumentParser(description="POC6-20 market context incremental value")
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
    root = REPO / P20.ROOT
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
                defined_signals=fx["defined_signals"],
                val_weeks=fx["val"]["weeks"],
                test_weeks=fx["test"]["weeks"],
                fits=fx["fits"],
                env=doc["env"],
                corrects=doc.get("corrects"),
            )
        elif args.command == "run":
            res = FW.run(root, PR.DB, REPO)
            j = res["report"]["judgment"]
            out.update(
                status=res["meta"]["status"],
                run_id=res["meta"]["run_id"],
                market_gain=j["market_gain"],
                candidate=j["candidate"],
                uncertainty=j.get("uncertainty"),
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
        if (
            args.command == "run"
        ):  # 1회 공식 실행이 FAILED 로 끝났으면 그 실행 폴더를 알려 준다
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
