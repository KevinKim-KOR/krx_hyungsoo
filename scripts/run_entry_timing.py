"""POC7-01 — 주간 ETF 신규 후보의 즉시 참여와 한 주 보류 비교 CLI(PC 수동 · CPU · 저장소 루트에서 실행).

    python scripts/run_entry_timing.py prepare   # 입력 해시 · 분모(PLAN §1-4) · 체결 가능 짝 · 주 기록 잠금
                                                 # (성과 계산 0)
    python scripts/run_entry_timing.py run       # 잠금과 같을 때만 공식 1회(경로 · 지표 · 판정 · 보고)
    python scripts/run_entry_timing.py verify    # 저장 산출물을 독립 경로로 다시 계산 · 대조
                                                 # (POC6 build_panel 칸 대조 포함)

코드 결함 정정(성과 때문 아님): `prepare --correction-reason "…"` = 정정 잠금(이전 잠금 · 실행 보존) → `run`.

외부 조회 · OCI · 라이브 DB 쓰기 0. 산출물 = `state/ml/research/poc7_01/` 에 추가만. 마지막 줄 = `RESULT {json}`.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.entry_timing import flow as FW  # noqa: E402
from app.entry_timing import verify as VR  # noqa: E402
from app.entry_timing.protocol import Busy, CheckRequired, Config  # noqa: E402

RC = {"OK": 0, "CHECK_REQUIRED": 2, "BUSY": 3, "ERROR": 1}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="POC7-01 즉시 참여 · 한 주 보류 비교(PC 회고 연구)"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("prepare")
    pp.add_argument("--correction-reason", default=None)
    sub.add_parser("run")
    vp = sub.add_parser("verify")
    vp.add_argument("--run-id", default=None)
    args = ap.parse_args(argv)
    cfg = Config()
    now = datetime.now(timezone.utc)
    try:
        if args.cmd == "prepare":
            out = FW.prepare(cfg, now, args.correction_reason)
        elif args.cmd == "run":
            out = FW.run(cfg, now)
        else:
            rec = VR.verify(cfg, now, args.run_id)
            out = {
                "verify_status": rec["status"],
                "verify_id": rec["verify_id"],
                "run_id": rec["run_id"],
                "failed": [c["name"] for c in rec["checks"] if not c["ok"]],
            }
        status = "OK"
        if args.cmd == "verify" and out["verify_status"] != "VERIFIED_OK":
            status = "CHECK_REQUIRED"  # 불일치 = 0 이 아닌 종료 코드(결과서 판정 D)
    except CheckRequired as e:
        out, status = {"error": str(e)}, "CHECK_REQUIRED"
    except Busy as e:
        out, status = {"error": str(e)}, "BUSY"
    except Exception as e:  # 실패도 한 줄로 남긴다(run 은 FAILED 기록을 이미 썼다)
        traceback.print_exc()
        out, status = {"error": f"{type(e).__name__}: {e}"}, "ERROR"
    print(
        "RESULT "
        + json.dumps(
            {"cmd": args.cmd, "status": status, **out}, ensure_ascii=False, default=str
        )
    )
    return RC[status]


if __name__ == "__main__":
    raise SystemExit(main())
