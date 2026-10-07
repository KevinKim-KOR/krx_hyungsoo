"""POC5-01B — 운영 원장 읽기 전용 대조(OCI · PC 수동 실행 · 새 cron · API 없음).

설계서 §7 · PLAN §2-6. 원장 run · 기존 `runtime_execution_status` · 원장 STARTED 잔류를 비교해
분류별 건수와 ID 만 출력한다. 자동 수정 · 재발송 · backfill 은 하지 않는다.

```text
python scripts/run_decision_ledger_reconcile.py            # 기본 경로(실행 위치 기준 · 저장소 루트에서)
python scripts/run_decision_ledger_reconcile.py --ledger <원장 DB> --runtime <runtime DB>
```

```text
ok                 원장 FINALIZED + 같은 (push_kind, started_at) runtime 행
missing_in_ledger  runtime 에만 있음 — 원장 STARTED · 권한 실패(구조화 오류 로그) · 또는 플래그를
                   끈 동안의 send(하한은 첫 활성 시각 하나)
started_gap        원장 STARTED 로 남음 — 종료 기록 실패 · 프로세스 중단 · 대조 시점에 진행 중
ledger_only        원장에만 있음 — run() 밖 예외(_finish 전 예외 · _finish 안 runtime DB 기록 예외)
```

두 DB 를 `mode=ro` 로 연다. `.env` 를 읽지 않는다. 본문 · 비밀값을 출력하지 않는다.
예외면 status=FAILED · 예외 종류만 출력하고 3 을 돌려준다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app import runtime_state_db  # noqa: E402
from app.three_push_runtime import ledger_store  # noqa: E402
from app.three_push_runtime.ledger_context import CONTRACT_VERSIONS  # noqa: E402

_ORDER = ("ok", "missing_in_ledger", "started_gap", "ledger_only")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="POC5-01B 원장 읽기 전용 대조")
    parser.add_argument("--ledger", default=str(ledger_store.DEFAULT_DB_PATH))
    parser.add_argument("--runtime", default=str(runtime_state_db.DEFAULT_DB_PATH))
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="(POC5-02) 원장 cohort 별 run 수 · run_id 연결 수 · 원장 이전 runtime send 수",
    )
    args = parser.parse_args(argv)
    try:
        ledger, runtime = Path(args.ledger), Path(args.runtime)
        for p in (ledger, runtime):
            if not p.exists():
                raise FileNotFoundError(p.name)
        out = ledger_store.reconcile(ledger, runtime, kinds=CONTRACT_VERSIONS)
        legacy = (
            ledger_store.legacy_summary(ledger, runtime, kinds=CONTRACT_VERSIONS)
            if args.legacy
            else None
        )
    except Exception as e:  # noqa: BLE001 - 예외 종류만 출력한다
        print(f"status=FAILED error_class={type(e).__name__}")
        return 3
    print(f"status=OK floor={out['floor']}")
    print(" ".join(f"{k}={out[k]['count']}" for k in _ORDER))
    for k in _ORDER[1:]:
        if out[k]["ids"]:
            print(f"{k}_ids={','.join(str(i) for i in out[k]['ids'])}")
    if legacy is not None:
        for r in legacy["ledger_runs"]:
            print(
                f"legacy cohort={r['cohort']} kind={r['push_kind']} runs={r['runs']}"
                f" run_id_linked={r['run_id_linked']}"
            )
        for kind, n in legacy["runtime_send_before_ledger"].items():
            print(f"legacy runtime_send_before_ledger kind={kind} runs={n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
