"""POC5-04 — R1 원시 가격 결과 리포트(성공 · 적중 판정 없음).

설계 개정 1 §5 · §6 · §7 · PLAN §2-2.

```text
표본        02 가격 결과 대상(FINALIZED · PRIMARY_LIVE · off 0 · evaluable 1 · subject 4종 · market=SP500)
            중 사건일 ∈ [시작일, 종료일] · disposition ∈ 관측 5종
노출        저장된 exposure 그대로 — PRIMARY(주 표) · SECONDARY(보조 표) · NONE(= NULL · '노출 분류 없음')
보기        observed(관측 분포 · 5종 전부) · delivered(disposition sent ∧ delivery sent) · partial 은 건수만
그룹        exposure × 보기 × push_kind · subject_kind · state · contract_version ·
            price_basis · horizon
            (대기 슬롯은 결과 행이 없어 가격 기준을 알 수 없다 → price_basis = '미기록' 그룹에 건수만 ·
             평가일이 종료일 뒤인 행도 그 종료일 기준으로는 미도래 대기로 센다)
제외        기간 안 대상 아닌 행의 사유 + 기간 밖(시작 전 · LEGACY 포함 / 종료일 뒤) item 건수
통계        MATURED 의 return_raw — 평균 · 중앙값 · 25/75 분위 · 최소 · 최대 · max_up/down 중앙값 ·
            n_event · n_item · n_price_observation · n_signal_date · 날짜 묶음 bootstrap
평가        표본 · 통계와 무관 — 최신 평가 있음/없음 event 수와 분포만 부가 표
```
"""

from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any, Optional

from app.ledger_reports import bootstrap, dates
from app.ledger_reports.source import REPORT_VERSION, Snapshot, input_summary
from app.ml_score_validity_metrics import percentile
from app.three_push_runtime import ledger_outcome, ledger_outcome_prices as px


class InvalidInput(ValueError):
    """입력 사본 손상(필수 표 없음 등) — 원시 통계를 만들지 않는다."""


OBSERVED_DISPOSITIONS = (
    "sent",
    "suppressed",
    "cut_by_section_cap",
    "cut_by_daily_cap",
    "not_selected",
)
EXPOSURES = ("PRIMARY", "SECONDARY", "NONE")
EXPOSURE_LABEL = {
    "PRIMARY": "PRIMARY(최초 노출 · 주 표)",
    "SECONDARY": "SECONDARY(반복 노출 · 보조 표)",
    "NONE": "노출 분류 없음",
}
VIEWS = ("observed", "delivered")
NO_BASIS = "미기록"


def _exclusions(
    snap: Snapshot, start: str, end: str, kept: set[tuple[str, int]]
) -> dict[str, int]:
    runs = {r["event_id"]: r for r in snap.runs}
    out: Counter[str] = Counter()
    for i in snap.items:
        r = runs.get(i["event_id"])
        if r is None:
            out["run_missing"] += 1
            continue
        day = str(r.get("runtime_date_kst") or "")
        if day < start:
            out[
                "before_primary_start"
            ] += 1  # LEGACY_DIAGNOSTIC 은 여기(시작일 전 실행)
            continue
        if day > end:
            out["after_end"] += 1
            continue
        key = (i["event_id"], i["item_seq"])
        if key in kept:
            continue
        if r["run_state"] != "FINALIZED":
            out["run_not_finalized"] += 1
        elif r.get("cohort") != "PRIMARY_LIVE":
            out["cohort_not_primary_live"] += 1
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


def _group_order(key: tuple[Any, ...]) -> tuple[Any, ...]:
    """노출(PRIMARY → SECONDARY → NONE) · 보기 · 문자열 키 · horizon(숫자) 순."""
    exposure, view, *rest, horizon = key
    text = tuple("" if v is None else str(v) for v in rest)
    rank = EXPOSURES.index(exposure) if exposure in EXPOSURES else len(EXPOSURES)
    return (rank, str(exposure), VIEWS.index(view), *text, int(horizon))


def _stats(
    rows: list[dict[str, Any]],
    days: list[str],
    horizon: int,
    iterations: int,
    seed: int,
) -> dict[str, Any]:
    matured = [
        r for r in rows if r["status"] == "MATURED" and r.get("return_raw") is not None
    ]
    vals = [float(r["return_raw"]) for r in matured]
    ups = [float(r["max_up_raw"]) for r in matured if r.get("max_up_raw") is not None]
    downs = [
        float(r["max_down_raw"]) for r in matured if r.get("max_down_raw") is not None
    ]
    by_day: dict[str, list[float]] = {}
    for r in matured:
        by_day.setdefault(r["signal_date"], []).append(float(r["return_raw"]))
    axis = set(days)
    outside = sum(len(v) for d, v in by_day.items() if d not in axis)
    return {
        "n_matured": len(vals),
        "mean": mean(vals) if vals else None,
        "median": percentile(vals, 50),
        "q25": percentile(vals, 25),
        "q75": percentile(vals, 75),
        "min": min(vals) if vals else None,
        "max": max(vals) if vals else None,
        "max_up_median": percentile(ups, 50),
        "max_down_median": percentile(downs, 50),
        "n_event": len({r["event_id"] for r in matured}),
        "n_item": len({(r["event_id"], r["item_seq"]) for r in matured}),
        "n_price_observation": len(matured),
        "n_signal_date": len(by_day),
        "n_matured_outside_axis": outside,  # 비거래일 사건 — bootstrap 날짜 축 밖
        "bootstrap": bootstrap.date_block_ci(
            days,
            by_day,
            block=bootstrap.block_days(horizon),
            iterations=iterations,
            seed=seed,
        ),
    }


