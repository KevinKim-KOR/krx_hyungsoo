"""POC5-04 — R0 수집 점검(읽기 전용 · 투자 효과 판정 없음).

설계 개정 1 §3 · §4 · PLAN §2-1.

```text
1 대조       evidence.parse_reconcile — OK · ERRORS(건수 · ID 보존) · NOT_CHECKED
2 예정 실행   거래일마다 시장 08:30 · 보유 09:15 · 12:30 · 15:40 · 장중 09:30 ~ 14:30 매시 + 15:20(11 슬롯)
             ↔ 원장 run(상태 무관 · skipped · no_selection 포함) · 누락 · 중복 · 예정 외 · 비거래일 기록
3 무결성      orphan item · delivery · outcome · 대상 아닌 item 의 outcome · FINALIZED ⇒ delivery ·
             STARTED ⇒ 행 0 · STARTED 잔류 · cohort × 계약
  운영 실패   기간 안 실행 status=failed · 전달 failed · partial(실제 운영 오류 = COLLECTION_OK 아님)
4 가격 결과   02 예상 슬롯(_expected) ↔ price_outcome · 상태별 건수(평가일이 종료일 뒤인 행은 미도래)
5 대기        PENDING_NOT_DUE(평가일 미도래) · PENDING_DUE(평가일 도래 · 결과 미기록 · 원인 미확인)
6 운영 근거   evidence.parse_ops — 종료일 배치 완료 · 그 뒤 동기화 · ops_error_count(> 0 = 점검 필요)
판정          CHECK_REQUIRED(입력 사본 손상 — 다른 조건과 무관) → NOT_READY(시작 meta · 10완료거래일 · 배치 근거)
              → CHECK_REQUIRED(검출 오류) → NOT_READY(대조 미확인)
              → COLLECTION_OK. 자동 수정 · 재생성 0
```
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Optional

from app.ledger_reports import dates, evidence
from app.ledger_reports.evidence import parse_ops, parse_reconcile
from app.ledger_reports.source import REPORT_VERSION, Snapshot, input_summary
from app.three_push_runtime import ledger_outcome, ledger_outcome_prices as px

LIST_CAP = 50
_FINALIZED = "FINALIZED"
_STARTED = "STARTED"


def expected_slots() -> list[tuple[str, str]]:
    """거래일 하루의 (push_kind, 예정 HH:MM) — 러너 예정 시각 상수를 그대로 쓴다."""
    from app.runtime_evidence.holdings_selection_flow import SLOT_TIME_LABEL
    from app.three_push_runtime.ledger_context import INTRADAY_TICKS, MARKET_TIMES

    return (
        [("market_briefing", t) for t in MARKET_TIMES]
        + [("holdings_briefing", t) for t in sorted(SLOT_TIME_LABEL.values())]
        + [("holdings_risk_alert", t) for t in INTRADAY_TICKS]
    )


def _cap(values: list[Any]) -> dict[str, Any]:
    return {"count": len(values), "keys": values[:LIST_CAP]}


def _in(day: Optional[str], start: str, end: str) -> bool:
    return bool(day) and start <= str(day) <= end


def schedule_check(
    snap: Snapshot, days: list[str], start: str, end: str
) -> dict[str, Any]:
    slots = expected_slots()
    trading = set(days)
    seen: Counter[tuple[str, str, str]] = Counter()
    status_by_kind: dict[str, Counter[str]] = {}
    off = non_trading = 0
    for r in snap.runs:
        day = r.get("runtime_date_kst")
        if not _in(day, start, end):
            continue
        status_by_kind.setdefault(r["push_kind"], Counter())[
            str(r.get("status") or r["run_state"])
        ] += 1
        if day not in trading:
            non_trading += 1
        elif int(r.get("off_schedule") or 0) == 1:
            off += 1
        else:
            seen[(day, r["push_kind"], r.get("schedule_expected") or "")] += 1
    missing = [f"{d} {k} {t}" for d in days for k, t in slots if seen[(d, k, t)] == 0]
    dup = [f"{d} {k} {t}" for (d, k, t), n in sorted(seen.items()) if n > 1]
    return {
        "expected": len(days) * len(slots),
        "recorded_on_schedule": sum(seen.values()),
        "missing": _cap(missing),
        "duplicates": _cap(dup),
        "off_schedule_runs": off,
        "non_trading_day_runs": non_trading,
        "status_by_kind": {
            k: dict(sorted(v.items())) for k, v in sorted(status_by_kind.items())
        },
    }


def integrity_check(snap: Snapshot, start: str, end: str) -> dict[str, Any]:
    runs = {r["event_id"]: r for r in snap.runs}
    items = {(i["event_id"], i["item_seq"]) for i in snap.items}
    delivered = {d["event_id"] for d in snap.deliveries}
    item_events = {i["event_id"] for i in snap.items}
    targets = {(t.event_id, t.item_seq) for t in snap.targets}
    orphan_items = sorted(f"{e}#{s}" for e, s in items if e not in runs)
    orphan_del = sorted(e for e in delivered if e not in runs)
    orphan_out = sorted(
        {f"{o['event_id']}#{o['item_seq']}" for o in snap.outcomes}
        - {f"{e}#{s}" for e, s in items}
    )
    non_target = sorted(
        {
            f"{o['event_id']}#{o['item_seq']}"
            for o in snap.outcomes
            if (o["event_id"], o["item_seq"]) in items
            and (o["event_id"], o["item_seq"]) not in targets
        }
    )
    no_delivery = sorted(
        e
        for e, r in runs.items()
        if r["run_state"] == _FINALIZED and e not in delivered
    )
    started_rows = sorted(
        e
        for e, r in runs.items()
        if r["run_state"] == _STARTED and (e in delivered or e in item_events)
    )
    started = sorted(
        e
        for e, r in runs.items()
        if r["run_state"] == _STARTED and _in(r.get("runtime_date_kst"), start, end)
    )
    cohort: Counter[str] = Counter(
        f"{r.get('cohort')}|{r.get('contract_version')}" for r in snap.runs
    )
    return {
        "orphan_items": _cap(orphan_items),
        "orphan_deliveries": _cap(orphan_del),
        "orphan_outcomes": _cap(orphan_out),
        "outcome_on_non_target": _cap(non_target),
        "finalized_without_delivery": _cap(no_delivery),
        "started_with_rows": _cap(started_rows),
        "started_in_window": _cap(started),
        "cohort_contract": dict(sorted(cohort.items())),
    }


def outcome_check(
    snap: Snapshot, cal: px.Calendar, start: str, end: str
) -> dict[str, Any]:
    by_item: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for o in snap.outcomes:
        by_item.setdefault((o["event_id"], o["item_seq"]), []).append(o)
    statuses: Counter[str] = Counter()
    expected = not_due = due = 0
    memo: dict[tuple[str, Optional[str]], dict[int, Optional[str]]] = {}
    for t in snap.targets:
        if not _in(t.signal_date, start, end):
            continue
        expected += ledger_outcome._expected(t)
        per = ledger_outcome._expected(t) // len(ledger_outcome.HORIZONS)
        rows = dates.rows_known_by(by_item.get((t.event_id, t.item_seq), []), end)
        statuses.update(r["status"] for r in rows)
        key = (t.signal_date, t.schedule)
        if key not in memo:
            memo[key] = dates.eval_dates(cal, t.signal_date, t.schedule)
        for h in ledger_outcome.HORIZONS:
            gap = max(0, per - sum(1 for r in rows if r["horizon"] == h))
            when = memo[key][h]
            if when is None or when > end:
                not_due += gap
            else:
                due += gap
    return {
        "expected_slots": expected,
        "recorded": sum(statuses.values()),
        "by_status": dict(sorted(statuses.items())),
        "pending_not_due": not_due,
        "pending_due": due,
        "pending_due_note": "평가일 도래 · 결과 미기록(원인 미확인 — 정상 뒤채우기로 단정하지 않음)",
    }


def operations_check(snap: Snapshot, start: str, end: str) -> dict[str, Any]:
    """기간 안 실제 운영 실패 — 실행 status=failed · 전달 failed · partial(원장이 기록한 사실)."""
    window = {
        r["event_id"]: r
        for r in snap.runs
        if _in(r.get("runtime_date_kst"), start, end)
    }
    failed = sorted(e for e, r in window.items() if r.get("status") == "failed")
    by_kind: dict[str, Counter[str]] = {}
    bad: dict[str, list[str]] = {"failed": [], "partial": []}
    for d in snap.deliveries:
        r = window.get(d["event_id"])
        if r is None:
            continue
        by_kind.setdefault(r["push_kind"], Counter())[d["delivery_status"]] += 1
        if d["delivery_status"] in bad:
            bad[d["delivery_status"]].append(d["event_id"])
    return {
        "run_failed": _cap(failed),
        "delivery_failed": _cap(sorted(bad["failed"])),
        "delivery_partial": _cap(sorted(bad["partial"])),
        "delivery_by_kind": {
            k: dict(sorted(v.items())) for k, v in sorted(by_kind.items())
        },
    }


def build(
    snap: Snapshot,
    cal: px.Calendar,
    *,
    end: str,
    reconcile_text: Optional[str],
    ops_text: Optional[str],
    generated_at: str,
) -> dict[str, Any]:
    start = snap.meta.get("primary_start_date")
    d10 = dates.official_day(cal, start) if start else None
    days = dates.trading_days(cal, start, end) if start else []
    recon = parse_reconcile(
        reconcile_text, first_active_at=snap.meta.get("first_active_at"), end=end
    )
    ops = parse_ops(ops_text, end=end, last_sync_success=snap.sync["last_success_at"])
    schedule = schedule_check(snap, days, start or "", end) if start else None
    integrity = integrity_check(snap, start or "", end)
    outcomes = outcome_check(snap, cal, start, end) if start else None

    operations = operations_check(snap, start or "", end)

    not_ready: list[str] = []
    if not start:
        not_ready.append("원장 시작 meta(primary_start_date) 없음")
    elif d10 is None or end < d10:
        not_ready.append(f"완료 거래일 {dates.OFFICIAL_DAYS}일 미만(D10={d10})")
    if not ops["batch_confirmed"]:
        not_ready.append(ops["reason"])
    if ops["error_count"] is None:
        not_ready.append(ops["error_count_reason"])
    problems: list[str] = []
    if recon["state"] == "ERRORS":
        errs = {k: recon["counts"][k] for k in evidence.ERROR_KINDS}
        problems.append(
            f"OCI 대조 오류 {errs} · 근거 기간 {recon['period']}"
            f" · 종료일 뒤 실행 포함 {recon['includes_after_end']}"
        )
    if ops["error_count"]:
        problems.append(
            f"개발자 확인 운영 오류 {ops['error_count']}건(ops_error_count)"
        )
    if schedule is not None:
        if schedule["missing"]["count"]:
            problems.append(f"예정 실행 누락 {schedule['missing']['count']}")
        if schedule["duplicates"]["count"]:
            problems.append(f"예정 실행 중복 {schedule['duplicates']['count']}")
    for k in (
        "orphan_items",
        "orphan_deliveries",
        "orphan_outcomes",
        "outcome_on_non_target",
        "finalized_without_delivery",
        "started_with_rows",
        "started_in_window",
    ):
        if integrity[k]["count"]:
            problems.append(f"{k} {integrity[k]['count']}")
    for k in ("run_failed", "delivery_failed", "delivery_partial"):
        if operations[k]["count"]:
            problems.append(f"{k} {operations[k]['count']}")
    damaged = [f"입력 사본 손상 — {p}" for p in snap.problems]
    problems = damaged + problems
    if damaged:
        verdict = "CHECK_REQUIRED"  # 손상된 사본은 준비 여부와 무관하게 점검 대상
    elif not_ready:
        verdict = "NOT_READY"
    elif problems:
        verdict = "CHECK_REQUIRED"
    elif recon["state"] == "NOT_CHECKED":
        verdict = "NOT_READY"
        not_ready.append(f"RUNTIME_RECONCILIATION=NOT_CHECKED({recon['reason']})")
    else:
        verdict = "COLLECTION_OK"
    return {
        "report": "R0",
        "version": REPORT_VERSION,
        "generated_at": generated_at,
        "verdict": verdict,
        "verdict_note": "COLLECTION_OK 는 수집 계약 점검 결과이며 투자 효과를 뜻하지 않는다",
        "not_ready_reasons": not_ready,
        "problems": problems,
        "input": input_summary(snap),
        "window": {"start": start, "end": end, "d10": d10, "trading_days": len(days)},
        "reconciliation": recon,
        "schedule": schedule,
        "integrity": integrity,
        "operations": operations,
        "outcomes": outcomes,
        "ops": ops,
    }
