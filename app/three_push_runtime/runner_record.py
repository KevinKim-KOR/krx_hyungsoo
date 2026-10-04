"""실행 기록 시작 · 종료 확정 (POC5-01A 러너 기계 분리 · 2026-10-03).

`run_three_push_runtime_oci.py` 의 record 초기화와 `_finish` 본문을 **문장 순서 그대로**
옮겼다. 판정 · 기록 내용 · 키 순서 · 예외 전파 변경 0건.

러너는 `_finish` closure 를 그대로 두고 이 함수를 부른다. 테스트가 러너 모듈에서 바꿔
끼우는 `_HISTORY_PATH` · `insert_status_from_record` 는 러너가 **호출 때마다** 인자로
넘긴다(여기서 import 하면 바꿔 끼우기가 먹지 않는다 · PLAN 1-8).

logger 는 러너 것을 받는다. 모듈 전역 logger 를 두면 운영 로그 파일 경로가 갈라진다
(`runner_spike` 선례).

POC5-01B 원장은 `new_run_record` 직후(실행 진입)와 `finish_run`(정상 종료 27곳)에 붙는다
(PLAN 1-12 · 이번 단계에서는 붙이지 않는다).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from app.runtime_evidence import holdings_risk_flow as _hrf


def new_run_record(
    push_kind: str,
    mode: str,
    *,
    started_at: str,
    runtime_kst: str,
    runtime_date_kst: str,
) -> dict[str, Any]:
    """실행 기록 21키 — 키 순서가 JSONL 줄의 순서다. 바꾸지 않는다."""
    return {
        "push_kind": push_kind,
        "mode": mode,
        "slot_id": None,
        "status": "failed",
        "reason": None,
        "started_at": started_at,
        "finished_at": "",
        "runtime_kst": runtime_kst,
        "runtime_date_kst": runtime_date_kst,
        "param_id": "",
        "param_source": "",
        "message_text_length": 0,
        "availability": {},
        "contentful_fact_count": 0,
        "selection_result_count": 0,
        "unavailable_reasons": {},
        "duplicate_key": "",
        "telegram_attempted": False,
        "telegram_sent": False,
        "partial_delivery": False,
        "error": None,
    }


def finish_run(
    record: dict[str, Any],
    status: str,
    reason: Optional[str] = None,
    error: Optional[str] = None,
    *,
    push_kind: str,
    mode: str,
    logger: Any,
    history_path: Path,
    insert_status: Callable[[dict[str, Any]], Any],
) -> dict[str, Any]:
    """러너의 모든 처리된 종료(`return _finish(...)`)가 지나는 한 곳."""
    _hrf.apply_intraday_records(record, mode=mode, status=status, reason=reason)
    record["status"] = status
    record["reason"] = reason
    record["error"] = error
    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    # Refactor v1 Q9 (c): DB latest status + history JSONL 을 runner 에서 분리 호출.
    insert_status(record)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.info(
        "runtime runner 완료: push_kind=%s mode=%s status=%s reason=%s",
        push_kind,
        mode,
        status,
        reason,
    )
    return record
