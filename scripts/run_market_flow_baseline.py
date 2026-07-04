"""수동 실행 진입점 — Market Flow ML Dataset + Baseline v1.

지시문 §9.2:
  기존 SQLite 읽기
  → 데이터셋 생성
  → 시간 순서 baseline 학습·평가
  → CSV·JSON artifact 저장
  → 짧은 실행 결과 출력

스케줄러 / 백그라운드 worker / API / UI 연결 없음.
외부 데이터 호출 없음.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _reconfigure_stdio_to_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        rc = getattr(stream, "reconfigure", None)
        if rc is None:
            continue
        try:
            rc(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


_reconfigure_stdio_to_utf8()


from app.market_flow_baseline import (  # noqa: E402
    BASELINE_ARTIFACT_PATH,
    DATASET_PATH,
    run_baseline,
)


def main() -> int:
    artifact = run_baseline()
    print(f"[market-flow-baseline] status={artifact['status']}")
    ds = artifact["dataset"]
    print(
        f"[dataset] rows={ds['row_count']} "
        f"start={ds['as_of_start_date']} end={ds['as_of_end_date']} "
        f"excluded={ds['excluded_row_count']}"
    )
    m = artifact["metrics"]
    print(f"[val] {m['validation']}")
    print(f"[test] {m['test']}")
    li = artifact["latest_inference"]
    print(
        f"[latest_inference] status={li['status']} asof={li['as_of_date']} "
        f"pred={li['predicted_future_kodex200_return_20d_pct']} "
        f"reason={li['unavailable_reason']}"
    )
    print(f"[artifact] dataset={DATASET_PATH} baseline={BASELINE_ARTIFACT_PATH}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
