"""POC5-08 — 사후평가 모집단 · 분모 · 가격 상태(설계 §3 · §4 · PLAN §2-1 · 판정 §3-B).

```text
손상        04 problems(필수 표 · 결과 표 기록) + 실행 없는 항목 · 없는 항목을 가리키는 결과 ·
            같은 키 2행 이상(실행 event_id · 항목 (event_id, item_seq) · 결과 (event, item, series, horizon)) ·
            대상 항목 values_json 해석 불가 · 실행 날짜(YYYY-MM-DD) · 대상 실행의 예정 시각(HH:MM) · 실행 시각
            (시간대 있는 ISO · KST 날짜 = 실행 날짜) · 결과 행의 horizon · status · 숫자 · 날짜 · 계산 시각(시간대
            있는 ISO) → CHECK_REQUIRED(빈 모집단 · 500 · 대체 시각으로 처리하지 않음)
모집단      02 대상(FINALIZED · PRIMARY_LIVE · off_schedule 0 · evaluable 1 · ticker · sector ·
            market/SP500 · index_group) 중 신호일 ≤ 신호 종료일 · disposition 관측 5종(04 R1 과 같음)
            — 평가 · 전달 · 노출과 무관(평가는 어떤 필터에도 없다)
가격        저장 결과 그대로(종료일 상태로 되돌리지 않음) · 결과 없는 슬롯 = 평가일(04 eval_dates)이
            price_asof_date 보다 뒤 = 미도래 · 같거나 앞 = 도래 후 미기록(오류 · PRICE_MISSING 아님)
```
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import date, timedelta, timezone
from typing import Any, Optional

from app.alert_retro import features as F
from app.ledger_reports import dates
from app.ledger_reports.r1 import OBSERVED_DISPOSITIONS
from app.ledger_reports.source import Snapshot
from app.three_push_runtime import ledger_outcome
from app.three_push_runtime import ledger_outcome_prices as px

HORIZONS = ledger_outcome.HORIZONS
MATURED = ledger_outcome.MATURED
PENDING_NOT_DUE = "PENDING_NOT_DUE"
PENDING_DUE = "PENDING_DUE"
PENDING = (PENDING_NOT_DUE, PENDING_DUE)
STATUS_TEXT = {  # 결측 3종은 03 화면(alert_records/format.ts STATUS_LABEL)과 같은 문구
    MATURED: "성숙",
    ledger_outcome.T0_MISSING: "기준 가격 없음",
    ledger_outcome.PRICE_MISSING: "가격 자료 없음",
    ledger_outcome.UNTRACKED_AFTER_EXIT: "매도 뒤 추적 중단",
    ledger_outcome.UNSUPPORTED: "지원 계열 없음",
    PENDING_NOT_DUE: "미도래",
    PENDING_DUE: "도래 후 미기록",
}
SIGN_TEXT = {
    "UP": "기준가격 대비 +5 종가 상승",
    "DOWN": "기준가격 대비 +5 종가 하락",
    "FLAT": "기준가격 대비 +5 종가 변화 없음",
}
OUTCOME_FIELDS = (
    "series_id",
    "horizon",
    "status",
    "t0_price",
    "t0_price_asof",
    "eval_date",
    "eval_price",
    "return_raw",
    "max_up_raw",
    "max_down_raw",
    "path_points",
    "price_basis",
    "computed_at",
)
_PROBLEM_LIMIT = 20
_STORED = (
    MATURED,
    ledger_outcome.T0_MISSING,
    ledger_outcome.PRICE_MISSING,
    ledger_outcome.UNTRACKED_AFTER_EXIT,
    ledger_outcome.UNSUPPORTED,
)
_REAL = ("t0_price", "eval_price", "return_raw", "max_up_raw", "max_down_raw")
_TEXT = ("t0_price_asof", "price_basis")
_HHMM = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
_KST = timezone(timedelta(hours=9))


def _day(v: Any) -> bool:
    try:
        return isinstance(v, str) and date.fromisoformat(v).isoformat() == v
    except ValueError:
        return False


def _real(v: Any) -> bool:
    ok = isinstance(v, (int, float)) and not isinstance(v, bool)
    return v is None or (ok and math.isfinite(float(v)))


def _row_ok(o: dict[str, Any]) -> bool:
    """결과 행 형식 — 이 단계가 읽는 칸만(모르는 horizon · status 도 손상으로 본다)."""
    return (
        o.get("horizon") in HORIZONS
        and not isinstance(o.get("horizon"), bool)
        and o.get("status") in _STORED
        and isinstance(o.get("series_id"), str)
        and bool(o["series_id"])
        and all(_real(o.get(k)) for k in _REAL)
        and (o.get("path_points") is None or type(o.get("path_points")) is int)
        and (o.get("eval_date") is None or _day(o.get("eval_date")))
        and all(o.get(k) is None or isinstance(o.get(k), str) for k in _TEXT)
        and F.aware_time(o.get("computed_at")) is not None
    )


def _run_ok(r: dict[str, Any], target: bool) -> bool:
    """실행 시각 형식 — 모든 실행은 날짜 · 가격 결과 대상 실행은 예정 시각 · 실행 시각까지."""
    if not _day(r.get("runtime_date_kst")):
        return False
    if not target:
        return True
    schedule = r.get("schedule_expected")
    at = F.aware_time(r.get("runtime_kst"))
    return (
        isinstance(schedule, str)
        and _HHMM.match(schedule) is not None
        and at is not None
        and at.astimezone(_KST).date().isoformat() == r["runtime_date_kst"]
    )


def _dup(keys: Any) -> int:
    return sum(1 for n in Counter(keys).values() if n > 1)


def check_copy(snap: Snapshot) -> list[str]:
    """사본 손상 사유(없으면 []) — 04 problems 에 참조 · 중복 · 형식 검사를 더한다."""
    problems = list(snap.problems)
    runs = {r["event_id"] for r in snap.runs}
    items = {(i["event_id"], i["item_seq"]) for i in snap.items}
    orphan_items = [i for i in snap.items if i["event_id"] not in runs]
    if orphan_items:
        problems.append(f"참조 손상: 실행 기록 없는 항목 {len(orphan_items)}건")
    for what, n in (
        ("실행 event_id", _dup(r["event_id"] for r in snap.runs)),
        (
            "항목 (event_id, item_seq)",
            _dup((i["event_id"], i["item_seq"]) for i in snap.items),
        ),
        (
            "가격 결과 (event, item, series, horizon)",
            _dup(
                (o["event_id"], o["item_seq"], o["series_id"], o["horizon"])
                for o in snap.outcomes
            ),
        ),
    ):
        if n:
            problems.append(f"중복 키: 같은 {what} 키가 2행 이상 {n}건")
    target_runs = {t.event_id for t in snap.targets}
    bad_runs = sum(1 for r in snap.runs if not _run_ok(r, r["event_id"] in target_runs))
    if bad_runs:
        problems.append(f"형식 손상: 실행 날짜 · 예정 시각 · 실행 시각 {bad_runs}건")
    bad_rows = sum(1 for o in snap.outcomes if not _row_ok(o))
    if bad_rows:
        problems.append(
            f"형식 손상: 가격 결과 행(horizon · status · 숫자 · 날짜 · 계산 시각) {bad_rows}행"
        )
    orphan = sum(
        1 for o in snap.outcomes if (o["event_id"], o["item_seq"]) not in items
    )
    if orphan:
        problems.append(f"참조 손상: 없는 항목을 가리키는 가격 결과 {orphan}행")
    targets = {(t.event_id, t.item_seq) for t in snap.targets}
    bad = 0
    for i in snap.items:
        if (i["event_id"], i["item_seq"]) not in targets:
            continue
        try:
            ok = isinstance(json.loads(i.get("values_json") or "{}"), dict)
        except ValueError:
            ok = False
        bad += 0 if ok else 1
    if bad:
        problems.append(f"values_json 해석 불가(대상 항목) {bad}건")
    if len(problems) > _PROBLEM_LIMIT:
        rest = len(problems) - _PROBLEM_LIMIT
        problems = problems[:_PROBLEM_LIMIT] + [f"외 {rest}건"]
    return problems


def _slot(row: dict[str, Any], expected: Optional[str]) -> dict[str, Any]:
    s = {f: row.get(f) for f in OUTCOME_FIELDS}
    h = int(s["horizon"])
    s["expected_eval_date"] = expected
    s["partial_path"] = s["path_points"] is not None and int(s["path_points"]) < h
    s["sign"] = None
    if h == F.ML_HORIZON and s["status"] == MATURED and s["return_raw"] is not None:
        r = float(s["return_raw"])
        s["sign"] = "UP" if r > 0 else ("DOWN" if r < 0 else "FLAT")
    return s


def _pending(h: int, expected: Optional[str], price_asof: str) -> dict[str, Any]:
    status = (
        PENDING_NOT_DUE if expected is None or expected > price_asof else PENDING_DUE
    )
    s: dict[str, Any] = {f: None for f in OUTCOME_FIELDS}
    s.update(
        horizon=h,
        status=status,
        expected_eval_date=expected,
        partial_path=False,
        sign=None,
    )
    return s


def _exclusions(snap: Snapshot, end: str, kept: set[tuple[str, int]]) -> dict[str, int]:
    runs = {r["event_id"]: r for r in snap.runs}
    out: Counter[str] = Counter()
    for i in snap.items:
        r = runs.get(i["event_id"])
        if r is None:
            continue  # check_copy 가 손상으로 막는다
        if str(r.get("runtime_date_kst") or "") > end:
            out["after_end"] += 1
            continue
        if (i["event_id"], i["item_seq"]) in kept:
            continue
        if r["run_state"] != "FINALIZED":
            out["run_not_finalized"] += 1
        elif r.get("cohort") != "PRIMARY_LIVE":
            out["cohort_not_primary_live"] += 1  # LEGACY_DIAGNOSTIC 포함
        elif int(r.get("off_schedule") or 0) == 1:
            out["off_schedule"] += 1
        elif int(i.get("evaluable") or 0) != 1:
            out["evaluable_0"] += 1
        elif i["subject_kind"] not in ledger_outcome._TARGET_KINDS:
            out["subject_not_outcome_target"] += 1
        elif i["subject_kind"] == "market":
            out["market_not_sp500"] += 1
        else:
            out["disposition_outside_observed"] += 1
    return dict(sorted(out.items()))


def build(
    snap: Snapshot, cal: px.Calendar, *, end: str, price_asof: str
) -> dict[str, Any]:
    """모집단 item(가격 슬롯 · 숫자 feature 포함) · 분모 · 전달 · 제외 · 최신 평가."""
    runs = {r["event_id"]: r for r in snap.runs}
    items = {(i["event_id"], i["item_seq"]): i for i in snap.items}
    delivery = {d["event_id"]: d.get("delivery_status") for d in snap.deliveries}
    outcomes: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for o in snap.outcomes:
        outcomes.setdefault((o["event_id"], o["item_seq"]), []).append(o)
    memo: dict[tuple[str, Optional[str]], dict[int, Optional[str]]] = {}
    out: list[dict[str, Any]] = []
    for t in snap.targets:
        item = items[(t.event_id, t.item_seq)]
        if t.signal_date > end or item["disposition"] not in OBSERVED_DISPOSITIONS:
            continue
        run = runs[t.event_id]
        if (t.signal_date, t.schedule) not in memo:
            memo[(t.signal_date, t.schedule)] = dates.eval_dates(
                cal, t.signal_date, t.schedule
            )
        expected = memo[(t.signal_date, t.schedule)]
        status = delivery.get(t.event_id)
        rec: dict[str, Any] = {
            "event_id": t.event_id,
            "item_seq": t.item_seq,
            "signal_date": t.signal_date,
            "schedule_expected": t.schedule,
            "runtime_kst": run.get("runtime_kst"),
            "push_kind": run["push_kind"],
            "contract_version": run.get("contract_version"),
            "subject_kind": t.subject_kind,
            "subject_id": t.subject_id,
            "held": item.get("held"),
            "state": item.get("state"),
            "event_type": item.get("event_type"),
            "exposure": item.get("exposure"),
            "disposition": item["disposition"],
            "delivery_status": status,
            "delivered": item["disposition"] == "sent" and status == "sent",
            "partial": item["disposition"] == "sent" and status == "partial",
            "expected_eval_dates": {str(h): expected[h] for h in HORIZONS},
        }
        in_scope = F.scope_reason(rec) is None
        rec["numeric"] = (
            F.numeric(t.values, rec["push_kind"], t.subject_kind) if in_scope else None
        )
        per = ledger_outcome._expected(t) // len(HORIZONS)
        rows = outcomes.get((t.event_id, t.item_seq), [])
        slots: list[dict[str, Any]] = []
        for h in HORIZONS:
            own = sorted(
                (r for r in rows if r["horizon"] == h), key=lambda r: r["series_id"]
            )
            slots.extend(_slot(r, expected[h]) for r in own)
            slots.extend(
                _pending(h, expected[h], price_asof)
                for _ in range(max(0, per - len(own)))
            )
        rec["slots"] = slots
        rec["series_count"] = per
        out.append(rec)
    out.sort(
        key=lambda r: (
            r["signal_date"],
            r["runtime_kst"] or "",
            r["event_id"],
            r["item_seq"],
        )
    )
    return {
        "items": out,
        "summary": summarize(out),
        "exclusions": _exclusions(
            snap, end, {(r["event_id"], r["item_seq"]) for r in out}
        ),
        "feedback": {
            e: {
                k: snap.feedback[e].get(k)
                for k in ("feedback_seq", "helpfulness", "feedback_at")
            }
            for e in sorted({r["event_id"] for r in out})
            if e in snap.feedback
        },
    }


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    slots = [s for r in items for s in r["slots"]]
    by_h: dict[str, dict[str, int]] = {}
    for h in HORIZONS:
        c = Counter(s["status"] for s in slots if s["horizon"] == h)
        by_h[str(h)] = dict(sorted(c.items()))
    events = {r["event_id"] for r in items}
    return {
        "denominators": {
            "events": len(events),
            "items": len(items),
            "price_observations": sum(r["series_count"] for r in items),
            "price_slots": len(slots),
            "signal_dates": len({r["signal_date"] for r in items}),
            # 결과 행이 기록된 실제 가격 계열(미지원 표시 `unsupported:` 제외) — 미성숙 슬롯은 계열 미상
            "series_recorded": len(
                {
                    s["series_id"]
                    for s in slots
                    if s["series_id"] and not s["series_id"].startswith("unsupported:")
                }
            ),
        },
        "status_by_horizon": by_h,
        "delivery": {
            "dispositions": dict(
                sorted(Counter(r["disposition"] for r in items).items())
            ),
            "delivered_items": sum(1 for r in items if r["delivered"]),
            "partial_items": sum(1 for r in items if r["partial"]),
            "exposure": dict(
                sorted(Counter(r["exposure"] or "NONE" for r in items).items())
            ),
        },
    }
