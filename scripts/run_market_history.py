"""POC6-19 — 과거 시장 자료(코스피 수급 · 원/달러 · WTI) 연구 사본 CLI(맥북 1회성 · 저장소 루트에서 실행).

    python scripts/run_market_history.py fetch            # A 표본 → 조건부 B 장기 → 정규화 · 보고
    python scripts/run_market_history.py verify [--run-id <id>]   # 외부 재조회 없이 원시에서 다시 계산 · 대조

키움 등록 IP 망에서 실행한다(IP 미등록이면 키움 = ACCESS_BLOCKED · Yahoo 는 계속). 08:20 ~ 10:30 KST 시작 금지.
운영 DB · 봉인 판 = 읽기 전용 · OCI 0 · 산출물 = `state/ml/research/poc6_19/<run_id>/`(git 제외).
진행 상황은 stderr · 마지막 줄 = `RESULT {json}`.
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import traceback
from pathlib import Path
from typing import Optional, Sequence

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.market_history import fetch as FT  # noqa: E402
from app.market_history import verify as VR  # noqa: E402

RC = {"OK": 0, "MISMATCH": 2, "REFUSED": 3, "ERROR": 1}


def _interrupt(signum, _frame):
    """종료 신호 = Ctrl-C 와 같게(실행이 '중단'으로 기록하고 원시 · 보고 · 파일 목록을 남긴다)."""
    raise KeyboardInterrupt(f"signal {signum}")


def _latest_run(root: Path) -> Optional[Path]:
    runs = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    return runs[-1] if runs else None


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="POC6-19 historical market context archive"
    )
    ap.add_argument("command", choices=("fetch", "verify"))
    ap.add_argument("--run-id", default=None, help="verify 할 실행(없으면 가장 최근)")
    args = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(message)s"
    )
    root = REPO / FT.ROOT_REL
    out: dict = {"command": args.command}
    try:
        if args.command == "fetch":
            for sig in (signal.SIGTERM, signal.SIGHUP):
                signal.signal(sig, _interrupt)
            out.update(FT.run())
        else:
            run_dir = root / args.run_id if args.run_id else _latest_run(root)
            if run_dir is None or not run_dir.is_dir():
                out.update(status="REFUSED", reason="검산할 실행 폴더가 없다")
            else:
                out.update(run_id=run_dir.name, **VR.verify_run(run_dir))
    except Exception as e:  # noqa: BLE001 — CLI 경계: 종류 · 위치를 남기고 ERROR
        out.update(status="ERROR", error=f"{type(e).__name__}: {e}")
        traceback.print_exc()
    print("RESULT " + json.dumps(out, ensure_ascii=False, sort_keys=True))
    return RC.get(out.get("status", "ERROR"), 1)


if __name__ == "__main__":
    raise SystemExit(main())
