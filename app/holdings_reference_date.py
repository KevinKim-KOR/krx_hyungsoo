"""POC5-07 — 가격 비교 기준일 설정 · 수정 · 해제(PC · PUT /holdings/trade-history 의 action).

설계 §2 · §3 · §9 · PLAN §2-2 · §2-6 · §7:

```text
요청   {action: "reference_date", request_id: UUID, base_revision: int ≥ 0,
        reference_date: "YYYY-MM-DD" | null,
        targets: [{position_id, cycle_id}, ...]}   대상 1 ~ 200 · 겹침 없음
입력   날짜 = 유효 · KST 오늘 이하(휴장일 · 가격 없는 날 허용) · null = 해제 → 아니면 422
순서   commit 안에서 request_id 재시도 확인(같은 hash = 쓰기 없이 응답 · 다른 hash = 409)
       → revision(문서와 같아야 · V1 = 0) 다르면 409 → 대상마다 현재 계산에서 찾기(없음 = 409 ·
       실제 매수로 시작한 기간 = 422) → 현재 값과 같으면 '변경 없음' → 바뀌는 대상만 기록 →
       하나도 없으면 쓰지 않음(revision 그대로) · 있으면 V1 확정 · 한 번 교체(holdings_store.commit)
응답   {status, revision, changed: [cycle_id], unchanged: [cycle_id]}
```

REFERENCE_DATE 는 계산 밖 메타데이터라 holdings(수량 · 평단) · OCI 적용 payload 가 바뀌지 않는다
(holdings_book). 일괄 설정의 '이미 설정된 기간 덮어쓰지 않음'은 화면이 기준일 없는 기간만 보내고
여기서 base_revision 일치를 확인해 보장한다(서버 별도 표지 없음 · 판정 §9-1).
"""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

from app import holdings_book as book
from app import holdings_store as store
from app.holdings_history import (
    HistoryConflict,
    HistoryInputError,
    blank_record,
    compute_doc,
    content_hash,
    valid_record_id,
)

ACTION = "reference_date"
MAX_TARGETS = 200
REQUEST_KEYS = {"action", "request_id", "base_revision", "reference_date", "targets"}


def _is_day(v: Any) -> bool:
    try:
        return isinstance(v, str) and date.fromisoformat(v).isoformat() == v
    except ValueError:
        return False


def _is_id(v: Any) -> bool:
    return isinstance(v, str) and v != ""


def normalize(req: Any, *, today: str) -> dict[str, Any]:
    """요청 → 정규화한 내용(재시도 비교 · 기록 생성의 근거). 실패면 HistoryInputError."""
    if not isinstance(req, dict) or req.get("action") != ACTION:
        raise HistoryInputError("가격 비교 기준일 요청이 아닙니다.")
    if (
        set(req) != REQUEST_KEYS
    ):  # reference_date 빠짐을 '해제'로 받지 않는다(해제 = null 명시)
        raise HistoryInputError(
            "요청 칸은 action · request_id · base_revision · reference_date · targets 입니다."
        )
    if not valid_record_id(req.get("request_id")):
        raise HistoryInputError("request_id 는 UUID 여야 합니다.")
    base = req.get("base_revision")
    if isinstance(base, bool) or not isinstance(base, int) or base < 0:
        raise HistoryInputError("base_revision 은 0 이상의 정수입니다.")
    day = req.get("reference_date")
    if day is not None and not _is_day(day):
        raise HistoryInputError("가격 비교 기준일은 YYYY-MM-DD 형식의 날짜입니다.")
    if day is not None and day > today:
        raise HistoryInputError(f"가격 비교 기준일은 오늘({today}) 이후일 수 없습니다.")
    targets = req.get("targets")
    if not isinstance(targets, list) or not 1 <= len(targets) <= MAX_TARGETS:
        raise HistoryInputError(f"대상 보유 기간은 1 ~ {MAX_TARGETS}개입니다.")
    pairs: list[list[str]] = []
    for t in targets:
        pid = t.get("position_id") if isinstance(t, dict) else None
        cid = t.get("cycle_id") if isinstance(t, dict) else None
        if not (_is_id(pid) and _is_id(cid)) or set(t) != {
            "position_id",
            "cycle_id",
        }:
            raise HistoryInputError("대상은 position_id · cycle_id 두 칸입니다.")
        if [pid, cid] in pairs:
            raise HistoryInputError("같은 보유 기간이 두 번 있습니다.")
        pairs.append([pid, cid])
    return {"action": ACTION, "reference_date": day, "targets": pairs}


def _reply(status: str, revision: int, changed: list, unchanged: list) -> dict:
    return {
        "status": status,
        "revision": revision,
        "changed": changed,
        "unchanged": unchanged,
    }


def apply_reference_dates(req: Any) -> dict[str, Any]:
    """가격 비교 기준일 1 ~ N 기간 → 한 번 저장. 422 = 입력 오류 · 409 = 충돌."""
    cmd = normalize(req, today=store.today_kst())
    request_id = req["request_id"]
    fingerprint = content_hash(cmd)
    day = cmd["reference_date"]

    def change(state: dict[str, Any]):
        status, doc = state["status"], copy.deepcopy(state["doc"])
        records = doc["personal_trade_history"]["records"]
        done = [r for r in records if r.get("request_id") == request_id]
        if done:  # 재시도 확인이 revision 확인보다 먼저다(입력 정정 일괄 저장과 같음)
            if any(r.get("request_hash") != fingerprint for r in done):
                raise HistoryConflict(
                    "같은 저장 ID 에 다른 내용이 있습니다 — 새로고침하세요."
                )
            changed = [r["cycle_id"] for r in done]
            unchanged = [cid for _, cid in cmd["targets"] if cid not in changed]
            return _reply(status, doc["revision"], changed, unchanged), None
        if req["base_revision"] != doc["revision"]:
            raise HistoryConflict(
                "다른 화면에서 보유가 바뀌었습니다 — 새로고침한 뒤 다시 설정하세요."
            )
        cur = compute_doc(doc)
        cycles = {
            (p["position_id"], c["cycle_id"]): c
            for p in cur["positions"]
            for c in p["cycles"]
        }
        new, changed, unchanged = [], [], []
        for pid, cid in cmd["targets"]:
            cy = cycles.get((pid, cid))
            if cy is None:
                raise HistoryConflict(
                    "보유가 바뀌었거나 없는 보유 기간입니다 — 새로고침하세요."
                )
            if cy["opened_by"] not in book.ANCHORS:
                raise HistoryInputError(
                    "가격 비교 기준일은 기준잔고 · 잔고 등록으로 시작한 기간에만 둡니다"
                    "(실제 매수로 시작한 기간은 거래일을 씁니다)."
                )
            if cy["reference_date"] == day:  # 같은 값 재설정 · 미설정 해제 = 변경 없음
                unchanged.append(cid)
                continue
            new.append(blank_record(book.REFERENCE, pid, cid, {"reference_date": day}))
            changed.append(cid)
        if not new:
            return _reply(status, doc["revision"], changed, unchanged), None
        at = store.now_kst()
        store.materialize(doc, at)  # V1 첫 저장 = 기존 가상 ID 그대로 확정(POC5-05)
        for r in new:
            r.update(recorded_at=at, request_id=request_id, request_hash=fingerprint)
            records.append(r)
        result = compute_doc(doc)
        doc["holdings"] = result["holdings"]
        doc["revision"] += 1
        return _reply("V2", doc["revision"], changed, unchanged), doc

    return store.commit(change)