def build(
    snap: Snapshot,
    cal: px.Calendar,
    *,
    end: str,
    generated_at: str,
    iterations: int = bootstrap.ITERATIONS,
    seed: int = bootstrap.SEED,
) -> dict[str, Any]:
    if snap.problems:
        raise InvalidInput("; ".join(snap.problems))
    start = snap.meta.get("primary_start_date")
    days = dates.trading_days(cal, start, end) if start else []
    runs = {r["event_id"]: r for r in snap.runs}
    items = {(i["event_id"], i["item_seq"]): i for i in snap.items}
    deliveries = {d["event_id"]: d for d in snap.deliveries}
    outcomes: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for o in snap.outcomes:
        outcomes.setdefault((o["event_id"], o["item_seq"]), []).append(o)

    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    kept: set[tuple[str, int]] = set()
    partial_items = 0
    events: set[str] = set()
    memo: dict[tuple[str, Optional[str]], dict[int, Optional[str]]] = {}
    for t in snap.targets if start else []:
        if not (start <= t.signal_date <= end):
            continue
        item = items[(t.event_id, t.item_seq)]
        if item["disposition"] not in OBSERVED_DISPOSITIONS:
            continue
        kept.add((t.event_id, t.item_seq))
        events.add(t.event_id)
        run = runs[t.event_id]
        status = (deliveries.get(t.event_id) or {}).get("delivery_status")
        views = ["observed"]
        if item["disposition"] == "sent" and status == "sent":
            views.append("delivered")
        if item["disposition"] == "sent" and status == "partial":
            partial_items += 1
        exposure = item.get("exposure") or "NONE"
        base = (
            run["push_kind"],
            t.subject_kind,
            item.get("state") or "—",
            run.get("contract_version"),
        )
        rows = dates.rows_known_by(outcomes.get((t.event_id, t.item_seq), []), end)
        per = ledger_outcome._expected(t) // len(ledger_outcome.HORIZONS)
        key = (t.signal_date, t.schedule)
        if key not in memo:
            memo[key] = dates.eval_dates(cal, t.signal_date, t.schedule)
        for h in ledger_outcome.HORIZONS:
            own = [
                dict(r, signal_date=t.signal_date) for r in rows if r["horizon"] == h
            ]
            gap = max(0, per - len(own))
            when = memo[key][h]
            pend = "pending_not_due" if (when is None or when > end) else "pending_due"
            for view in views:
                for r in own:
                    g = groups.setdefault(
                        (exposure, view, *base, r.get("price_basis") or NO_BASIS, h),
                        {"rows": [], "pending_not_due": 0, "pending_due": 0},
                    )
                    g["rows"].append(r)
                if gap:
                    g = groups.setdefault(
                        (exposure, view, *base, NO_BASIS, h),
                        {"rows": [], "pending_not_due": 0, "pending_due": 0},
                    )
                    g[pend] += gap

    table = []
    for k in sorted(groups, key=_group_order):
        g = groups[k]
        exposure, view, kind, subject, state, contract, basis, h = k
        table.append(
            {
                "exposure": exposure,
                "exposure_label": EXPOSURE_LABEL.get(
                    exposure, f"알 수 없는 노출값({exposure})"
                ),
                "view": view,
                "push_kind": kind,
                "subject_kind": subject,
                "state": state,
                "contract_version": contract,
                "price_basis": basis,
                "horizon": h,
                "status_counts": dict(
                    sorted(Counter(r["status"] for r in g["rows"]).items())
                ),
                "pending_not_due": g["pending_not_due"],
                "pending_due": g["pending_due"],
                **_stats(g["rows"], days, h, iterations, seed),
            }
        )
    with_fb = [e for e in sorted(events) if e in snap.feedback]
    return {
        "report": "R1",
        "version": REPORT_VERSION,
        "generated_at": generated_at,
        "input": input_summary(snap),
        "window": {"start": start, "end": end, "trading_days": len(days)},
        "settings": {
            "iterations": iterations,
            "seed": seed,
            "block_days": "max(5, horizon)",
            "ci": [bootstrap.LOW_PCT, bootstrap.HIGH_PCT],
            "quantile": "(n-1)p linear",
        },
        "population": {
            "items": len(kept),
            "events": len(events),
            "partial_sent_items": partial_items,
            "exclusions": _exclusions(snap, start or "", end, kept),
        },
        "groups": table,
        "feedback": {
            "events_with_feedback": len(with_fb),
            "events_without_feedback": len(events) - len(with_fb),
            "latest_helpfulness": dict(
                sorted(
                    Counter(snap.feedback[e]["helpfulness"] for e in with_fb).items()
                )
            ),
            "latest_action": dict(
                sorted(
                    Counter(
                        snap.feedback[e].get("action") or "선택 안 함" for e in with_fb
                    ).items()
                )
            ),
            "note": "평가는 표본 · 통계와 무관한 부가 정보 — 평가 없음은 제외 · 부정이 아니다",
        },
    }
